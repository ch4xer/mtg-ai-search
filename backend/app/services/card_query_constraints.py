"""Structured card-search constraint extraction shared by tag search."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm_provider import create_chat_llm

logger = logging.getLogger(__name__)

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
    "Strict meaning preservation rules:\n"
    "- Do not weaken, broaden, summarize away, or normalize away gameplay qualifiers from the original request.\n"
    "- Preserve actor, target, quantity, plurality, frequency, repeatability, duration, trigger condition, zone, timing, and restrictions in oracle_text.\n"
    "- A repeated/recurring/repeatable/each-turn/whenever effect is materially different from a one-shot effect. Never rewrite it as a one-shot effect.\n"
    "- If the user has a typo such as repeatly, infer the intended word repeatedly but keep the repeated/repeatable meaning.\n"
    "- If unsure whether a qualifier matters, keep it in oracle_text.\n"
    "Be faithful to the original wording. Do not add unstated constraints.\n"
    "Do not map a localized/translated title to a different known card by guesswork.\n"
    'Example full: "2020年后的红蓝双面传奇龙，法术力值小于5，力量大于3，能抓牌" -> '
    '{"oracle_text":"draw cards","name":"","type":"Legendary Creature Dragon","colors":"U R","released_at":">2020-01-01",'
    '"layout":"transform","mana_cost":"","cmc":"<5","power":">3","toughness":""}\n'
    'Example discard: "能让对手弃牌的黑色生物" -> '
    '{"oracle_text":"target opponent discards a card","name":"","type":"Creature","colors":"B","released_at":"","layout":"","mana_cost":"","cmc":"","power":"","toughness":""}\n'
    'Example repeatable tag effect: "blue creatures that repeatly create token and discards opponent card" -> '
    '{"oracle_text":"repeatedly create tokens and target opponent discards a card","name":"","type":"Creature","colors":"U","released_at":"","layout":"","mana_cost":"","cmc":"","power":"","toughness":""}\n'
    'Example faithful typing: "奥扎奇泰坦" -> '
    '{"oracle_text":"","name":"Titan","type":"Creature Eldrazi","colors":"","released_at":"","layout":"","mana_cost":"","cmc":"","power":"","toughness":""}'
)


def _extract_json(text: str) -> dict:
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


def extract_card_search_constraints(query: str) -> tuple[dict[str, str], int, int]:
    """Extract structured card filters and effect text without invoking old AI Search."""
    llm = create_chat_llm(temperature=0.3)
    response = llm.invoke(
        [
            SystemMessage(content=QUERY_OPTIMIZER_PROMPT),
            HumanMessage(content=query),
        ]
    )
    tokens_prompt, tokens_completion = _get_token_usage(response)

    content = response.content
    if isinstance(content, str):
        content = content.strip()

    logger.info(">>> Original query: %s", query)
    logger.info(">>> Token usage: prompt=%d, completion=%d", tokens_prompt, tokens_completion)

    result = _parse_optimizer_response(content)
    return result, tokens_prompt, tokens_completion


def build_structured_card_filters(constraints: dict) -> dict:
    return {key: constraints[key] for key in FILTER_KEYS if constraints.get(key)}
