import json
import logging
from time import perf_counter
from collections import defaultdict
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from .embedding import encode_query
from .llm_provider import create_chat_llm
from .repositories.cards import (
    effect_vector_search_cards,
    filter_cards,
    get_cards_by_ids,
    search_abilities,
    text_match_cards,
    vector_search_cards,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

ABILITY_DISTANCE_THRESHOLD = 0.18
EFFECT_DISTANCE_THRESHOLD = 0.5
VECTOR_SEARCH_N_RESULTS = 50
EFFECT_VECTOR_SEARCH_N_RESULTS = 100
MAX_EFFECT_MATCHES_PER_CARD = 2
RERANK_TOP_N = 10  # Number of cards to send to LLM for reranking
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
    "Extract MTG card-search constraints. Return ONLY JSON with exactly these keys: "
    "oracle_text,name,type,colors,released_at,layout,mana_cost,cmc,power,toughness. Empty string means unspecified.\n"
    "Field rules:\n"
    "oracle_text: English effect/gameplay intent only, not card titles.\n"
    "name: English card-title query. If input is a short title-like noun phrase, put its literal English title here and leave oracle_text empty.\n"
    "type: supertypes/types/subtypes, space-separated, e.g. Legendary Creature Dragon.\n"
    "colors: W U B R G C, space-separated. released_at: date condition like >2020-01-01.\n"
    "layout: layout word like transform, modal_dfc, adventure. mana_cost: condition on mana cost if explicit.\n"
    "cmc,power,toughness: numeric conditions using >,>=,<,<=,=.\n"
    "Type allocation rules:\n"
    "- If a token/word is a card supertype, type, creature type, planeswalker type, or any MTG subtype, put it in type first.\n"
    "- Do not repeat the same semantic token in multiple fields. If a word is already captured in type, do not repeat it in name.\n"
    "- When a query mixes a kind/category word with a title-like word, keep only the non-type/title-distinguishing remainder in name.\n"
    "Color rules:\n"
    "- Only set colors when the user's original query explicitly mentions a color, color combination, mana symbol, or colorless.\n"
    "- Never infer colors from creature race, subtype, faction, lore, or common MTG knowledge.\n"
    "- If the query does not explicitly mention color, leave colors empty.\n"
    "Preserve the user's semantic relationships in oracle_text, including actor, target, quantity, and qualifiers when they matter to card matching.\n"
    "Be faithful to the original wording. Do not add unstated constraints.\n"
    "Do not map a localized/translated title to a different known card by guesswork.\n"
    'Example full: "2020年后的红蓝双面传奇龙，法术力值小于5，力量大于3，能抓牌" -> '
    '{"oracle_text":"draw cards","name":"","type":"Legendary Creature Dragon","colors":"U R","released_at":">2020-01-01",'
    '"layout":"transform","mana_cost":"","cmc":"<5","power":">3","toughness":""}\n'
    'Example discard: "能让对手弃牌的黑色生物" -> '
    '{"oracle_text":"target opponent discards a card","name":"","type":"Creature","colors":"B","released_at":"","layout":"","mana_cost":"","cmc":"","power":"","toughness":""}\n'
    'Example faithful typing: "奥扎奇泰坦" -> '
    '{"oracle_text":"","name":"Titan","type":"Creature Eldrazi","colors":"","released_at":"","layout":"","mana_cost":"","cmc":"","power":"","toughness":""}'
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
    "Return a JSON object with a single field 'rankings' containing an array of candidate numbers "
    "sorted by relevance (most relevant first). Only include candidates that are reasonably relevant.\n"
    "Use the numeric candidate labels exactly as provided. Do not return card IDs or card names.\n"
    "Format: {\"rankings\": [3, 1, 7, 2]}\n\n"
    "If no cards are relevant, return: {\"rankings\": []}\n\n"
    "Return ONLY the JSON object, nothing else."
)

llm = create_chat_llm(temperature=0.3)


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
    query_embeddings: dict[str, list[float]]
    candidate_results: list[dict]  # Results before LLM reranking
    ranked_results: list[dict]
    rerank_enabled: bool
    rerank_top_n: int
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
    "query_embeddings": {},
    "candidate_results": [],
    "ranked_results": [],
    "rerank_enabled": False,
    "rerank_top_n": RERANK_TOP_N,
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


def _fuse_rankings(rankings: dict[str, list[str]]) -> list[tuple[str, float]]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings.values():
        for rank, card_id in enumerate(ranking, start=1):
            scores[card_id] += 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:VECTOR_SEARCH_N_RESULTS]


