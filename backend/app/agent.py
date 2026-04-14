import json
import logging
import os
from collections import defaultdict
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from .db import filter_cards, get_cards_by_ids, search_abilities, vector_search_cards
from .embedding import encode_query

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
ABILITY_DISTANCE_THRESHOLD = 0.18
VECTOR_SEARCH_N_RESULTS = 50
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
    ranked_results: list[dict]
    tokens_prompt: int
    tokens_completion: int


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
    "ranked_results": [],
    "tokens_prompt": 0,
    "tokens_completion": 0,
}


class SearchResult(TypedDict):
    ranked_results: list[dict]
    tokens_prompt: int
    tokens_completion: int


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
        return {"ranked_results": []}

    if not queries and filtered_card_ids:
        cards = await get_cards_by_ids(filtered_card_ids[:VECTOR_SEARCH_N_RESULTS])
        logger.info("<<< No vector queries, returning %d filtered cards directly", len(cards))
        return {"ranked_results": cards}

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
    return {"ranked_results": cards}


def build_graph():
    graph = StateGraph(SearchState)

    graph.add_node("optimize_query", optimize_query)
    graph.add_node("search_abilities", search_abilities_node)
    graph.add_node("filter_cards", filter_cards_node)
    graph.add_node("prepare_vector_queries", prepare_vector_queries)
    graph.add_node("vector_search", vector_search_node)

    graph.set_entry_point("optimize_query")
    graph.add_edge("optimize_query", "search_abilities")
    graph.add_edge("search_abilities", "filter_cards")
    graph.add_edge("filter_cards", "prepare_vector_queries")
    graph.add_edge("prepare_vector_queries", "vector_search")
    graph.add_edge("vector_search", END)

    return graph.compile()


search_agent = build_graph()


async def run_search(query: str) -> SearchResult:
    """Run the search agent with a query. Returns results and token usage."""
    result = await search_agent.ainvoke({**INITIAL_SEARCH_STATE, "query": query})
    return {
        "ranked_results": result["ranked_results"],
        "tokens_prompt": result.get("tokens_prompt", 0),
        "tokens_completion": result.get("tokens_completion", 0),
    }
