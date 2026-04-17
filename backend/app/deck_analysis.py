"""Generate a bilingual (zh + en) strategy write-up for a deck using Deepseek.

A single Deepseek call returns a JSON object keyed by language. The model is
forced to return valid JSON via `response_format={"type": "json_object"}`.
"""

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from .agent import llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a seasoned Magic: The Gathering player and coach. The user will give "
    "you a decklist where each entry includes the card name, type line, mana cost, "
    "oracle text and quantity. Read the whole deck and analyse its overall strategy, "
    "core gameplan, curve, key interactions, and typical weaknesses.\n\n"
    "Return STRICTLY a JSON object with this exact shape and no extra text:\n"
    "{\n"
    '  "zh": {\n'
    '    "deck_summary": "一两句话概括这个卡组的核心玩法风格",\n'
    '    "playstyle": "详细的对战思路和核心打法，包含关键连锁/节奏建议，200 字以内",\n'
    '    "weaknesses": "这个卡组的主要弱点和容易被针对的地方，以及实战时需要注意的关键点"\n'
    "  },\n"
    '  "en": {\n'
    '    "deck_summary": "one or two sentences summarising the deck\'s core playstyle",\n'
    '    "playstyle": "detailed gameplan and piloting advice, under 200 words",\n'
    '    "weaknesses": "the deck\'s main weaknesses and what opponents can exploit"\n'
    "  }\n"
    "}\n\n"
    "The `zh` fields MUST be in 简体中文 and the `en` fields MUST be in English. "
    "Both language versions should describe the same deck faithfully — they are "
    "translations of the same analysis, not independently generated takes. "
    "Return the JSON object only — no Markdown fences, no prose."
)


def _format_card_line(card: dict) -> str:
    # Quantity-prefixed card line used in the LLM payload. Keep `\n` inside
    # oracle_text as a single space so each card stays on one line.
    oracle = (card.get("oracle_text") or "").replace("\n", " ").strip()
    parts = [f"{card['quantity']}x {card['name']}"]
    if card.get("type_line"):
        parts.append(card["type_line"])
    if card.get("mana_cost"):
        parts.append(card["mana_cost"])
    if oracle:
        parts.append(oracle)
    return " — ".join(parts)


def build_deck_payload(deck_name: str, deck_format: str, cards: list[dict]) -> str:
    mainboard = [c for c in cards if c.get("board") != "sideboard"]
    sideboard = [c for c in cards if c.get("board") == "sideboard"]

    lines = [f"Deck: {deck_name}    Format: {deck_format}", "", "MAINBOARD"]
    lines.extend(_format_card_line(c) for c in mainboard)
    if sideboard:
        lines.append("")
        lines.append("SIDEBOARD")
        lines.extend(_format_card_line(c) for c in sideboard)
    return "\n".join(lines)


def _extract_language_block(data: dict, lang: str) -> dict:
    block = data.get(lang) or {}
    summary = (block.get("deck_summary") or "").strip()
    playstyle = (block.get("playstyle") or "").strip()
    weaknesses = (block.get("weaknesses") or "").strip()
    if not (summary and playstyle and weaknesses):
        raise ValueError(f"Deepseek response missing required fields for '{lang}'")
    return {"summary": summary, "playstyle": playstyle, "weaknesses": weaknesses}


async def analyze_deck(deck_name: str, deck_format: str, cards: list[dict]) -> dict:
    """Call Deepseek once and return {"zh": {...}, "en": {...}}.

    Raises ValueError if the response cannot be parsed into the expected shape.
    """
    payload = build_deck_payload(deck_name, deck_format, cards)

    bound = llm.bind(response_format={"type": "json_object"})
    response = await bound.ainvoke(
        [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=payload)]
    )

    raw = response.content if isinstance(response.content, str) else str(response.content)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Deepseek returned non-JSON for deck analysis: %s", raw[:500])
        raise ValueError("Deepseek returned non-JSON content") from exc

    return {
        "zh": _extract_language_block(data, "zh"),
        "en": _extract_language_block(data, "en"),
    }
