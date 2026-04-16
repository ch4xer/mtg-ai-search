import json
import logging
import os
from collections import defaultdict
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

import re

from .db import filter_cards, get_cards_by_ids, search_abilities, text_match_cards, vector_search_cards
from .embedding import encode_query

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
ABILITY_DISTANCE_THRESHOLD = 0.18
VECTOR_SEARCH_N_RESULTS = 50
RERANK_TOP_N = 20  # Number of cards to send to LLM for reranking
RRF_K = 60
FILTER_KEYS = (
    "colors",
    "type",
    "released_at",
    "layout",
    "mana_cost",
    "cmc",
    "power",
    "toughness",
)
VECTOR_QUERY_COLUMNS = {
    "name": "name_embedding",
    "oracle_text": "oracle_text_embedding",
}
QUERY_OPTIMIZER_PROMPT = (
    "You are a Magic: The Gathering expert. Given a user's card search query, "
    "extract structured information.\n\n"
    "Return a JSON object with these fields:\n"
    '- "oracle_text": English description of the card effect/mechanics for vector search. Leave empty if the user only specified a card name.\n'
    '- "name": exact card name if the user specified one, otherwise empty string\n'
    '- "type": card type and/or subtype if specified, space-separated (e.g. "Creature", "Creature Eldrazi", "Instant", "Artifact Equipment"). '
    "Include supertypes (Legendary), card types (Creature, Instant, Sorcery, Enchantment, Artifact, Land, Planeswalker), "
    "and subtypes/creature types (Eldrazi, Dragon, Human, Goblin, Angel, etc.). Otherwise empty string\n"
    '- "colors": color codes for filtering, space-separated. W=White, U=Blue, B=Black, R=Red, G=Green, C=Colorless. '
    'For example "B", "B R", "C" for colorless. Otherwise empty string\n'
    '- "released_at": date condition if specified (e.g. ">2020-01-01"), otherwise empty string\n'
    '- "layout": card layout if specified (e.g. "transform"), otherwise empty string\n'
    '- "mana_cost": mana cost condition if specified, otherwise empty string\n'
    '- "cmc": mana value condition if specified (e.g. "<3", ">5"), otherwise empty string\n'
    '- "power": power condition if specified (e.g. ">10"), otherwise empty string\n'
    '- "toughness": toughness condition if specified, otherwise empty string\n\n'
    "Examples:\n"
    'Input: "能让对手弃牌的黑色生物"\n'
    'Output: {"oracle_text": "discard cards from opponent hand", "name": "", "type": "Creature", '
    '"colors": "B", "released_at": "", "layout": "", "mana_cost": "", "cmc": "", "power": "", "toughness": ""}\n\n'
    'Input: "red instant that deals damage with cmc less than 3"\n'
    'Output: {"oracle_text": "deal direct damage to target", "name": "", "type": "Instant", '
    '"colors": "R", "released_at": "", "layout": "", "mana_cost": "", "cmc": "<3", "power": "", "toughness": ""}\n\n'
    'Input: "creatures with power greater than 10 released after 2020"\n'
    'Output: {"oracle_text": "", "name": "", "type": "Creature", '
    '"colors": "", "released_at": ">2020-01-01", "layout": "", "mana_cost": "", "cmc": "", "power": ">10", "toughness": ""}\n\n'
    "Return ONLY the JSON object, nothing else."
)

RERANK_PROMPT = (
    "You are a Magic: The Gathering expert helping to rank search results by relevance.\n"
    "Given the user's original search query and a list of candidate cards, "
    "evaluate how well each card matches the user's intent.\n\n"
    "For each card, consider:\n"
    "- Does the card name match what the user might be looking for?\n"
    "- Does the card type match the user's requirements?\n"
    "- Do the card's abilities/effects align with the user's description?\n"
    "- Are there any color, mana cost, or other constraints that should be considered?\n\n"
    "Return a JSON object with a single field 'rankings' containing an array of card IDs "
    "sorted by relevance (most relevant first). Only include cards that are reasonably relevant.\n"
    "Format: {\"rankings\": [\"card_id_1\", \"card_id_2\", ...]}\n\n"
    "If no cards are relevant, return: {\"rankings\": []}\n\n"
    "Return ONLY the JSON object, nothing else."
)

llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key=DEEPSEEK_API_KEY,
    temperature=0.3,
)