def _rank_effect_results(effect_results: list[dict]) -> tuple[list[str], dict[str, list[dict]]]:
    """Aggregate effect-level matches into card-level rankings.

    Caps matches per card at MAX_EFFECT_MATCHES_PER_CARD so a single card with
    many weakly related chunks can't out-score a card with fewer strong hits.
    """
    scores: dict[str, float] = defaultdict(float)
    matches_by_card: dict[str, list[dict]] = defaultdict(list)

    for rank, row in enumerate(effect_results, start=1):
        card_id = row["card_id"]
        if len(matches_by_card[card_id]) >= MAX_EFFECT_MATCHES_PER_CARD:
            continue

        scores[card_id] += 1.0 / (RRF_K + rank)
        matches_by_card[card_id].append(
            {
                "effect_id": row["effect_id"],
                "effect_text": row["effect_text"],
                "face_index": row["face_index"],
                "chunk_index": row["chunk_index"],
                "source": row["source"],
                "distance": row["distance"],
            }
        )

    ranking = [card_id for card_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]
    return ranking, matches_by_card


def optimize_query(state: SearchState) -> dict:
    """Use LLM to optimize the query and extract structured card constraints."""
    started = perf_counter()
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
    logger.info("<<< optimize_query took %.2fs", perf_counter() - started)
    return result


async def filter_cards_node(state: SearchState) -> dict:
    """Filter cards by structured conditions and keyword abilities."""
    started = perf_counter()
    filters = _build_filters(state)
    if not filters:
        logger.info("<<< No filters, skipping structured filtering")
        logger.info("<<< filter_cards took %.2fs", perf_counter() - started)
        return {"filtered_card_ids": None}

    card_ids = await filter_cards(filters)
    logger.info("<<< Filtered to %d cards", len(card_ids))
    logger.info("<<< filter_cards took %.2fs", perf_counter() - started)
    return {"filtered_card_ids": card_ids}


async def search_abilities_node(state: SearchState) -> dict:
    """Search keyword abilities by vector similarity."""
    started = perf_counter()
    oracle_text = state.get("oracle_text", "")
    if not oracle_text:
        logger.info("<<< search_abilities skipped in %.2fs", perf_counter() - started)
        return {"abilities": []}

    query_embedding = state.get("query_embeddings", {}).get("ability_oracle_text")
    if query_embedding is None:
        query_embedding = encode_query([oracle_text])[0]

    abilities = await search_abilities(
        query_embedding,
        n_results=5,
        distance_threshold=ABILITY_DISTANCE_THRESHOLD,
    )

    for ability in abilities:
        logger.info("  - %s (distance: %.3f)", ability["name"], ability["distance"])
    logger.info("<<< Found %d relevant abilities", len(abilities))
    logger.info("<<< search_abilities took %.2fs", perf_counter() - started)
    return {"abilities": abilities}


def prepare_ability_embedding(state: SearchState) -> dict:
    """Prepare the oracle-text embedding used for keyword ability matching."""
    started = perf_counter()
    oracle_text = state.get("oracle_text", "")
    if not oracle_text:
        logger.info("<<< prepare_ability_embedding skipped in %.2fs", perf_counter() - started)
        return {"query_embeddings": {}}

    started_embedding = perf_counter()
    embedding = encode_query([oracle_text])[0]
    logger.info(
        "<<< ability embedding: %r in %.2fs",
        oracle_text,
        perf_counter() - started_embedding,
    )
    logger.info("<<< prepare_ability_embedding took %.2fs", perf_counter() - started)
    return {"query_embeddings": {"ability_oracle_text": embedding}}


def prepare_vector_queries(state: SearchState) -> dict:
    """Prepare vector query texts and batch missing embeddings for vector search."""
    started = perf_counter()
    queries = _build_vector_queries(state)
    logger.info("<<< Vector queries: %s", queries)

    query_embeddings = dict(state.get("query_embeddings", {}))
    texts_by_key: dict[str, str] = {}
    for query_key, query_text in queries.items():
        if query_text:
            embedding_key = f"vector:{query_key}"
            if embedding_key in query_embeddings:
                continue
            if query_text == state.get("oracle_text") and "ability_oracle_text" in query_embeddings:
                query_embeddings[embedding_key] = query_embeddings["ability_oracle_text"]
                continue
            texts_by_key[embedding_key] = query_text

    if texts_by_key:
        unique_texts = list(dict.fromkeys(texts_by_key.values()))
        started_embedding = perf_counter()
        embeddings = encode_query(unique_texts)
        logger.info("<<< embedding batch: %d texts in %.2fs", len(unique_texts), perf_counter() - started_embedding)
        embedding_by_text = dict(zip(unique_texts, embeddings))
        query_embeddings.update({
            key: embedding_by_text[text]
            for key, text in texts_by_key.items()
        })

    logger.info("<<< prepare_vector_queries took %.2fs", perf_counter() - started)
    return {"vector_queries": queries, "query_embeddings": query_embeddings}


