"""Deck HTTP endpoints."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from .auth import get_current_user
from .schemas.decks import (
    AddCardRequest,
    CreateDeckRequest,
    ImportDeckRequest,
    UpdateCardImageRequest,
    UpdateDeckRequest,
)
from .services.deck_export_service import (
    build_attachment_headers,
    build_export_download_response,
    pop_image_export,
    pop_pdf_export,
    stream_image_export,
    stream_pdf_export,
)
from .services.deck_access_service import require_existing_deck, require_owner
from .services.deck_analysis_service import analyze_owned_deck
from .services.deck_crud_service import (
    add_owned_deck_card,
    create_user_deck,
    delete_owned_deck,
    get_owned_deck_summary,
    list_owned_deck_cards,
    list_public_deck_cards,
    list_user_decks,
    remove_owned_deck_card,
    update_owned_deck,
    update_owned_deck_card_image,
)
from .services.deck_import_service import import_owned_deck
from .services.deck_text_export_service import build_decklist_text

deck_router = APIRouter(prefix="/api/decks", tags=["decks"])
shared_deck_router = APIRouter(prefix="/api/shared/decks", tags=["shared-decks"])


@deck_router.get("")
async def list_decks(user_id: str = Depends(get_current_user)):
    return await list_user_decks(user_id)


@deck_router.post("", status_code=201)
async def create_deck_endpoint(req: CreateDeckRequest, user_id: str = Depends(get_current_user)):
    return await create_user_deck(user_id, req)


@deck_router.get("/{deck_id}")
async def get_deck_endpoint(deck_id: str, user_id: str = Depends(get_current_user)):
    return await get_owned_deck_summary(deck_id, user_id)


@deck_router.put("/{deck_id}")
async def update_deck_endpoint(deck_id: str, req: UpdateDeckRequest, user_id: str = Depends(get_current_user)):
    return await update_owned_deck(deck_id, user_id, req)


@deck_router.delete("/{deck_id}", status_code=204)
async def delete_deck_endpoint(deck_id: str, user_id: str = Depends(get_current_user)):
    await delete_owned_deck(deck_id, user_id)


@deck_router.get("/{deck_id}/cards")
async def list_deck_cards(deck_id: str, user_id: str = Depends(get_current_user)):
    return await list_owned_deck_cards(deck_id, user_id)


@deck_router.post("/{deck_id}/cards", status_code=201)
async def add_card(deck_id: str, req: AddCardRequest, user_id: str = Depends(get_current_user)):
    return await add_owned_deck_card(deck_id, user_id, req)


@deck_router.patch("/{deck_id}/cards/{card_id}")
async def update_card_image(
    deck_id: str,
    card_id: str,
    req: UpdateCardImageRequest,
    user_id: str = Depends(get_current_user),
):
    return await update_owned_deck_card_image(deck_id, card_id, user_id, req)


@deck_router.delete("/{deck_id}/cards/{card_id}", status_code=204)
async def remove_card(
    deck_id: str,
    card_id: str,
    board: str | None = Query(None),
    user_id: str = Depends(get_current_user),
):
    await remove_owned_deck_card(deck_id, card_id, user_id, board)


@deck_router.get("/{deck_id}/export/text")
async def export_deck_text(deck_id: str, user_id: str = Depends(get_current_user)):
    deck = await require_owner(deck_id, user_id)
    content = await build_decklist_text(deck_id)
    return PlainTextResponse(content, headers=build_attachment_headers(f"{deck['name']}.txt"))


@deck_router.post("/{deck_id}/analyze")
async def analyze_deck_endpoint(deck_id: str, user_id: str = Depends(get_current_user)):
    return await analyze_owned_deck(deck_id, user_id)


@deck_router.post("/{deck_id}/import")
async def import_deck(deck_id: str, req: ImportDeckRequest, user_id: str = Depends(get_current_user)):
    return await import_owned_deck(deck_id, user_id, req)


@deck_router.get("/{deck_id}/export/stream")
async def export_deck_pdf_stream(deck_id: str, user_id: str = Depends(get_current_user)):
    return StreamingResponse(stream_pdf_export(deck_id, user_id), media_type="text/event-stream")


@deck_router.get("/{deck_id}/export/download/{export_id}")
async def export_download(deck_id: str, export_id: str, request: Request, user_id: str = Depends(get_current_user)):
    await require_owner(deck_id, user_id)
    pdf_bytes, filename = pop_pdf_export(export_id)
    return build_export_download_response(
        pdf_bytes,
        filename,
        "application/pdf",
        request.headers.get("range"),
    )


@deck_router.get("/{deck_id}/export/images/stream")
async def export_deck_images_stream(deck_id: str, user_id: str = Depends(get_current_user)):
    return StreamingResponse(stream_image_export(deck_id, user_id), media_type="text/event-stream")


@deck_router.get("/{deck_id}/export/images/download/{export_id}")
async def export_images_download(deck_id: str, export_id: str, request: Request, user_id: str = Depends(get_current_user)):
    await require_owner(deck_id, user_id)
    zip_bytes, filename = pop_image_export(export_id)
    return build_export_download_response(
        zip_bytes,
        filename,
        "application/zip",
        request.headers.get("range"),
    )


@shared_deck_router.get("/{deck_id}")
async def get_shared_deck(deck_id: str):
    return await require_existing_deck(deck_id)


@shared_deck_router.get("/{deck_id}/cards")
async def get_shared_deck_cards(deck_id: str):
    return await list_public_deck_cards(deck_id)


@shared_deck_router.get("/{deck_id}/export/text")
async def shared_export_deck_text(deck_id: str):
    deck = await require_existing_deck(deck_id)
    content = await build_decklist_text(deck_id)
    return PlainTextResponse(content, headers=build_attachment_headers(f"{deck['name']}.txt"))


@shared_deck_router.get("/{deck_id}/export/stream")
async def shared_export_deck_pdf_stream(deck_id: str):
    return StreamingResponse(stream_pdf_export(deck_id), media_type="text/event-stream")


@shared_deck_router.get("/{deck_id}/export/download/{export_id}")
async def shared_export_download(deck_id: str, export_id: str, request: Request):
    pdf_bytes, filename = pop_pdf_export(export_id)
    return build_export_download_response(
        pdf_bytes,
        filename,
        "application/pdf",
        request.headers.get("range"),
    )


@shared_deck_router.get("/{deck_id}/export/images/stream")
async def shared_export_deck_images_stream(deck_id: str):
    return StreamingResponse(stream_image_export(deck_id), media_type="text/event-stream")


@shared_deck_router.get("/{deck_id}/export/images/download/{export_id}")
async def shared_export_images_download(deck_id: str, export_id: str, request: Request):
    zip_bytes, filename = pop_image_export(export_id)
    return build_export_download_response(
        zip_bytes,
        filename,
        "application/zip",
        request.headers.get("range"),
    )