class SearchState(TypedDict):
    query: str
    oracle_text: str
    name: str
    type: str
    colors: str
    released_at: str
    layout: str
    mana_cost: str
    cmc: str
    power: str
    toughness: str
    filtered_card_ids: list[str] | None
    abilities: list[dict]
    vector_queries: dict[str, str]
    candidate_results: list[dict]  # Results before LLM reranking
    ranked_results: list[dict]
    tokens_prompt: int
    tokens_completion: int
    rerank_tokens_prompt: int
    rerank_tokens_completion: int


INITIAL_SEARCH_STATE: SearchState = {
    "query": "",
    "oracle_text": "",
    "name": "",
    "type": "",
    "colors": "",
    "released_at": "",
    "layout": "",
    "mana_cost": "",
    "cmc": "",
    "power": "",
    "toughness": "",
    "filtered_card_ids": None,
    "abilities": [],
    "vector_queries": {},
    "candidate_results": [],
    "ranked_results": [],
    "tokens_prompt": 0,
    "tokens_completion": 0,
    "rerank_tokens_prompt": 0,
    "rerank_tokens_completion": 0,
}


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _get_token_usage(response) -> tuple[int, int]:
    usage = getattr(response, "usage_metadata", None) or {}
    if isinstance(usage, dict):
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    return getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0)


def _parse_optimizer_response(content: str) -> dict[str, str]:
    try:
        data = _extract_json(content)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse LLM response as JSON: %s", content)
        data = {}

    return {
        "oracle_text": data.get("oracle_text", ""),
        "name": data.get("name", ""),
        "type": data.get("type", ""),
        "colors": data.get("colors", ""),
        "released_at": data.get("released_at", ""),
        "layout": data.get("layout", ""),
        "mana_cost": data.get("mana_cost", ""),
        "cmc": data.get("cmc", ""),
        "power": data.get("power", ""),
        "toughness": data.get("toughness", ""),
    }


def _build_filters(state: SearchState) -> dict:
    filters = {key: state[key] for key in FILTER_KEYS if state.get(key)}
    abilities = state.get("abilities", [])
    if abilities:
        filters["keywords"] = [ability["name"] for ability in abilities]
    return filters


def _build_vector_queries(state: SearchState) -> dict[str, str]:
    queries: dict[str, str] = {}
    if state.get("name"):
        queries["name"] = state["name"]
    if state.get("oracle_text"):
        queries["oracle_text"] = state["oracle_text"]
    if not queries and state.get("filtered_card_ids") is None:
        queries["oracle_text"] = state["query"]
    return queries


def _fuse_rankings(rankings: dict[str, list[str]]) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings.values():
        for rank, card_id in enumerate(ranking, start=1):
            scores[card_id] += 1.0 / (RRF_K + rank)
    return sorted(scores, key=lambda card_id: scores[card_id], reverse=True)[
        :VECTOR_SEARCH_N_RESULTS
    ]


def optimize_query(state: SearchState) -> dict:
    """Use LLM to optimize the query and extract structured card constraints."""
    response = llm.invoke(
        [
            SystemMessage(content=QUERY_OPTIMIZER_PROMPT),
            HumanMessage(content=state["query"]),
        ]
    )
    tokens_prompt, tokens_completion = _get_token_usage(response)

    content = response.content
    if isinstance(content, str):
        content = content.strip()

    logger.info(">>> Original query: %s", state["query"])
    logger.info(">>> Token usage: prompt=%d, completion=%d", tokens_prompt, tokens_completion)

    result = _parse_optimizer_response(content)
    result["tokens_prompt"] = tokens_prompt
    result["tokens_completion"] = tokens_completion

    logger.info(
        "<<< Parsed: %s",
        {
            key: value
            for key, value in result.items()
            if value and key not in ("tokens_prompt", "tokens_completion")
        },
    )
    return result


async def filter_cards_node(state: SearchState) -> dict:
    """Filter cards by structured conditions and keyword abilities."""
    filters = _build_filters(state)
    if not filters:
        logger.info("<<< No filters, skipping structured filtering")
        return {"filtered_card_ids": None}

    card_ids = await filter_cards(filters)
    logger.info("<<< Filtered to %d cards", len(card_ids))
    return {"filtered_card_ids": card_ids}


async def search_abilities_node(state: SearchState) -> dict:
    """Search keyword abilities by vector similarity."""
    oracle_text = state.get("oracle_text", "")
    if not oracle_text:
        return {"abilities": []}

    query_embedding = encode_query([oracle_text])[0]
    abilities = await search_abilities(
        query_embedding,
        n_results=5,
        distance_threshold=ABILITY_DISTANCE_THRESHOLD,
    )

    for ability in abilities:
        logger.info("  - %s (distance: %.3f)", ability["name"], ability["distance"])
    logger.info("<<< Found %d relevant abilities", len(abilities))
    return {"abilities": abilities}