async def vector_search_node(state: SearchState) -> dict:
    """Run vector search and combine rankings via reciprocal rank fusion."""
    started = perf_counter()
    queries = state.get("vector_queries", {})
    filtered_card_ids = state.get("filtered_card_ids")
    query_embeddings = state.get("query_embeddings", {})

    if filtered_card_ids is not None and not filtered_card_ids:
        logger.info("<<< Filters matched 0 cards, returning empty")
        logger.info("<<< vector_search took %.2fs", perf_counter() - started)
        return {"candidate_results": [], "ranked_results": []}

    if not queries and filtered_card_ids:
        cards = await get_cards_by_ids(filtered_card_ids[:VECTOR_SEARCH_N_RESULTS])
        logger.info("<<< No vector queries, returning %d filtered cards directly", len(cards))
        logger.info("<<< vector_search took %.2fs", perf_counter() - started)
        return {"candidate_results": cards}

    rankings: dict[str, list[str]] = {}
    effect_matches_by_card: dict[str, list[dict]] = {}
    for query_key, query_text in queries.items():
        if not query_text:
            continue

        query_embedding = query_embeddings.get(f"vector:{query_key}")
        if query_embedding is None:
            query_embedding = encode_query([query_text])[0]

        if query_key == "oracle_text":
            effect_results = await effect_vector_search_cards(
                query_embedding,
                n_results=EFFECT_VECTOR_SEARCH_N_RESULTS,
                card_ids=filtered_card_ids,
                distance_threshold=EFFECT_DISTANCE_THRESHOLD,
            )
            if effect_results:
                effect_ranking, effect_matches = _rank_effect_results(effect_results)
                rankings["oracle_text_effects"] = effect_ranking[:VECTOR_SEARCH_N_RESULTS]
                effect_matches_by_card.update(effect_matches)
                logger.info(
                    "  Effect chunk search [%s]: %d chunks under %.3f, %d cards",
                    query_key,
                    len(effect_results),
                    EFFECT_DISTANCE_THRESHOLD,
                    len(effect_ranking),
                )
                continue
            logger.info("  Effect chunk search [%s]: 0 results, falling back to card-level", query_key)

        results = await vector_search_cards(
            VECTOR_QUERY_COLUMNS[query_key],
            query_embedding,
            n_results=VECTOR_SEARCH_N_RESULTS,
            card_ids=filtered_card_ids,
        )
        rankings[query_key] = [card_id for card_id, _ in results]
        logger.info("  Vector search [%s]: %d results", query_key, len(results))

    fused = _fuse_rankings(rankings)
    score_by_id = dict(fused)
    cards = await get_cards_by_ids([card_id for card_id, _ in fused])
    for card in cards:
        card["_search_score"] = score_by_id.get(card["id"], 0.0)
        if card["id"] in effect_matches_by_card:
            card["_matched_effects"] = effect_matches_by_card[card["id"]]
    logger.info("<<< RRF fusion: %d results", len(cards))
    logger.info("<<< vector_search took %.2fs", perf_counter() - started)
    return {"candidate_results": cards}


def _format_card_for_rerank(card: dict) -> str:
    """Format a card's key info for LLM reranking."""
    name = card.get("name", "Unknown")
    type_line = card.get("type_line", "")
    colors = "".join(card.get("colors", []) or [])
    cmc = card.get("cmc", "")
    matched_effects = card.get("_matched_effects") or []
    keywords = ", ".join(card.get("keywords", []) or [])

    parts = [f"Name: {name}", f"Type: {type_line}"]
    if colors:
        parts.append(f"Colors: {colors}")
    if cmc:
        parts.append(f"CMC: {cmc}")
    if matched_effects:
        effect_text = " / ".join(effect["effect_text"] for effect in matched_effects[:2])
        if len(effect_text) > 220:
            effect_text = effect_text[:220] + "..."
        parts.append(f"Matched effects: {effect_text}")
    if keywords:
        parts.append(f"Keywords: {keywords}")

    return "\n".join(parts)


