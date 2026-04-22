from fastapi import HTTPException

from ..repositories.decks import get_deck_cards_for_export


async def build_decklist_text(deck_id: str) -> str:
    cards = await get_deck_cards_for_export(deck_id)
    if not cards:
        raise HTTPException(status_code=400, detail="Deck is empty")

    main_lines = [f"{c['quantity']} {c['name']}" for c in cards if c["board"] == "mainboard"]
    side_lines = [f"{c['quantity']} {c['name']}" for c in cards if c["board"] == "sideboard"]
    lines = main_lines
    if side_lines:
        lines += ["", "SIDEBOARD"] + side_lines
    return "\n".join(lines) + "\n"