def prepare_vector_queries(state: SearchState) -> dict:
    """Prepare vector query texts for vector search."""
    queries = _build_vector_queries(state)
    logger.info("<<< Vector queries: %s", queries)
    return {"vector_queries": queries}


async def vector_search_node(state: SearchState) -> dict:
    """Run vector search and combine rankings via reciprocal rank fusion."""
    queries = state.get("vector_queries", {})
    filtered_card_ids = state.get("filtered_card_ids")

    if filtered_card_ids is not None and not filtered_card_ids:
        logger.info("<<< Filters matched 0 cards, returning empty")
        return {"candidate_results": [], "ranked_results": []}

    if not queries and filtered_card_ids:
        cards = await get_cards_by_ids(filtered_card_ids[:VECTOR_SEARCH_N_RESULTS])
        logger.info("<<< No vector queries, returning %d filtered cards directly", len(cards))
        return {"candidate_results": cards}

    rankings: dict[str, list[str]] = {}
    for query_key, query_text in queries.items():
        if not query_text:
            continue

        results = await vector_search_cards(
            VECTOR_QUERY_COLUMNS[query_key],
            encode_query([query_text])[0],
            n_results=VECTOR_SEARCH_N_RESULTS,
            card_ids=filtered_card_ids,
        )
        rankings[query_key] = [card_id for card_id, _ in results]
        logger.info("  Vector search [%s]: %d results", query_key, len(results))

    cards = await get_cards_by_ids(_fuse_rankings(rankings))
    logger.info("<<< RRF fusion: %d results", len(cards))
    return {"candidate_results": cards}


def _format_card_for_rerank(card: dict) -> str:
    """Format a card's key info for LLM reranking."""
    name = card.get("name", "Unknown")
    type_line = card.get("type_line", "")
    colors = "".join(card.get("colors", []) or [])
    cmc = card.get("cmc", "")
    oracle_text = card.get("oracle_text", "")
    keywords = ", ".join(card.get("keywords", []) or [])

    # Truncate long oracle text
    if oracle_text and len(oracle_text) > 200:
        oracle_text = oracle_text[:200] + "..."

    parts = [f"Name: {name}", f"Type: {type_line}"]
    if colors:
        parts.append(f"Colors: {colors}")
    if cmc:
        parts.append(f"CMC: {cmc}")
    if oracle_text:
        parts.append(f"Text: {oracle_text}")
    if keywords:
        parts.append(f"Keywords: {keywords}")

    return "\n".join(parts)


def rerank_with_llm(state: SearchState) -> dict:
    """Use LLM to rerank candidate results based on user's original query."""
    candidate_results = state.get("candidate_results", [])
    query = state.get("query", "")

    # If no candidates, return empty
    if not candidate_results:
        return {"ranked_results": [], "rerank_tokens_prompt": 0, "rerank_tokens_completion": 0}

    # If only a few results, skip reranking
    if len(candidate_results) <= 5:
        return {"ranked_results": candidate_results, "rerank_tokens_prompt": 0, "rerank_tokens_completion": 0}

    # Take top N candidates for reranking
    top_candidates = candidate_results[:RERANK_TOP_N]

    # Build card list for LLM
    card_list = []
    for i, card in enumerate(top_candidates, 1):
        card_info = _format_card_for_rerank(card)
        card_id = card.get("id", "")
        card_list.append(f"[{i}] ID: {card_id}\n{card_info}")

    cards_text = "\n\n".join(card_list)
    user_message = f"User query: {query}\n\nCandidate cards:\n{cards_text}"

    logger.info(">>> Reranking %d candidates with LLM", len(top_candidates))

    response = llm.invoke(
        [
            SystemMessage(content=RERANK_PROMPT),
            HumanMessage(content=user_message),
        ]
    )

    tokens_prompt, tokens_completion = _get_token_usage(response)
    logger.info(">>> Rerank token usage: prompt=%d, completion=%d", tokens_prompt, tokens_completion)

    content = response.content
    if isinstance(content, str):
        content = content.strip()

    # Parse rankings from LLM response
    try:
        data = _extract_json(content)
        ranked_ids = data.get("rankings", [])
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse rerank response as JSON: %s", content)
        ranked_ids = []

    # Map card IDs to full card data
    card_map = {card.get("id"): card for card in top_candidates}

    # Build final ranked list
    ranked_results = []
    for card_id in ranked_ids:
        if card_id in card_map:
            ranked_results.append(card_map[card_id])

    # Add remaining candidates that weren't ranked by LLM
    remaining = [card for card in top_candidates if card.get("id") not in ranked_ids]
    ranked_results.extend(remaining)

    # Also include candidates beyond RERANK_TOP_N at the end
    if len(candidate_results) > RERANK_TOP_N:
        ranked_results.extend(candidate_results[RERANK_TOP_N:])

    logger.info("<<< LLM reranked: %d results (from %d candidates)", len(ranked_results), len(candidate_results))

    return {
        "ranked_results": ranked_results,
        "rerank_tokens_prompt": tokens_prompt,
        "rerank_tokens_completion": tokens_completion,
    }


