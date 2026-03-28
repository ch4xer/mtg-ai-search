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

ABILITY_DISTANCE_THRESHOLD = 0.2
RRF_K = 60


class SearchState(TypedDict):
    query: str
    optimized_query: str
    colors: list[str]
    type: str
    name: str
    filters: dict
    filtered_card_ids: list[str]
    abilities: list[dict]
    vector_queries: dict
    ranked_results: list[dict]


# ── Node 1: optimize_query ──────────────────────────────────────────────

def optimize_query(state: SearchState) -> dict:
    """Use LLM to optimize query and extract structured card constraints."""
    response = llm.invoke([
        SystemMessage(content=(
            "You are a Magic: The Gathering expert. Given a user's card search query, "
            "extract structured information and generate an optimized ability search query.\n\n"
            "Return a JSON object with these fields:\n"
            '- "optimized_query": English query for ability vector search (focus on mechanics/effects)\n'
            '- "colors": array of color codes (W, U, B, R, G) if specified\n'
            '- "type": card type if specified (Creature, Instant, Sorcery, Enchantment, Artifact, Land, etc.)\n'
            '- "name": exact card name if the user specified a specific card\n'
            '- "filters": object with optional keys: released_at, layout, mana_cost, cmc, power, toughness, colors.\n'
            '  - For non-enumerable fields (cmc, power, toughness, released_at, mana_cost), use condition expressions like ">5", ">=2020-01-01"\n'
            '  - For enumerable fields (colors, layout), use exact values like "B R", "transform"\n'
            '  - Use null for fields not mentioned in the query\n\n'
            "Examples:\n"
            'Input: "能让对手弃牌的黑色生物"\n'
            'Output: {"optimized_query": "discard cards from opponent hand", "colors": ["B"], "type": "Creature", "name": "", '
            '"filters": {"colors": "B", "released_at": null, "layout": null, "mana_cost": null, "cmc": null, "power": null, "toughness": null}}\n\n'
            'Input: "red instant that deals damage with cmc less than 3"\n'
            'Output: {"optimized_query": "deal direct damage to target", "colors": ["R"], "type": "Instant", "name": "", '
            '"filters": {"colors": "R", "cmc": "<3", "released_at": null, "layout": null, "mana_cost": null, "power": null, "toughness": null}}\n\n'
            'Input: "creatures with power greater than 10 released after 2020"\n'
            'Output: {"optimized_query": "powerful creature", "colors": [], "type": "Creature", "name": "", '
            '"filters": {"power": ">10", "released_at": ">2020-01-01", "colors": null, "layout": null, "mana_cost": null, "cmc": null, "toughness": null}}\n\n'
            'Input: "Liliana of the Veil"\n'
            'Output: {"optimized_query": "", "colors": [], "type": "", "name": "Liliana of the Veil", '
            '"filters": {"colors": null, "released_at": null, "layout": null, "mana_cost": null, "cmc": null, "power": null, "toughness": null}}\n\n'
            "Return ONLY the JSON object, nothing else."
        )),
        HumanMessage(content=state["query"]),
    ])

    content = response.content
    if isinstance(content, str):
        content = content.strip()

    logger.info(">>> Original query: %s", state["query"])

    try:
        data = json.loads(content)
        optimized = data.get("optimized_query", state["query"])
        colors = data.get("colors", [])
        card_type = data.get("type", "")
        card_name = data.get("name", "")
        filters = data.get("filters", {})
        # Clean null values from filters
        filters = {k: v for k, v in filters.items() if v is not None}
    except (json.JSONDecodeError, TypeError):
        optimized = content if isinstance(content, str) else str(content)
        colors = []
        card_type = ""
        card_name = ""
        filters = {}

    logger.info("<<< Optimized: %s, Colors: %s, Type: %s, Name: %s, Filters: %s",
                optimized, colors, card_type, card_name, filters)

    return {
        "optimized_query": optimized,
        "colors": colors,
        "type": card_type,
        "name": card_name,
        "filters": filters,
    }


# ── Node 2a: filter_cards_node (parallel) ───────────────────────────────

async def filter_cards_node(state: SearchState) -> dict:
    """Filter cards by structured conditions from optimize_query."""
    filters = state.get("filters", {})
    if not filters:
        logger.info("<<< No filters, skipping structured filtering")
        return {"filtered_card_ids": []}

    card_ids = await filter_cards(filters)
    logger.info("<<< Filtered to %d cards", len(card_ids))
    return {"filtered_card_ids": card_ids}


# ── Node 2b: search_abilities_node (parallel) ───────────────────────────

async def search_abilities_node(state: SearchState) -> dict:
    """Search keyword abilities by vector similarity."""
    query = state.get("optimized_query") or state["query"]
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
    """Prepare vector query texts for 3-way search."""
    optimized = state.get("optimized_query") or state["query"]
    abilities = state.get("abilities", [])
    card_name = state.get("name", "")
    card_type = state.get("type", "")

    queries = {}

    # name query: only if a specific card name was given
    if card_name:
        queries["name"] = card_name

    # type_line query: only if a card type was specified
    if card_type:
        queries["type_line"] = card_type

    # oracle_text query: always present, combine with abilities
    oracle_parts = [optimized] if optimized else []
    for a in abilities:
        oracle_parts.append(a["name"])
    queries["oracle_text"] = " ".join(oracle_parts) if oracle_parts else ""

    logger.info("<<< Vector queries: %s", queries)
    return {"vector_queries": queries}


# ── Node 4: vector_search_node ───────────────────────────────────────────

async def vector_search_node(state: SearchState) -> dict:
    """3-way vector search with RRF fusion."""
    queries = state.get("vector_queries", {})
    filtered_ids = state.get("filtered_card_ids", [])
    card_ids_filter = filtered_ids if filtered_ids else None

    # Map query keys to embedding column names
    column_map = {
        "name": "name_embedding",
        "type_line": "type_line_embedding",
        "oracle_text": "oracle_text_embedding",
    }

    # Run each vector search
    rankings: dict[str, list[str]] = {}
    for key, text in queries.items():
        if not text:
            continue
        col = column_map[key]
        query_vec = encode([text])[0]
        results = await vector_search_cards(col, query_vec, n_results=20, card_ids=card_ids_filter)
        rankings[key] = [r[0] for r in results]  # list of card IDs in rank order
        logger.info("  Vector search [%s]: %d results", key, len(results))

    # RRF fusion
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings.values():
        for rank, card_id in enumerate(ranking, start=1):
            scores[card_id] += 1.0 / (RRF_K + rank)

    # Sort by RRF score descending, take top 10
    top_ids = sorted(scores, key=lambda card_id: scores[card_id], reverse=True)[:10]

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

    # Fan out: optimize_query -> [filter_cards, search_abilities] in parallel
    graph.add_edge("optimize_query", "filter_cards")
    graph.add_edge("optimize_query", "search_abilities")

    # Fan in: both -> prepare_vector_queries
    graph.add_edge("filter_cards", "prepare_vector_queries")
    graph.add_edge("search_abilities", "prepare_vector_queries")

    graph.add_edge("prepare_vector_queries", "vector_search")
    graph.add_edge("vector_search", END)

    return graph.compile()


search_agent = build_graph()


async def run_search(query: str) -> list[dict]:
    """Run the search agent with a query."""
    result = await search_agent.ainvoke({
        "query": query,
        "optimized_query": "",
        "colors": [],
        "type": "",
        "name": "",
        "filters": {},
        "filtered_card_ids": [],
        "abilities": [],
        "vector_queries": {},
        "ranked_results": [],
    })
    return result["ranked_results"]
