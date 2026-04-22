"""Deck export orchestration."""

import asyncio
import json
from collections.abc import AsyncIterator
from urllib.parse import quote

from fastapi import HTTPException

from ..repositories.decks import get_deck_card_images
from .deck_access_service import require_existing_deck, require_owner
from .export_cache import ExportCache, pop_export, put_export
from .image_download_service import ImageSlot, download_unique_images, expand_card_image_slots
from .pdf_exporter import build_pdf
from .zip_exporter import build_zip

_pdf_export_cache: ExportCache = {}
_image_export_cache: ExportCache = {}


def build_attachment_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}


async def _prepare_export(deck_id: str, deck: dict, suffix: str) -> tuple[list[ImageSlot], str]:
    cards = await get_deck_card_images(deck_id)
    slots = expand_card_image_slots(cards)
    if not slots:
        raise HTTPException(status_code=400, detail="No card images to export")
    return slots, f"{deck['name']}_{suffix}"


async def _load_export_input(deck_id: str, user_id: str | None, suffix: str) -> tuple[list[ImageSlot], str]:
    deck = await (require_owner(deck_id, user_id) if user_id else require_existing_deck(deck_id))
    return await _prepare_export(deck_id, deck, suffix)


async def _download_for_sse(slots: list[ImageSlot]) -> AsyncIterator[tuple[str | None, list[bytes | None] | None, list[int] | None]]:
    async for progress, data, index in download_unique_images(slots):
        if progress:
            yield f"data: {json.dumps(progress)}\n\n", None, None
        else:
            yield None, data, index


async def stream_pdf_export(deck_id: str, user_id: str | None = None) -> AsyncIterator[str]:
    slots, filename = await _load_export_input(deck_id, user_id, "cards.pdf")
    total = len(slots)

    unique_data = None
    slot_url_index = None
    async for event, data, index in _download_for_sse(slots):
        if event:
            yield event
        else:
            unique_data, slot_url_index = data, index

    assert unique_data is not None and slot_url_index is not None
    yield f"data: {json.dumps({'type': 'progress', 'phase': 'pdf', 'current': total, 'total': total})}\n\n"
    pdf_buf = await asyncio.to_thread(build_pdf, unique_data, slot_url_index)
    export_id = put_export(_pdf_export_cache, pdf_buf.getvalue(), filename)
    yield f"data: {json.dumps({'type': 'complete', 'export_id': export_id})}\n\n"


async def stream_image_export(deck_id: str, user_id: str | None = None) -> AsyncIterator[str]:
    slots, filename = await _load_export_input(deck_id, user_id, "images.zip")
    total = len(slots)

    unique_data = None
    slot_url_index = None
    async for event, data, index in _download_for_sse(slots):
        if event:
            yield event
        else:
            unique_data, slot_url_index = data, index

    assert unique_data is not None and slot_url_index is not None
    yield f"data: {json.dumps({'type': 'progress', 'phase': 'zip', 'current': total, 'total': total})}\n\n"
    zip_buf = await asyncio.to_thread(build_zip, unique_data, slots, slot_url_index)
    export_id = put_export(_image_export_cache, zip_buf.getvalue(), filename)
    yield f"data: {json.dumps({'type': 'complete', 'export_id': export_id})}\n\n"


def pop_pdf_export(export_id: str) -> tuple[bytes, str]:
    return pop_export(_pdf_export_cache, export_id)


def pop_image_export(export_id: str) -> tuple[bytes, str]:
    return pop_export(_image_export_cache, export_id)
