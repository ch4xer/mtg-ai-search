"""Summarize keyword abilities using DeepSeek LLM.

Converts verbose rules text into concise one-sentence descriptions
for better embedding matching.
"""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 0.5  # seconds between requests

SYSTEM_PROMPT = (
    "You are a Magic: The Gathering rules expert. Given a keyword ability name and its full rules description, "
    "write a concise one-sentence summary focusing on the core game effect. "
    "Do NOT mention rule numbers or redundancy notes. "
    "Use simple MTG terms a player would search for.\n\n"
    "Examples:\n"
    'Input: Lifelink - "Lifelink is a static ability. Damage dealt by a source with lifelink causes that source\'s controller to gain that much life..."\n'
    'Output: Damage dealt by this creature also causes its controller to gain that much life.\n\n'
    'Input: Annihilator - "Annihilator is a triggered ability. "Annihilator N" means "Whenever this creature attacks, defending player sacrifices N permanents."..."\n'
    'Output: Whenever this creature attacks, defending player sacrifices permanents.\n\n'
    'Input: Flying - "Flying is an evasion ability. A creature with flying can\'t be blocked except by creatures with flying or reach..."\n'
    'Output: This creature can only be blocked by creatures with flying or reach.\n\n'
    "Return ONLY the summary sentence, nothing else."
)


def summarize_ability(name: str, description: str) -> str | None:
    """Use DeepSeek to generate a concise summary of an ability.

    Returns None on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"{name} - \"{description}\""},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 150,
                },
                timeout=30,
            )
            resp.raise_for_status()
            summary = resp.json()["choices"][0]["message"]["content"].strip()
            time.sleep(RATE_LIMIT_DELAY)
            return summary
        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.HTTPStatusError) as e:
            if attempt == MAX_RETRIES:
                logger.error("Failed to summarize %s after %d attempts: %s", name, MAX_RETRIES, e)
                return None
            wait = attempt * 5
            logger.warning("Summarize API error (attempt %d/%d), retrying in %ds: %s", attempt, MAX_RETRIES, wait, e)
            time.sleep(wait)
    return None


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