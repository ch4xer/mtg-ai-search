from fastapi import HTTPException

from ..repositories.cards import get_card_by_oracle_id
from ..repositories.decks import get_deck, get_deck_cards

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

SINGLETON_FORMATS = {"commander", "brawl", "oathbreaker", "paupercommander", "pauper commander"}
SPECIAL_COPY_LIMITS: tuple[tuple[str, int | None], ...] = (
    ("up to seven cards named", 7),
    ("up to nine cards named", 9),
    ("any number of cards named", None),
)


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


def _is_basic_land(card: dict) -> bool:
    return "Basic" in (card.get("type_line") or "")


def _get_special_copy_limit(card: dict) -> int | None:
    text = (card.get("oracle_text") or "").lower()
    for needle, limit in SPECIAL_COPY_LIMITS:
        if needle in text:
            return limit
    return None


def _get_copy_limit(card: dict, format_key: str, legality: str) -> int | None:
    if not format_key or format_key == "undefined":
        return None
    if _is_basic_land(card):
        return None

    special_limit = _get_special_copy_limit(card)
    if special_limit is not None or "any number of cards named" in (card.get("oracle_text") or "").lower():
        return special_limit

    if legality == "restricted":
        return 1
    if format_key in SINGLETON_FORMATS:
        return 1
    return 4


async def require_copy_limit(deck_id: str, card_id: str, quantity_delta: int) -> None:
    if quantity_delta <= 0:
        return

    deck = await require_existing_deck(deck_id)
    format_key = deck.get("format") or "undefined"
    if format_key == "undefined":
        return

    deck_cards = await get_deck_cards(deck_id)
    existing_total = sum(item["quantity"] for item in deck_cards if item["card_id"] == card_id)
    target_card = next((item["card"] for item in deck_cards if item["card_id"] == card_id), None)
    if target_card is None:
        target_card = await get_card_by_oracle_id(card_id)
    if target_card is None:
        return

    legalities = target_card.get("legalities") or {}
    legality = (legalities.get(format_key) or "").lower()
    limit = _get_copy_limit(target_card, format_key, legality)
    if limit is None:
        return

    if existing_total + quantity_delta > limit:
        raise HTTPException(
            status_code=400,
            detail=f"{target_card.get('name') or 'Card'} has reached the copy limit ({limit})",
        )