def build_graph():
    graph = StateGraph(SearchState)

    graph.add_node("optimize_query", optimize_query)
    graph.add_node("search_abilities", search_abilities_node)
    graph.add_node("filter_cards", filter_cards_node)
    graph.add_node("prepare_vector_queries", prepare_vector_queries)
    graph.add_node("vector_search", vector_search_node)
    graph.add_node("rerank_with_llm", rerank_with_llm)

    graph.set_entry_point("optimize_query")
    graph.add_edge("optimize_query", "search_abilities")
    graph.add_edge("search_abilities", "filter_cards")
    graph.add_edge("filter_cards", "prepare_vector_queries")
    graph.add_edge("prepare_vector_queries", "vector_search")
    graph.add_edge("vector_search", "rerank_with_llm")
    graph.add_edge("rerank_with_llm", END)

    return graph.compile()


search_agent = build_graph()


class SearchResult(TypedDict):
    ranked_results: list[dict]
    tokens_prompt: int
    tokens_completion: int
    rerank_tokens_prompt: int
    rerank_tokens_completion: int


def _dedup_by_name(cards: list[dict]) -> list[dict]:
    """Keep only the newest printing per card name, preserving order."""
    seen: dict[str, int] = {}
    for i, card in enumerate(cards):
        name = card.get("name", "")
        if name not in seen:
            seen[name] = i
        else:
            prev = cards[seen[name]]
            if (card.get("released_at") or "") > (prev.get("released_at") or ""):
                seen[name] = i
    keep = set(seen.values())
    return [card for i, card in enumerate(cards) if i in keep]


_NON_ENGLISH_RE = re.compile(r"[^\x00-\x7F]")

TRANSLATE_PROMPT = (
    "Translate the following text to English. "
    "Return ONLY the English translation, nothing else."
)


def _is_english(text: str) -> bool:
    """Return True if the text contains only ASCII characters (English)."""
    return not _NON_ENGLISH_RE.search(text)


async def _translate_to_english(text: str) -> tuple[str, int, int]:
    """Translate non-English text to English using LLM.

    Returns (translated_text, prompt_tokens, completion_tokens).
    """
    response = await llm.ainvoke([
        SystemMessage(content=TRANSLATE_PROMPT),
        HumanMessage(content=text),
    ])
    tokens_prompt, tokens_completion = _get_token_usage(response)
    translated = response.content.strip() if isinstance(response.content, str) else text
    logger.info(">>> Translated '%s' → '%s'", text, translated)
    return translated, tokens_prompt, tokens_completion


async def run_search(query: str) -> SearchResult:
    """Run the search agent with a query. Returns results and token usage.

    First attempts a direct string match on card name, oracle text, and type line.
    If the input is non-English, it is translated first. If any cards match the
    full input string, they are returned immediately without invoking the AI pipeline.
    """
    query_stripped = query.strip()
    translate_tokens_prompt = 0
    translate_tokens_completion = 0

    if _is_english(query_stripped):
        search_text = query_stripped
    else:
        search_text, translate_tokens_prompt, translate_tokens_completion = (
            await _translate_to_english(query_stripped)
        )

    # Direct string match
    matches = await text_match_cards(search_text)
    if matches:
        logger.info("<<< Direct text match: %d results for '%s'", len(matches), search_text)
        return {
            "ranked_results": matches,
            "tokens_prompt": translate_tokens_prompt,
            "tokens_completion": translate_tokens_completion,
        }

    logger.info("<<< No direct text match for '%s', falling back to AI search", search_text)

    # Fall back to full AI pipeline
    result = await search_agent.ainvoke({**INITIAL_SEARCH_STATE, "query": query})
    return {
        "ranked_results": _dedup_by_name(result["ranked_results"]),
        "tokens_prompt": translate_tokens_prompt + result.get("tokens_prompt", 0) + result.get("rerank_tokens_prompt", 0),
        "tokens_completion": translate_tokens_completion + result.get("tokens_completion", 0) + result.get("rerank_tokens_completion", 0),
    }