def rerank_with_llm(state: SearchState) -> dict:
    """Use LLM to rerank candidate results based on user's original query."""
    started = perf_counter()
    candidate_results = state.get("candidate_results", [])
    rerank_enabled = state.get("rerank_enabled", True)
    rerank_top_n = state.get("rerank_top_n", RERANK_TOP_N)
    query = state.get("query", "")

    # If no candidates, return empty
    if not candidate_results:
        logger.info("<<< rerank skipped: no candidates in %.2fs", perf_counter() - started)
        return {"ranked_results": [], "rerank_tokens_prompt": 0, "rerank_tokens_completion": 0}

    if not rerank_enabled:
        logger.info("<<< rerank skipped: disabled in %.2fs", perf_counter() - started)
        return {"ranked_results": candidate_results, "rerank_tokens_prompt": 0, "rerank_tokens_completion": 0}

    # Take top N candidates for reranking
    top_candidates = candidate_results[:rerank_top_n]

    # Build card list for LLM
    card_list = []
    for i, card in enumerate(top_candidates, 1):
        card_info = _format_card_for_rerank(card)
        card_list.append(f"[{i}]\n{card_info}")

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
        ranked_numbers = data.get("rankings", [])
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse rerank response as JSON: %s", content)
        ranked_numbers = []

    card_map = {i: card for i, card in enumerate(top_candidates, 1)}

    # Build final ranked list
    ranked_results = []
    ranked_indexes: set[int] = set()
    for raw_number in ranked_numbers:
        try:
            number = int(raw_number)
        except (TypeError, ValueError):
            continue
        if number in card_map:
            ranked_results.append(card_map[number])
            ranked_indexes.add(number)

    # Add remaining candidates that weren't ranked by LLM
    remaining = [card for i, card in enumerate(top_candidates, 1) if i not in ranked_indexes]
    ranked_results.extend(remaining)

    # Also include candidates beyond RERANK_TOP_N at the end
    if len(candidate_results) > rerank_top_n:
        ranked_results.extend(candidate_results[rerank_top_n:])

    logger.info("<<< LLM reranked: %d results (from %d candidates)", len(ranked_results), len(candidate_results))
    logger.info("<<< rerank_with_llm took %.2fs", perf_counter() - started)

    return {
        "ranked_results": ranked_results,
        "rerank_tokens_prompt": tokens_prompt,
        "rerank_tokens_completion": tokens_completion,
    }


def build_graph():
    graph = StateGraph(SearchState)

    graph.add_node("optimize_query", optimize_query)
    graph.add_node("prepare_ability_embedding", prepare_ability_embedding)
    graph.add_node("search_abilities", search_abilities_node)
    graph.add_node("filter_cards", filter_cards_node)
    graph.add_node("prepare_vector_queries", prepare_vector_queries)
    graph.add_node("vector_search", vector_search_node)
    graph.add_node("rerank_with_llm", rerank_with_llm)

    graph.set_entry_point("optimize_query")
    graph.add_edge("optimize_query", "prepare_ability_embedding")
    graph.add_edge("prepare_ability_embedding", "search_abilities")
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


async def run_search(
    query: str,
    rerank_enabled: bool = False,
    rerank_top_n: int = RERANK_TOP_N,
) -> SearchResult:
    """Run the search agent with a query. Returns results and token usage.

    First attempts a direct string match on card name, oracle text, and type line.
    If any cards match the full input string, they are returned immediately without
    invoking the AI pipeline. Cross-language understanding is handled by the query
    optimizer instead of a separate translation call.
    """
    started = perf_counter()
    query_stripped = query.strip()

    # Direct string match
    started_text_match = perf_counter()
    matches = await text_match_cards(query_stripped)
    logger.info("<<< direct text match check took %.2fs", perf_counter() - started_text_match)
    if matches:
        logger.info("<<< Direct text match: %d results for '%s'", len(matches), query_stripped)
        logger.info("<<< run_search total took %.2fs", perf_counter() - started)
        return {
            "ranked_results": matches,
            "tokens_prompt": 0,
            "tokens_completion": 0,
        }

    logger.info("<<< No direct text match for '%s', falling back to AI search", query_stripped)

    # Fall back to full AI pipeline
    result = await search_agent.ainvoke({
        **INITIAL_SEARCH_STATE,
        "query": query,
        "rerank_enabled": rerank_enabled,
        "rerank_top_n": max(1, min(100, rerank_top_n)),
    })
    logger.info("<<< run_search total took %.2fs", perf_counter() - started)
    ranked_results = result["ranked_results"]
    if rerank_enabled:
        ranked_results = _dedup_by_name(ranked_results)
    return {
        "ranked_results": ranked_results,
        "tokens_prompt": result.get("tokens_prompt", 0) + result.get("rerank_tokens_prompt", 0),
        "tokens_completion": result.get("tokens_completion", 0) + result.get("rerank_tokens_completion", 0),
    }
