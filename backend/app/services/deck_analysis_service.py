import logging

from fastapi import HTTPException

from ..deck_analysis import analyze_deck
from ..llm_provider import is_chat_provider_configured
from ..repositories.decks import get_deck_cards_for_analysis, update_deck_analysis
from .deck_access_service import require_owner

logger = logging.getLogger(__name__)


async def analyze_owned_deck(deck_id: str, user_id: str) -> dict:
    if not is_chat_provider_configured():
        raise HTTPException(status_code=503, detail="DeepSeek API key not configured")

    deck = await require_owner(deck_id, user_id)
    cards = await get_deck_cards_for_analysis(deck_id)
    mainboard = [c for c in cards if c.get("board") != "sideboard"]
    if not mainboard:
        raise HTTPException(status_code=400, detail="Deck is empty")

    try:
        analysis = await analyze_deck(deck["name"], deck.get("format", "undefined"), mainboard)
    except ValueError as exc:
        logger.warning("Deck analysis failed for %s: %s", deck_id, exc)
        raise HTTPException(status_code=502, detail="Analysis failed, please try again") from exc
    except Exception as exc:
        logger.exception("Deck analysis error for %s", deck_id)
        raise HTTPException(status_code=502, detail="Analysis failed, please try again") from exc

    return await update_deck_analysis(deck_id, analysis)
