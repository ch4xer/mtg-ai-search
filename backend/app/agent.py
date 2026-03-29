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
from .embedding import encode

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key=DEEPSEEK_API_KEY,
    temperature=0.3,
)

ABILITY_DISTANCE_THRESHOLD = 0.18
VECTOR_SEARCH_N_RESULTS = 50
RRF_K = 60


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
    vector_queries: dict
    ranked_results: list[dict]


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown code fences if present."""
    text = text.strip()
    if text.startswith("```"):
        # Remove ```json ... ``` wrapper
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return json.loads(text)


# ── Node 1: optimize_query ──────────────────────────────────────────────

def optimize_query(state: SearchState) -> dict:
    """Use LLM to optimize query and extract structured card constraints."""
    response = llm.invoke([
        SystemMessage(content=(
            "You are a Magic: The Gathering expert. Given a user's card search query, "
            "extract structured information.\n\n"
            "Return a JSON object with these fields:\n"
            '- "oracle_text": English description of the card effect/mechanics for vector search. Leave empty if the user only specified a card name.\n'
            '- "name": exact card name if the user specified one, otherwise empty string\n'
            '- "type": card type and/or subtype if specified, space-separated (e.g. "Creature", "Creature Eldrazi", "Instant", "Artifact Equipment"). '
            'Include supertypes (Legendary), card types (Creature, Instant, Sorcery, Enchantment, Artifact, Land, Planeswalker), '
            'and subtypes/creature types (Eldrazi, Dragon, Human, Goblin, Angel, etc.). Otherwise empty string\n'
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
        )),
        HumanMessage(content=state["query"]),
    ])

    content = response.content
    if isinstance(content, str):
        content = content.strip()

    logger.info(">>> Original query: %s", state["query"])

    try:
        data = _extract_json(content)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse LLM response as JSON: %s", content)
        data = {}

    result = {
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

    logger.info("<<< Parsed: %s", {k: v for k, v in result.items() if v})

    return result


# ── Node 2a: filter_cards_node (parallel) ───────────────────────────────

async def filter_cards_node(state: SearchState) -> dict:
    """Filter cards by structured conditions and keyword abilities."""
    # Build filters dict from flat state fields
    filter_keys = ["colors", "type", "released_at", "layout", "mana_cost", "cmc", "power", "toughness"]
    filters = {k: state[k] for k in filter_keys if state.get(k)}

    # Add keyword abilities as filter
    abilities = state.get("abilities", [])
    if abilities:
        filters["keywords"] = [a["name"] for a in abilities]

    if not filters:
        logger.info("<<< No filters, skipping structured filtering")
        return {"filtered_card_ids": None}

    card_ids = await filter_cards(filters)
    logger.info("<<< Filtered to %d cards", len(card_ids))
    return {"filtered_card_ids": card_ids}


# ── Node 2b: search_abilities_node (parallel) ───────────────────────────

async def search_abilities_node(state: SearchState) -> dict:
    """Search keyword abilities by vector similarity."""
    query = state.get("oracle_text", "")
    if not query:
        return {"abilities": []}

    query_vec = encode([query])[0]
    abilities = await search_abilities(
        query_vec, n_results=5, distance_threshold=ABILITY_DISTANCE_THRESHOLD
    )

    for a in abilities:
        logger.info("  - %s (distance: %.3f)", a["name"], a["distance"])
    logger.info("<<< Found %d relevant abilities", len(abilities))

    return {"abilities": abilities}


# ── Node 3: prepare_vector_queries ───────────────────────────────────────

def prepare_vector_queries(state: SearchState) -> dict:
    """Prepare vector query texts for vector search."""
    oracle_text = state.get("oracle_text", "")
    card_name = state.get("name", "")

    queries = {}

    # name query: only if a specific card name was given
    if card_name:
        queries["name"] = card_name

    # oracle_text query: only if LLM extracted a card effect description
    if oracle_text:
        queries["oracle_text"] = oracle_text

    # If no queries at all, fall back to raw query for oracle_text
    if not queries:
        queries["oracle_text"] = state["query"]

    logger.info("<<< Vector queries: %s", queries)
    return {"vector_queries": queries}


# ── Node 4: vector_search_node ───────────────────────────────────────────

async def vector_search_node(state: SearchState) -> dict:
    """3-way vector search with RRF fusion."""
    queries = state.get("vector_queries", {})
    filtered_ids = state.get("filtered_card_ids")

    # None = no filters applied, search all cards
    # [] = filters applied but no cards matched, return empty
    if filtered_ids is not None and len(filtered_ids) == 0:
        logger.info("<<< Filters matched 0 cards, returning empty")
        return {"ranked_results": []}

    card_ids_filter = filtered_ids

    # Map query keys to embedding column names
    column_map = {
        "name": "name_embedding",
        "oracle_text": "oracle_text_embedding",
    }

    # Run each vector search
    rankings: dict[str, list[str]] = {}
    for key, text in queries.items():
        if not text:
            continue
        col = column_map[key]
        query_vec = encode([text])[0]
        results = await vector_search_cards(col, query_vec, n_results=VECTOR_SEARCH_N_RESULTS, card_ids=card_ids_filter)
        rankings[key] = [r[0] for r in results]  # list of card IDs in rank order
        logger.info("  Vector search [%s]: %d results", key, len(results))

    # RRF fusion
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings.values():
        for rank, card_id in enumerate(ranking, start=1):
            scores[card_id] += 1.0 / (RRF_K + rank)

    # Sort by RRF score descending, take top 10
    top_ids = sorted(scores, key=lambda card_id: scores[card_id], reverse=True)[:VECTOR_SEARCH_N_RESULTS]

    # Fetch full card data
    cards = await get_cards_by_ids(top_ids)
    logger.info("<<< RRF fusion: %d results", len(cards))

    return {"ranked_results": cards}


# ── Graph assembly ───────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(SearchState)

    graph.add_node("optimize_query", optimize_query)
    graph.add_node("filter_cards", filter_cards_node)
    graph.add_node("search_abilities", search_abilities_node)
    graph.add_node("prepare_vector_queries", prepare_vector_queries)
    graph.add_node("vector_search", vector_search_node)

    graph.set_entry_point("optimize_query")

    # Sequential: abilities must be found before filtering by keywords
    graph.add_edge("optimize_query", "search_abilities")
    graph.add_edge("search_abilities", "filter_cards")
    graph.add_edge("filter_cards", "prepare_vector_queries")

    graph.add_edge("prepare_vector_queries", "vector_search")
    graph.add_edge("vector_search", END)

    return graph.compile()


search_agent = build_graph()


async def run_search(query: str) -> list[dict]:
    """Run the search agent with a query."""
    result = await search_agent.ainvoke({
        "query": query,
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
    })
    return result["ranked_results"]
