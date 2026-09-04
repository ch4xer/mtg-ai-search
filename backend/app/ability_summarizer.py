"""Summarize keyword abilities using the configured chat LLM provider.

Converts verbose rules text into concise one-sentence descriptions
for better embedding matching.
"""

import logging
import time

import httpx

from .llm_provider import get_chat_provider_config
from .services.llm_json import parse_llm_json_object

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RATE_LIMIT_DELAY = 0.5  # seconds between requests

ABILITY_SUMMARIZATION_PROMPT = (
    "You are a Magic: The Gathering rules expert and English/Chinese rules translator. "
    "Given a keyword ability name and its full English rules description, return its established Simplified Chinese name "
    "and a concise one-sentence explanation in both English and Simplified Chinese. Focus only on the core game effect. "
    "Do not mention rule numbers, reminder-text redundancy, or strategy. Use standard MTG terminology. "
    "Return ONLY a JSON object with exactly these string fields: "
    '{"name_zh":"", "description_en":"", "description_zh":""}.'
)


def summarize_ability_bilingual(name: str, description: str) -> dict[str, str] | None:
    """Use the configured chat provider to generate bilingual ability metadata.

    Returns None on failure.
    """
    config = get_chat_provider_config()
    if not config.api_key:
        logger.warning("Keyword ability summarization skipped: chat provider is not configured")
        return None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.post(
                f"{config.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.model,
                    "messages": [
                        {"role": "system", "content": ABILITY_SUMMARIZATION_PROMPT},
                        {"role": "user", "content": f"{name} - \"{description}\""},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 320,
                },
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = parse_llm_json_object(content)
            result = {
                "name_zh": str(parsed.get("name_zh") or "").strip(),
                "description_en": str(parsed.get("description_en") or "").strip(),
                "description_zh": str(parsed.get("description_zh") or "").strip(),
            }
            if not all(result.values()):
                raise ValueError("Bilingual ability summary is missing required fields")
            time.sleep(RATE_LIMIT_DELAY)
            return result
        except (httpx.RequestError, httpx.HTTPStatusError, KeyError, TypeError, ValueError) as e:
            if attempt == MAX_RETRIES:
                logger.error("Failed to summarize %s after %d attempts: %s", name, MAX_RETRIES, e)
                return None
            wait = attempt * 5
            logger.warning("Summarize API error (attempt %d/%d), retrying in %ds: %s", attempt, MAX_RETRIES, wait, e)
            time.sleep(wait)
    return None


def summarize_ability(name: str, description: str) -> str | None:
    """Backward-compatible English-only interface."""
    result = summarize_ability_bilingual(name, description)
    return result["description_en"] if result else None


def summarize_abilities_batch(abilities: dict[str, str], on_progress=None) -> dict[str, str]:
    """Summarize multiple abilities, returning {name: summary}.

    abilities: {name: original_description}
    on_progress: optional callback(done, total) called after each ability
    """
    summaries = {}
    total = len(abilities)

    for i, (name, desc) in enumerate(abilities.items(), 1):
        summary = summarize_ability(name, desc)
        if summary:
            summaries[name] = summary
            logger.info("[%d/%d] %s: %s", i, total, name, summary)
        else:
            # Fallback to original description truncated
            summaries[name] = desc[:200] if len(desc) > 200 else desc
            logger.warning("[%d/%d] %s: using fallback (original truncated)", i, total, name)

        if on_progress:
            on_progress(i, total)

    return summaries
