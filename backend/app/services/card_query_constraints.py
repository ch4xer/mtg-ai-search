"""Structured card-search constraint extraction shared by tag search."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm_provider import create_chat_llm
from .llm_json import parse_llm_json_object

logger = logging.getLogger(__name__)

FILTER_KEYS = (
    "colors",
    "excluded_colors",
    "type",
    "released_at",
    "layout",
    "cmc",
    "power",
    "toughness",
)

CONSTRAINT_EXTRACTION_PROMPT = (
    "Create a MTG AI Search plan.\n\n"
    "Return ONLY a sparse JSON object using these allowed keys:\n"
    "type,colors,excluded_colors,released_at,layout,cmc,power,toughness,"
    "targets,logic\n"
    "Omit every unspecified key. Do not return empty strings, empty arrays, or null values.\n\n"
    "Field rules:\n"
    "- type: supertypes/types/subtypes, space-separated, e.g. Legendary Creature Dragon.\n"
    "- colors: actual card colors W U B R G C.\n"
    "- released_at: date condition like >2020-01-01.\n"
    "- layout: layout word like transform, modal_dfc, adventure.\n"
    "- cmc,power,toughness: numeric conditions using >,>=,<,<=,=.\n\n"
    "Structured-filter scope rules:\n"
    "- A structured filter describes a printed property of the cards the user wants returned, never a property of another card, spell, permanent, target, cost, or trigger event mentioned in rules text.\n"
    "- Set type only when the user directly restricts the desired result cards to a supertype, card type, creature type, planeswalker type, or subtype.\n"
    "- Card types mentioned inside an effect or trigger condition stay in a target intent and must not become result-card type filters.\n"
    "- Apply the same scope rule to colors, mana value, power, toughness, layout, and release date.\n"
    "- Do not repeat the same semantic constraint in both a structured field and a target.\n"
    "- Example: 'find red creatures that trigger when I cast an instant or sorcery' uses type='Creature' and colors='R'; instant and sorcery belong only in the trigger target.\n"
    "- Example: '每当施放瞬间或法术咒语时触发效果' has no type filter; preserve Instant and Sorcery in one cast-trigger target.\n"
    "- Example: '每当施放红色咒语时触发' has no colors filter; red modifies the spell being cast, not the result card.\n\n"
    "Color DSL:\n"
    "- 'R W': all listed colors are required.\n"
    "- 'any:R W': any listed color is allowed.\n"
    "- '=R W': exactly those colors only.\n\n"
    "Color rules:\n"
    "- Use color symbols only when explicitly mentioned; never infer colors from type, lore, or faction.\n"
    "- Convert named color groups such as Boros, Esper, Sultai, 艾斯波, or 苏勒台 to symbols.\n"
    "- and / A-B / 红白色 / 红色和白色 -> 'R W'; or / either / 红色或白色 / 任一红白色 -> 'any:R W'; exactly / only / 正好 / 仅 / 只有 -> '=R W'.\n"
    "- not / excluding / 不含 / 不包括 / 排除 -> excluded_colors, e.g. excluded_colors='R W'.\n\n"
    "Meaning preservation rules:\n"
    "- Each atomic target must independently preserve the explicit gameplay qualifiers that apply to it: actor, target, quantity, plurality, zone, timing, trigger condition, duration, restrictions, and recurrence.\n"
    "- When splitting into atomic targets, repeat shared qualifiers (e.g. actor) in every target they apply to. Repetition is expected and correct.\n"
    "- Do not convert recurring/repeatable/each-turn/whenever effects into one-shot effects.\n"
    "- Correct obvious typos only when the intended gameplay meaning is clear; keep the original qualifier's meaning.\n"
    "- Do not add inferred constraints, card names, targets, colors, timing, or restrictions that the user did not state.\n"
    "- If unsure whether a qualifier matters, keep it in a target intent instead of dropping it.\n\n"
    "Card title rules:\n"
    "- AI Search does not search by card name. Ignore card titles completely.\n"
    "- Do not put card titles in targets or filters.\n"
    "- If the query is only a card title with no gameplay intent, return {}.\n\n"
    "Tag retrieval rules:\n"
    "- If no gameplay effect is requested, omit targets and logic.\n"
    "- targets is an array of focused functional retrieval goals; each target has slot and intent.\n"
    "- slot must be a concise, stable English snake_case name for the canonical mechanic or effect, such as lifelink, opponent_discard, or draw_cards.\n"
    "- Create multiple targets when the user asks for multiple gameplay concepts.\n"
    "- Each target must describe exactly ONE atomic gameplay effect. Never merge multiple effects into one target.\n"
    "- Split conjunctive phrases like 'does A and B' into two separate targets, one per effect, even when they share the same actor, subject, or target.\n"
    "- logic is required only when there are multiple targets; omit it for zero or one target.\n"
    "- logic is a Boolean tree preserving the user's relationship between targets.\n"
    "- logic operator nodes use {'op':'and'|'or','children':[...]}.\n"
    "- logic children are target slot strings or nested operator nodes.\n"
    "- Use and when all concepts must be true. Use or when any alternative effect may satisfy the user.\n\n"
    "Examples:\n"
    '- "能让对手弃牌并失去生命值的黑色生物" -> '
    '{"type":"Creature","colors":"B",'
    '"targets":[{"slot":"opponent_discard","intent":"Target opponent discards a card."},'
    '{"slot":"opponent_life_loss","intent":"Target opponent loses life."}],'
    '"logic":{"op":"and","children":["opponent_discard","opponent_life_loss"]}}\n'
    '- "必须包含弃牌和烧血，或者必须包含回血和抽卡" -> '
    '{"targets":[{"slot":"discard","intent":"Discard a card."},{"slot":"damage_opponent","intent":"Deal damage or cause life loss."},'
    '{"slot":"gain_life","intent":"Gain life."},{"slot":"draw_cards","intent":"Draw cards."}],'
    '"logic":{"op":"or","children":[{"op":"and","children":["discard","damage_opponent"]},{"op":"and","children":["gain_life","draw_cards"]}]}}\n'
    '- "2020年后的红蓝龙，法术力值小于5" -> '
    '{"type":"Creature Dragon","colors":"U R","released_at":">2020-01-01","cmc":"<5"}\n'
    '- "红色或白色生物，排除黑色" -> '
    '{"type":"Creature","colors":"any:R W","excluded_colors":"B"}'
)


def _get_token_usage(response) -> tuple[int, int]:
    usage = getattr(response, "usage_metadata", None) or {}
    if isinstance(usage, dict):
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    return getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0)


def _has_plan_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _parse_optimizer_response(content: str) -> dict:
    try:
        data = parse_llm_json_object(content)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse LLM response as JSON: %s", content)
        data = {}

    result = {
        key: data[key]
        for key in FILTER_KEYS
        if key in data and _has_plan_value(data.get(key))
    }
    if isinstance(data.get("targets"), list) and data["targets"]:
        result["targets"] = data["targets"]
    if isinstance(data.get("logic"), dict) and data["logic"]:
        result["logic"] = data["logic"]
    return result


def extract_card_search_constraints(query: str) -> tuple[dict, int, int]:
    """Extract structured card filters and effect text without invoking old AI Search."""
    llm = create_chat_llm(temperature=0)
    response = llm.invoke(
        [
            SystemMessage(content=CONSTRAINT_EXTRACTION_PROMPT),
            HumanMessage(content=query),
        ]
    )
    tokens_prompt, tokens_completion = _get_token_usage(response)

    content = response.content
    if isinstance(content, str):
        content = content.strip()

    logger.debug("Card constraint query: %s", query)
    logger.debug(
        "Card constraint token usage: prompt=%d, completion=%d",
        tokens_prompt,
        tokens_completion,
    )

    result = _parse_optimizer_response(content)
    return result, tokens_prompt, tokens_completion


def build_structured_card_filters(constraints: dict) -> dict:
    return {key: constraints[key] for key in FILTER_KEYS if constraints.get(key)}
