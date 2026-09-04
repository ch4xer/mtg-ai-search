"""Select the function tags that most precisely express an AI-search intent."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm_provider import create_chat_llm, is_chat_provider_configured
from .llm_json import parse_llm_json_object

logger = logging.getLogger(__name__)

TAG_RERANK_PROMPT = (
    "You map Magic: The Gathering natural-language requests to Scryfall Tagger tags.\n"
    "Your objective is semantic equality: the selected tags must cover everything the user explicitly requested, and nothing broader.\n"
    "Pick only from the provided candidates. Never invent a tag. It is valid to select none when no candidate is sufficiently faithful.\n"
    "Treat each target slot as one atomic requirement. By default select exactly one best tag per target slot.\n"
    "Select multiple tags for one slot only when the original query explicitly requests alternatives and no single candidate covers those alternatives.\n"
    "Order selected tags by semantic fit, with the most exact match first.\n"
    "Preserve every explicit qualifier: actor/controller, affected player or object, event or timing, card type, zone, quantity, plurality, duration, restriction, polarity, and recurrence.\n"
    "A candidate that drops or weakens any qualifier is not an exact match. A related effect or shared word is not enough.\n"
    "Prefer the narrowest candidate that fully entails the requested meaning. Never select both a broad category and a more precise tag for the same requirement.\n"
    "For example, for an instant-or-sorcery cast/copy trigger, select magecraft and reject cast-trigger-you because the latter also admits unrelated spell types.\n"
    "Conversely, for a trigger on casting any spell, select cast-trigger-you and reject magecraft because magecraft is too narrow.\n"
    "Do not add tags merely to improve recall, provide related effects, or hedge uncertainty.\n"
    "For multiple target slots, cover every slot required by AND logic and preserve every alternative required by OR logic.\n"
    "Use each candidate's description, aliases, and retrieval phrases as its authoritative semantic context.\n"
    "Return JSON only in this shape: "
    '{"selected":[{"id":1,"reason":"short reason"}]}.'
)


@dataclass(frozen=True)
class TagSelection:
    matches: list[dict]
    used_llm: bool


def _strings(value: object, limit: int) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


def _candidate_line(index: int, candidate: dict) -> str:
    slot = candidate.get("target_slot") or "target"
    aliases = ", ".join(_strings(candidate.get("aliases"), 5)) or "none"
    phrases = "; ".join(_strings(candidate.get("retrieval_phrases"), 8)) or "none"
    description = " ".join(str(candidate.get("description") or "").split()) or "none"
    return (
        f'{index}. [slot: {slot}] [function] {candidate["tag"]} '
        f'(label: {candidate["label"]}; description: {description}; '
        f'aliases: {aliases}; retrieval phrases: {phrases}; '
        f'heuristic: {candidate["reason"]})'
    )


def _invoke_reranker(search_context: str, candidates: list[dict], limit: int) -> TagSelection:
    lines = [_candidate_line(index, candidate) for index, candidate in enumerate(candidates, start=1)]
    response = create_chat_llm(temperature=0).invoke(
        [
            SystemMessage(content=TAG_RERANK_PROMPT),
            HumanMessage(
                content=(
                    f"Search context:\n{search_context}\n"
                    f"Select up to {limit} tags.\n"
                    "Candidates:\n"
                    + "\n".join(lines)
                )
            ),
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)

    try:
        payload = parse_llm_json_object(content)
    except Exception:
        logger.warning("Failed to parse tag-selection LLM response: %s", content)
        return TagSelection(candidates[:limit], False)

    selected = payload.get("selected")
    if not isinstance(selected, list):
        logger.warning("Tag-selection LLM response omitted the selected list: %s", content)
        return TagSelection(candidates[:limit], False)
    if not selected:
        return TagSelection([], True)

    chosen: list[dict] = []
    seen: set[str] = set()
    for item in selected:
        if not isinstance(item, dict):
            continue
        candidate_id = item.get("id")
        if not isinstance(candidate_id, int) or not 1 <= candidate_id <= len(candidates):
            continue
        candidate = dict(candidates[candidate_id - 1])
        if candidate["tag"] in seen:
            continue
        seen.add(candidate["tag"])
        reason = str(item.get("reason") or "").strip()
        if reason:
            candidate["reason"] = reason
        chosen.append(candidate)

    if not chosen:
        return TagSelection(candidates[:limit], False)
    return TagSelection(chosen[:limit], True)


async def rerank_tags(search_context: str, candidates: list[dict], limit: int) -> TagSelection:
    """Return LLM-selected candidates, or the original ranking after an LLM failure."""
    if not candidates or not is_chat_provider_configured():
        return TagSelection(candidates[:limit], False)
    return await asyncio.to_thread(_invoke_reranker, search_context, candidates, limit)
