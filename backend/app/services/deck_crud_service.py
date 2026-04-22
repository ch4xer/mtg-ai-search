from fastapi import HTTPException

from ..repositories.decks import (
    add_card_to_deck,
    create_deck,
    delete_deck,
    get_deck_cards,
    get_user_decks,
    remove_card_from_deck,
    update_deck,
    update_deck_card_image,
)
from ..schemas.decks import AddCardRequest, CreateDeckRequest, UpdateCardImageRequest, UpdateDeckRequest
from .deck_access_service import require_deck_name, require_nonzero_quantity, require_owner, validate_format


async def list_user_decks(user_id: str) -> list[dict]:
    return await get_user_decks(user_id)


async def create_user_deck(user_id: str, req: CreateDeckRequest) -> dict:
    fmt = validate_format(req.format) or "undefined"
    return await create_deck(user_id, require_deck_name(req.name), fmt)


async def get_owned_deck_summary(deck_id: str, user_id: str) -> dict:
    await require_owner(deck_id, user_id)
    decks = await get_user_decks(user_id)
    deck = next((d for d in decks if d["id"] == deck_id), None)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


async def update_owned_deck(deck_id: str, user_id: str, req: UpdateDeckRequest) -> dict:
    await require_owner(deck_id, user_id)
    return await update_deck(deck_id, require_deck_name(req.name), validate_format(req.format))


async def delete_owned_deck(deck_id: str, user_id: str) -> None:
    await require_owner(deck_id, user_id)
    await delete_deck(deck_id)


async def list_owned_deck_cards(deck_id: str, user_id: str) -> list[dict]:
    await require_owner(deck_id, user_id)
    return await get_deck_cards(deck_id)


async def list_public_deck_cards(deck_id: str) -> list[dict]:
    from .deck_access_service import require_existing_deck

    await require_existing_deck(deck_id)
    return await get_deck_cards(deck_id)


async def add_owned_deck_card(deck_id: str, user_id: str, req: AddCardRequest) -> dict:
    await require_owner(deck_id, user_id)
    require_nonzero_quantity(req.quantity)
    update_image = "image_url" in req.model_fields_set or "display_url" in req.model_fields_set
    return await add_card_to_deck(
        deck_id,
        req.card_id,
        req.quantity,
        req.image_url,
        req.display_url,
        update_image,
        req.board,
        req.print_id,
    )


async def update_owned_deck_card_image(deck_id: str, card_id: str, user_id: str, req: UpdateCardImageRequest) -> dict:
    await require_owner(deck_id, user_id)
    updated = await update_deck_card_image(deck_id, card_id, req.image_url, req.display_url, req.board, req.print_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Card not in deck")
    return updated


async def remove_owned_deck_card(deck_id: str, card_id: str, user_id: str, board: str | None) -> None:
    await require_owner(deck_id, user_id)
    await remove_card_from_deck(deck_id, card_id, board)
