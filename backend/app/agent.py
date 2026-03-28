from .vectorstore import search_abilities, search_cards
from .database import get_cards_by_ids
import json
import logging
import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


load_dotenv(os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), ".env"))

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key=DEEPSEEK_API_KEY,
    temperature=0.3,
)


class SearchState(TypedDict):
    query: str
    optimized_query: str
    extracted_colors: list[str]
    extracted_type: str
    extracted_name: str
    relevant_abilities: list[dict]
    card_description: str
    candidate_cards: list[dict]
    ranked_results: list[dict]


def optimize_query(state: SearchState) -> dict:
    """Use LLM to optimize query and extract structured card constraints."""
    response = llm.invoke([
        SystemMessage(content=(
            "You are a Magic: The Gathering expert. Given a user's card search query, "
            "extract structured information and generate an optimized ability search query.\n\n"
            "Return a JSON object with these fields:\n"
            "- \"optimized_query\": English query for ability vector search (focus on mechanics/effects)\n"
            "- \"colors\": array of color names (Black, Red, White, Blue, Green, Colorless) if specified\n"
            "- \"type\": card type if specified (Creature, Instant, Sorcery, Enchantment, Artifact, Land, etc.)\n"
            "- \"name\": exact card name if the user specified a specific card\n\n"
            "Example inputs and outputs:\n"
            "Input: \"能让对手弃牌的黑色生物\"\n"
            "Output: {\"optimized_query\": \"discard cards from opponent hand\", \"colors\": [\"Black\"], \"type\": \"Creature\", \"name\": \"\"}\n\n"
            "Input: \"red instant that deals damage\"\n"
            "Output: {\"optimized_query\": \"deal direct damage to target\", \"colors\": [\"Red\"], \"type\": \"Instant\", \"name\": \"\"}\n\n"
            "Input: \"Liliana of the Veil\"\n"
            "Output: {\"optimized_query\": \"\", \"colors\": [], \"type\": \"\", \"name\": \"Liliana of the Veil\"}\n\n"
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
    except (json.JSONDecodeError, TypeError):
        optimized = content if isinstance(content, str) else str(content)
        colors = []
        card_type = ""
        card_name = ""

    logger.info("<<< Optimized: %s, Colors: %s, Type: %s, Name: %s",
                optimized, colors, card_type, card_name)

    return {
        "optimized_query": optimized,
        "colors": colors,
        "type": card_type,
        "name": card_name,
    }


# Distance threshold for ability relevance (cosine distance, lower = more similar)
ABILITY_DISTANCE_THRESHOLD = 0.2


def search_abilities_node(state: SearchState) -> dict:
    """Search the ability vector DB using the optimized query, filtering by relevance."""
    query = state.get("optimized_query") or state["query"]
    abilities = search_abilities(query, n_results=5, distance_threshold=ABILITY_DISTANCE_THRESHOLD)

    for a in abilities:
        logger.info("  - %s (distance: %.3f)", a["name"], a["distance"])
    logger.info("<<< Found %d relevant abilities (threshold: %.2f)",
                len(abilities), ABILITY_DISTANCE_THRESHOLD)

    return {"abilities": abilities}


AVAILABLE_FIELDS = """\
Name: card name
Mana Cost: e.g. {2}{B}{B}
Mana Value: total mana value number
Type: e.g. Creature — Zombie Cat, Instant, Sorcery, Enchantment
Oracle Text: the card's rules text and effects
Colors: e.g. Black, Red, White, Blue, Green, Colorless (full English names)
Color Identity: color identity
Keywords: e.g. Flying, Deathtouch, Lifelink (comma separated)
Power/Toughness: e.g. 3/4
Loyalty: for planeswalkers
Defense: for battles
Produces Mana: colors of mana the card produces
Set: set name
Rarity: Common, Uncommon, Rare, Mythic
Flavor: flavor text
Layout: e.g. normal, transform, modal_dfc
Legal in: format names
Properties: e.g. Reserved List, Reprint, Promo"""


def generate_card_description(state: SearchState) -> dict:
    """Use DeepSeek to generate a structured card description matching the document format."""
    abilities = state["abilities"]
    has_abilities = len(abilities) > 0
    abilities_context = ",".join(a['name']
                                 for a in abilities) if has_abilities else ""

    optimized_query = state.get("optimized_query") or state["query"]
    colors = state.get("colors", [])
    card_type = state.get("type", "")
    card_name = state.get("name", "")
    has_name = bool(card_name)

    # Build constraints section
    constraints = []
    if card_name:
        constraints.append(f"Name: {card_name}")
    if colors:
        constraints.append(f"Colors: {', '.join(colors)}")
    if card_type:
        constraints.append(f"Type: {card_type}")
    constraints_text = "\n".join(
        constraints) if constraints else "No specific constraints."

    # 这块不应该是限定死的固定字段
    # Build available fields based on context
    fields = ["- Type: card type (e.g. Creature, Instant, Sorcery)",
              "- Colors: Black, Red, White, Blue, Green, Colorless",
              "- Oracle Text: rules text describing the card's effects"]
    if has_abilities:
        fields.append("- Keywords: comma-separated keyword abilities")
    if has_name:
        fields.append("- Name: exact card name for searching")
    fields.append("- Mana Cost: e.g. {2}{B}{B}")
    fields.append("- Power/Toughness: e.g. 3/4")
    fields_text = "\n".join(fields)

    logger.info(">>> Card description input — query: %s, colors: %s, type: %s, name: %s, abilities: %s",
                optimized_query, colors, card_type, card_name, abilities_context or "none")

    response = llm.invoke([
        SystemMessage(content=(
            "You are a Magic: The Gathering expert. Generate a HYPOTHETICAL card description "
            "for vector search to find matching cards.\n\n"
            f"Extracted constraints (MUST include these):\n{constraints_text}\n\n"
            f"Effect description: {optimized_query}\n\n"
            f"Relevant keyword abilities: {abilities_context or 'none found'}\n\n"
            f"Available fields (use EXACT format 'FieldName: value'):\n{fields_text}\n\n"
            "Rules:\n"
            "- MUST include the extracted constraints exactly as provided\n"
            "- Oracle Text should describe the expected effects using natural language\n"
            "- Do NOT use 'CARDNAME' placeholder — describe the effect directly\n"
            "- Include Keywords field ONLY if keyword abilities were found\n"
            "- Include Name field ONLY if a specific card name was provided\n"
            "- Do NOT include irrelevant fields (Rarity, Set, Flavor, Legal in, etc.)\n"
            "- Do NOT invent card names\n"
            "- Use English for all field values\n"
            "- Return ONLY the structured text, no extra explanation"
        )),
        HumanMessage(content="Generate the card description."),
    ])

    logger.info("<<< DeepSeek card description:\n%s", response.content)
    return {"description": response.content}


def search_cards_node(state: SearchState) -> dict:
    """Search the card vector DB, then retrieve full data from SQLite."""
    results = search_cards(state["description"], n_results=20)

    card_ids = []
    if results and results["ids"] and results["ids"][0]:
        card_ids = results["ids"][0]

    # Retrieve full card data from SQLite
    candidates = get_cards_by_ids(card_ids)

    return {"candidate_cards": candidates}


def _card_summary(card: dict) -> str:
    """Build a concise summary of a card for LLM ranking."""
    parts = [f"Name: {card.get('name', '')}"]
    if card.get("mana_cost"):
        parts.append(f"Mana: {card['mana_cost']}")
    parts.append(f"Type: {card.get('type_line', '')}")
    if card.get("oracle_text"):
        parts.append(f"Text: {card['oracle_text']}")
    if card.get("keywords"):
        parts.append(f"Keywords: {', '.join(card['keywords'])}")
    if card.get("power") and card.get("toughness"):
        parts.append(f"P/T: {card['power']}/{card['toughness']}")
    if card.get("colors"):
        parts.append(f"Colors: {', '.join(card['colors'])}")
    return "\n".join(parts)


def rank_results(state: SearchState) -> dict:
    """Use DeepSeek to rank the candidate cards by relevance."""
    if not state["candidate_cards"]:
        return {"ranked_results": []}

    cards_text = "\n\n".join(
        f"Card {i + 1}:\n{_card_summary(c)}"
        for i, c in enumerate(state["candidate_cards"])
    )

    response = llm.invoke([
        SystemMessage(content=(
            f'You are a Magic: The Gathering expert. The user searched for cards with '
            f'this query: "{state["query"]}"\n\n'
            f"Here are the candidate cards found:\n\n{cards_text}\n\n"
            "Rank these cards by relevance to the user's query. Return a JSON array of "
            "card indices (1-based) in order of relevance, most relevant first. "
            "Include only the top 10 most relevant cards.\n\n"
            "Return ONLY a JSON array of numbers, like [3, 1, 7, 2, ...]. Nothing else."
        )),
        HumanMessage(content="Please rank the cards."),
    ])

    try:
        indices = json.loads(response.content)
        ranked = []
        seen = set()
        for idx in indices:
            if isinstance(idx, int) and 1 <= idx <= len(state["candidate_cards"]):
                if idx not in seen:
                    seen.add(idx)
                    ranked.append(state["candidate_cards"][idx - 1])
        return {"ranked_results": ranked if ranked else state["candidate_cards"][:10]}
    except (json.JSONDecodeError, TypeError):
        return {"ranked_results": state["candidate_cards"][:10]}


def build_graph():
    graph = StateGraph(SearchState)

    graph.add_node("optimize_ability_query", optimize_query)
    graph.add_node("search_abilities", search_abilities_node)
    graph.add_node("generate_card_description", generate_card_description)
    graph.add_node("search_cards", search_cards_node)
    graph.add_node("rank_results", rank_results)

    graph.set_entry_point("optimize_ability_query")
    graph.add_edge("optimize_ability_query", "search_abilities")
    graph.add_edge("search_abilities", "generate_card_description")
    graph.add_edge("generate_card_description", "search_cards")
    graph.add_edge("search_cards", "rank_results")
    graph.add_edge("rank_results", END)

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
        "abilities": [],
        "description": "",
        "candidate_cards": [],
        "ranked_results": [],
    })
    return result["ranked_results"]
