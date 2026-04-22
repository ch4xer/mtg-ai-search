from fastapi import HTTPException

from ..repositories.decks import get_deck

ALLOWED_FORMATS = {
    "undefined",
    "standard",
    "pioneer",
    "modern",
    "legacy",
    "vintage",
    "pauper",
    "commander",
    "brawl",
    "historic",
    "alchemy",
    "explorer",
    "oathbreaker",
    "premodern",
    "pauper commander",
    "paupercommander",
}


def require_deck_name(name: str) -> str:
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Deck name cannot be empty")
    return clean_name


def require_nonzero_quantity(quantity: int) -> None:
    if quantity == 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be zero")


def validate_format(raw: str | None) -> str | None:
    if raw is None:
        return None
    fmt = raw.strip().lower()
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format: {raw}")
    return fmt


async def require_owner(deck_id: str, user_id: str) -> dict:
    deck = await get_deck(deck_id)
    if not deck or deck["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


async def require_existing_deck(deck_id: str) -> dict:
    deck = await get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck
