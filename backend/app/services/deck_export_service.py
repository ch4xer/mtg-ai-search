"""Deck export orchestration."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from time import perf_counter
from urllib.parse import quote

from fastapi import HTTPException
from starlette.responses import Response

from ..repositories.decks import get_deck_card_images
from .deck_access_service import require_existing_deck, require_owner
from .export_cache import ExportCache, get_export, put_export
from .image_download_service import ImageSlot, download_unique_images, expand_card_image_slots
from .pdf_exporter import build_pdf
from .zip_exporter import build_zip

_pdf_export_cache: ExportCache = {}
_image_export_cache: ExportCache = {}
logger = logging.getLogger(__name__)


def build_attachment_headers(filename: str, content_length: int | None = None) -> dict[str, str]:
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        "Accept-Ranges": "bytes",
    }
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    return headers


def build_export_download_response(
    data: bytes,
    filename: str,
    media_type: str,
    range_header: str | None = None,
) -> Response:
    total = len(data)
    if not range_header:
        return Response(
            content=data,
            media_type=media_type,
            headers=build_attachment_headers(filename, total),
        )

    if not range_header.startswith("bytes=") or "," in range_header:
        raise HTTPException(status_code=416, detail="Invalid Range header")

    start_str, end_str = range_header[6:].split("-", 1)
    try:
        if start_str == "":
            length = int(end_str)
            if length <= 0:
                raise ValueError
            start = max(total - length, 0)
            end = total - 1
        else:
            start = int(start_str)
            end = int(end_str) if end_str else total - 1
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Invalid Range header") from exc

    if start < 0 or start >= total or end < start:
        raise HTTPException(
            status_code=416,
            detail="Requested Range Not Satisfiable",
            headers={"Content-Range": f"bytes */{total}"},
        )

    end = min(end, total - 1)
    chunk = data[start : end + 1]
    headers = build_attachment_headers(filename, len(chunk))
    headers["Content-Range"] = f"bytes {start}-{end}/{total}"
    return Response(
        content=chunk,
        media_type=media_type,
        status_code=206,
        headers=headers,
    )


async def _prepare_export(deck_id: str, deck: dict, suffix: str) -> tuple[list[ImageSlot], str]:
    started = perf_counter()
    cards = await get_deck_card_images(deck_id)
    slots = expand_card_image_slots(cards)
    if not slots:
        raise HTTPException(status_code=400, detail="No card images to export")
    logger.info(
        "[deck-export] load deck_id=%s rows=%d slots=%d suffix=%s took %.2fs",
        deck_id,
        len(cards),
        len(slots),
        suffix,
        perf_counter() - started,
    )
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
    started = perf_counter()
    slots, filename = await _load_export_input(deck_id, user_id, "cards.pdf")
    total = len(slots)
    logger.info("[deck-export] pdf start deck_id=%s auth=%s slots=%d", deck_id, bool(user_id), total)

    unique_data = None
    slot_url_index = None
    download_started = perf_counter()
    async for event, data, index in _download_for_sse(slots):
        if event:
            yield event
        else:
            unique_data, slot_url_index = data, index

    assert unique_data is not None and slot_url_index is not None
    logger.info(
        "[deck-export] pdf download deck_id=%s unique=%d slots=%d took %.2fs",
        deck_id,
        len(unique_data),
        total,
        perf_counter() - download_started,
    )
    yield f"data: {json.dumps({'type': 'progress', 'phase': 'pdf', 'current': total, 'total': total})}\n\n"
    build_started = perf_counter()
    pdf_buf = await asyncio.to_thread(build_pdf, unique_data, slot_url_index)
    pdf_bytes = pdf_buf.getvalue()
    logger.info(
        "[deck-export] pdf build deck_id=%s output=%.2fMiB took %.2fs",
        deck_id,
        len(pdf_bytes) / (1024 * 1024),
        perf_counter() - build_started,
    )
    export_id = put_export(_pdf_export_cache, pdf_bytes, filename)
    logger.info("[deck-export] pdf complete deck_id=%s took %.2fs", deck_id, perf_counter() - started)
    yield f"data: {json.dumps({'type': 'complete', 'export_id': export_id})}\n\n"


async def stream_image_export(deck_id: str, user_id: str | None = None) -> AsyncIterator[str]:
    started = perf_counter()
    slots, filename = await _load_export_input(deck_id, user_id, "images.zip")
    total = len(slots)
    logger.info("[deck-export] zip start deck_id=%s auth=%s slots=%d", deck_id, bool(user_id), total)

    unique_data = None
    slot_url_index = None
    download_started = perf_counter()
    async for event, data, index in _download_for_sse(slots):
        if event:
            yield event
        else:
            unique_data, slot_url_index = data, index

    assert unique_data is not None and slot_url_index is not None
    logger.info(
        "[deck-export] zip download deck_id=%s unique=%d slots=%d took %.2fs",
        deck_id,
        len(unique_data),
        total,
        perf_counter() - download_started,
    )
    yield f"data: {json.dumps({'type': 'progress', 'phase': 'zip', 'current': total, 'total': total})}\n\n"
    build_started = perf_counter()
    zip_buf = await asyncio.to_thread(build_zip, unique_data, slots, slot_url_index)
    zip_bytes = zip_buf.getvalue()
    logger.info(
        "[deck-export] zip build deck_id=%s output=%.2fMiB took %.2fs",
        deck_id,
        len(zip_bytes) / (1024 * 1024),
        perf_counter() - build_started,
    )
    export_id = put_export(_image_export_cache, zip_bytes, filename)
    logger.info("[deck-export] zip complete deck_id=%s took %.2fs", deck_id, perf_counter() - started)
    yield f"data: {json.dumps({'type': 'complete', 'export_id': export_id})}\n\n"


def pop_pdf_export(export_id: str) -> tuple[bytes, str]:
    return get_export(_pdf_export_cache, export_id)


def pop_image_export(export_id: str) -> tuple[bytes, str]:
    return get_export(_image_export_cache, export_id)
