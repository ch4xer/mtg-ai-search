"""Deck endpoints: CRUD, cards, text import/export, PDF export."""

import asyncio
import io
import json
import logging
import re
import time as _time
import zipfile
from urllib.parse import quote
from uuid import uuid4

import httpx
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .auth import get_current_user
from .db import (
    add_card_to_deck,
    create_deck,
    delete_deck,
    get_cards_by_names,
    get_card_by_oracle_id,
    get_card_print_by_set_cn,
    get_deck,
    get_deck_card_images,
    get_deck_cards,
    get_deck_cards_for_analysis,
    get_deck_cards_for_export,
    get_user_decks,
    remove_card_from_deck,
    update_deck,
    update_deck_analysis,
    update_deck_card_image,
)
from .deck_analysis import analyze_deck

logger = logging.getLogger(__name__)

deck_router = APIRouter(prefix="/api/decks", tags=["decks"])
shared_deck_router = APIRouter(prefix="/api/shared/decks", tags=["shared-decks"])
# Match "<qty> <name>" optionally followed by "(SET) collector_number" and
# trailing *F*/*E*/etc. markers (Arena/MTGO export format).
# Set code and collector_number are captured for printing-specific lookups.
DECKLIST_ENTRY_RE = re.compile(
    r"^(\d+)\s+(.+?)(?:\s+\(([A-Za-z0-9]{2,6})\)\s+(\S+))?(?:\s+\*\w+\*)*\s*$"
)


# Accepted deck format keys (match Scryfall's `legalities` keys, plus `undefined`).
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


class CreateDeckRequest(BaseModel):
    name: str
    format: str = "undefined"


class UpdateDeckRequest(BaseModel):
    name: str
    format: str | None = None


class AddCardRequest(BaseModel):
    card_id: str
    quantity: int = 1
    print_id: str | None = None
    image_url: str | None = None
    display_url: str | None = None
    board: str = "mainboard"


class UpdateCardImageRequest(BaseModel):
    print_id: str | None = None
    image_url: str | None = None
    display_url: str | None = None
    board: str | None = None


class ImportDeckRequest(BaseModel):
    text: str


def _require_deck_name(name: str) -> str:
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Deck name cannot be empty")
    return clean_name


def _require_nonzero_quantity(quantity: int) -> None:
    if quantity == 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be zero")


def _build_attachment_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}


async def _verify_deck_ownership(deck_id: str, user_id: str) -> dict:
    """Fetch deck and verify it belongs to the user. Raises 404 if not found or not owned."""
    deck = await get_deck(deck_id)
    if not deck or deck["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


def _validate_format(raw: str | None) -> str | None:
    """Normalise and validate a format key. Returns None if raw is None."""
    if raw is None:
        return None
    fmt = raw.strip().lower()
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format: {raw}")
    return fmt


@deck_router.get("")
async def list_decks(user_id: str = Depends(get_current_user)):
    return await get_user_decks(user_id)


@deck_router.post("", status_code=201)
async def create_deck_endpoint(req: CreateDeckRequest, user_id: str = Depends(get_current_user)):
    fmt = _validate_format(req.format) or "undefined"
    return await create_deck(user_id, _require_deck_name(req.name), fmt)


@deck_router.get("/{deck_id}")
async def get_deck_endpoint(deck_id: str, user_id: str = Depends(get_current_user)):
    """Fetch a single deck (id, name, format, timestamps, card_count)."""
    await _verify_deck_ownership(deck_id, user_id)
    # Re-fetch via the list path so we get card_count too
    decks = await get_user_decks(user_id)
    deck = next((d for d in decks if d["id"] == deck_id), None)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


@deck_router.put("/{deck_id}")
async def update_deck_endpoint(deck_id: str, req: UpdateDeckRequest, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    fmt = _validate_format(req.format)
    return await update_deck(deck_id, _require_deck_name(req.name), fmt)


@deck_router.delete("/{deck_id}", status_code=204)
async def delete_deck_endpoint(deck_id: str, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    await delete_deck(deck_id)


@deck_router.get("/{deck_id}/cards")
async def list_deck_cards(deck_id: str, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    return await get_deck_cards(deck_id)


@deck_router.post("/{deck_id}/cards", status_code=201)
async def add_card(deck_id: str, req: AddCardRequest, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    _require_nonzero_quantity(req.quantity)
    update_image = "image_url" in req.model_fields_set or "display_url" in req.model_fields_set
    return await add_card_to_deck(
        deck_id, req.card_id, req.quantity, req.image_url, req.display_url, update_image, req.board, req.print_id
    )


@deck_router.patch("/{deck_id}/cards/{card_id}")
async def update_card_image(
    deck_id: str,
    card_id: str,
    req: UpdateCardImageRequest,
    user_id: str = Depends(get_current_user),
):
    """Update a deck card's image override without changing quantity.

    Passing null values resets the override to the default card image.
    """
    await _verify_deck_ownership(deck_id, user_id)
    updated = await update_deck_card_image(deck_id, card_id, req.image_url, req.display_url, req.board, req.print_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Card not in deck")
    return updated


@deck_router.delete("/{deck_id}/cards/{card_id}", status_code=204)
async def remove_card(
    deck_id: str, card_id: str,
    board: str | None = Query(None),
    user_id: str = Depends(get_current_user),
):
    await _verify_deck_ownership(deck_id, user_id)
    await remove_card_from_deck(deck_id, card_id, board)


# ── Deck Import / Export (text) ────────────────────────────────────────


def _extract_front_face_name(name: str) -> str:
    """Extract front face name for double-faced cards.

    Handles both 'Name A / Name B' and 'Name A // Name B' formats.
    """
    name = name.strip()
    for sep in [" // ", " / "]:
        if sep in name:
            return name.split(sep)[0].strip()
    return name


def _parse_decklist(text: str) -> list[tuple[int, str, str, str | None, str | None]]:
    """Parse a decklist text into [(quantity, card_name, board, set_code, collector_number), ...].

    Accepted line formats:
    - '<qty> <name> (<SET>) <collector_number> [*F*|*E*|...]' — Arena/MTGO
    - '<qty> <name>'
    - '<name>' — defaults to qty 1

    Lines starting with '#' or '//' are skipped.

    Board tracking:
    - Cards default to 'mainboard'.
    - A line containing 'SIDEBOARD' (case-insensitive) switches to 'sideboard'.
    - An empty line after sideboard cards switches back to 'mainboard'.

    Double-faced cards:
    - 'Name A / Name B' or 'Name A // Name B' → use 'Name A' for lookup

    Set code and collector number are captured for printing-specific lookups.
    """
    entries: list[tuple[int, str, str, str | None, str | None]] = []
    board = "mainboard"
    has_sideboard_cards = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("#") or line.startswith("//"):
            continue
        if "SIDEBOARD" in line.upper():
            board = "sideboard"
            has_sideboard_cards = False
            continue
        if not line:
            if board == "sideboard" and has_sideboard_cards:
                board = "mainboard"
            continue
        m = DECKLIST_ENTRY_RE.match(line)
        if m:
            name = _extract_front_face_name(m.group(2))
            set_code = m.group(3)  # None if not specified
            collector_num = m.group(4)  # None if not specified
            entries.append((int(m.group(1)), name, board, set_code, collector_num))
        else:
            entries.append((1, _extract_front_face_name(line), board, None, None))
        if board == "sideboard":
            has_sideboard_cards = True
    return entries


@deck_router.get("/{deck_id}/export/text")
async def export_deck_text(deck_id: str, user_id: str = Depends(get_current_user)):
    deck = await _verify_deck_ownership(deck_id, user_id)
    cards = await get_deck_cards_for_export(deck_id)
    if not cards:
        raise HTTPException(status_code=400, detail="Deck is empty")
    main_lines = [f"{c['quantity']} {c['name']}" for c in cards if c["board"] == "mainboard"]
    side_lines = [f"{c['quantity']} {c['name']}" for c in cards if c["board"] == "sideboard"]
    lines = main_lines
    if side_lines:
        lines += ["", "SIDEBOARD"] + side_lines
    content = "\n".join(lines) + "\n"
    filename = f"{deck['name']}.txt"
    return PlainTextResponse(
        content,
        headers=_build_attachment_headers(filename),
    )


@deck_router.post("/{deck_id}/analyze")
async def analyze_deck_endpoint(deck_id: str, user_id: str = Depends(get_current_user)):
    from .agent import DEEPSEEK_API_KEY
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=503, detail="Deepseek API key not configured")

    deck = await _verify_deck_ownership(deck_id, user_id)

    cards = await get_deck_cards_for_analysis(deck_id)
    mainboard = [c for c in cards if c.get("board") != "sideboard"]
    if not mainboard:
        raise HTTPException(status_code=400, detail="Deck is empty")

    try:
        analysis = await analyze_deck(deck["name"], deck.get("format", "undefined"), cards)
    except ValueError as exc:
        logger.warning("Deck analysis failed for %s: %s", deck_id, exc)
        raise HTTPException(status_code=502, detail="Analysis failed, please try again") from exc
    except Exception as exc:
        logger.exception("Deck analysis error for %s", deck_id)
        raise HTTPException(status_code=502, detail="Analysis failed, please try again") from exc

    return await update_deck_analysis(deck_id, analysis)


@deck_router.post("/{deck_id}/import")
async def import_deck(deck_id: str, req: ImportDeckRequest, user_id: str = Depends(get_current_user)):
    """Import cards from decklist text using local database only.

    All lookups are done against the local cards and card_prints tables,
    including flavor_name aliases and set-specific print versions.
    No Scryfall API calls are made, avoiding rate limit issues.
    """
    await _verify_deck_ownership(deck_id, user_id)

    entries = _parse_decklist(req.text)
    if not entries:
        raise HTTPException(status_code=400, detail="No cards found in text")

    unique_names = list({name for _, name, _, _, _ in entries})
    name_to_id = await get_cards_by_names(unique_names)

    added = []
    not_found = []

    for qty, name, board, set_code, collector_num in entries:
        card_id = name_to_id.get(name.lower())
        image_url = None
        display_url = None
        print_id = None
        resolved_name = None

        # If card found and has set code, try to get specific print
        if card_id and set_code:
            print_info = await get_card_print_by_set_cn(card_id, set_code, collector_num or "")
            if print_info:
                print_id = print_info["id"]
                image_url = print_info.get("image_large") or print_info.get("image_png")
                display_url = print_info.get("image_art_crop")

        # If card not found by name, try direct oracle_id lookup
        # (handles cases where name_to_id might miss flavor names)
        if not card_id:
            # Try to get card by oracle_id directly (in case user provided oracle_id as name)
            card_info = await get_card_by_oracle_id(name)
            if card_info:
                card_id = card_info["id"]
                resolved_name = card_info["name"]

        if card_id:
            await add_card_to_deck(
                deck_id, card_id, qty,
                image_url=image_url, display_url=display_url,
                update_image=bool(image_url), board=board,
                print_id=print_id,
            )
            result = {"name": resolved_name or name, "quantity": qty, "board": board}
            if set_code:
                result["set"] = set_code
            if resolved_name and resolved_name.lower() != name.lower():
                result["resolved_from"] = name
            added.append(result)
        else:
            not_found.append(name)

    return {"added": added, "not_found": not_found}


# ── Deck PDF Export ────────────────────────────────────────────────────

CARD_W = 2.5 * inch  # 180 pt
CARD_H = 3.5 * inch  # 252 pt
COLS, ROWS = 3, 3
CARDS_PER_PAGE = COLS * ROWS
FIX_W = 0
FIX_H = 0

# Temporary in-memory cache for generated PDFs
_export_cache: dict[str, tuple[bytes, str, float]] = {}
_EXPORT_CACHE_TTL = 300  # 5 minutes


def _cleanup_export_cache():
    now = _time.time()
    expired = [k for k, v in _export_cache.items() if now - v[2] > _EXPORT_CACHE_TTL]
    for k in expired:
        del _export_cache[k]


def _expand_slots(cards: list[dict]) -> list[tuple[str, str]]:
    """Expand card rows into (name, url) slots, one per copy."""
    slots: list[tuple[str, str]] = []
    for card in cards:
        url = card["png_url"]
        if url:
            for _ in range(card["quantity"]):
                slots.append((card["name"], url))
        back_url = card.get("back_png_url")
        if back_url:
            back_name = card.get("back_name") or card["name"] + " (Back)"
            for _ in range(card["quantity"]):
                slots.append((back_name, back_url))
    return slots


def _build_pdf(unique_data: list[bytes | None], slot_url_index: list[int]) -> io.BytesIO:
    """Generate a 3x3 card-grid PDF from deduplicated image data.

    unique_data: one entry per unique URL (bytes or None if download failed).
    slot_url_index: maps each card slot to its index in unique_data.
    """
    page_w, page_h = A4
    x_gap, y_gap = FIX_W, FIX_H
    grid_w = COLS * CARD_W + (COLS - 1) * x_gap
    grid_h = ROWS * CARD_H + (ROWS - 1) * y_gap
    x_offset = (page_w - grid_w) / 2
    y_offset = (page_h - grid_h) / 2

    def _draw_cut_guides(c):
        c.saveState()
        c.setStrokeColorRGB(0.3, 0.3, 0.3)
        c.setLineWidth(0.5)
        c.setDash(4, 4)
        for col in range(1, COLS):
            gx = x_offset + col * CARD_W
            c.line(gx, 0, gx, page_h)
        for row in range(1, ROWS):
            gy = page_h - y_offset - row * CARD_H
            c.line(0, gy, page_w, gy)
        c.restoreState()

    # Process each unique image once
    readers: dict[int, ImageReader] = {}
    for i, data in enumerate(unique_data):
        if data is None:
            continue
        pil_img = Image.open(io.BytesIO(data))
        if pil_img.mode == "RGBA":
            bg = Image.new("RGBA", pil_img.size, (0, 0, 0, 255))
            bg.paste(pil_img, (0, 0), pil_img)
            pil_img = bg.convert("RGB")
        elif pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        readers[i] = ImageReader(pil_img)

    # Build PDF pages using cached ImageReaders
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    slot_index = 0

    for uid in slot_url_index:
        if uid not in readers:
            slot_index += 1
            continue
        pos = slot_index % CARDS_PER_PAGE
        if pos == 0 and slot_index > 0:
            _draw_cut_guides(c)
            c.showPage()
        col = pos % COLS
        row = pos // COLS
        x = x_offset + col * (CARD_W + x_gap)
        y = page_h - y_offset - (row + 1) * CARD_H - row * y_gap
        c.drawImage(readers[uid], x, y, width=CARD_W, height=CARD_H, preserveAspectRatio=True)
        slot_index += 1

    _draw_cut_guides(c)
    c.save()
    buf.seek(0)
    return buf


@deck_router.get("/{deck_id}/export/stream")
async def export_deck_pdf_stream(deck_id: str, user_id: str = Depends(get_current_user)):
    """SSE endpoint that streams download progress, then caches the PDF."""
    deck = await _verify_deck_ownership(deck_id, user_id)
    cards = await get_deck_card_images(deck_id)
    slots = _expand_slots(cards)

    if not slots:
        raise HTTPException(status_code=400, detail="No card images to export")

    total = len(slots)
    filename = f"{deck['name']}_cards.pdf"

    async def event_stream():
        _cleanup_export_cache()

        # Deduplicate downloads: same URL only fetched once
        unique_urls: dict[str, int] = {}  # url -> index in unique list
        slot_url_index: list[int] = []
        for _, url in slots:
            if url not in unique_urls:
                unique_urls[url] = len(unique_urls)
            slot_url_index.append(unique_urls[url])
        unique_url_list = list(unique_urls.keys())
        unique_count = len(unique_url_list)
        unique_data: list[bytes | None] = [None] * unique_count

        sem = asyncio.Semaphore(10)
        progress_queue: asyncio.Queue[int | None] = asyncio.Queue()

        async def fetch_one(client: httpx.AsyncClient, url: str, uid: int):
            async with sem:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        unique_data[uid] = resp.content
                except Exception as e:
                    logger.warning("Failed to download %s: %s", url, e)
            await progress_queue.put(uid)

        async def download_all():
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                tasks = [fetch_one(client, url, i) for i, url in enumerate(unique_url_list)]
                await asyncio.gather(*tasks)
            await progress_queue.put(None)

        dl_task = asyncio.create_task(download_all())

        completed = 0
        while True:
            idx = await progress_queue.get()
            if idx is None:
                break
            completed += 1
            yield f"data: {json.dumps({'type': 'progress', 'phase': 'download', 'current': completed, 'total': unique_count})}\n\n"

        await dl_task

        yield f"data: {json.dumps({'type': 'progress', 'phase': 'pdf', 'current': total, 'total': total})}\n\n"

        # Pass deduplicated data and slot mapping directly to avoid redundant processing
        pdf_buf = await asyncio.to_thread(_build_pdf, unique_data, slot_url_index)

        export_id = str(uuid4())
        _export_cache[export_id] = (pdf_buf.getvalue(), filename, _time.time())

        yield f"data: {json.dumps({'type': 'complete', 'export_id': export_id})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@deck_router.get("/{deck_id}/export/download/{export_id}")
async def export_download(deck_id: str, export_id: str, user_id: str = Depends(get_current_user)):
    """Download a previously generated PDF by export_id."""
    await _verify_deck_ownership(deck_id, user_id)
    entry = _export_cache.pop(export_id, None)
    if not entry:
        raise HTTPException(status_code=404, detail="Export not found or expired")
    pdf_bytes, filename, _ = entry
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=_build_attachment_headers(filename),
    )


# ── Deck Image Collection Export (ZIP) ─────────────────────────────────────

# Separate cache for image exports to avoid conflicts with PDF exports
_image_export_cache: dict[str, tuple[bytes, str, float]] = {}
_IMAGE_EXPORT_CACHE_TTL = 300  # 5 minutes


def _cleanup_image_export_cache():
    now = _time.time()
    expired = [k for k, v in _image_export_cache.items() if now - v[2] > _IMAGE_EXPORT_CACHE_TTL]
    for k in expired:
        del _image_export_cache[k]


def _sanitize_filename(name: str) -> str:
    """Remove/replace characters that are invalid in filenames."""
    # Replace common problematic characters
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Remove leading/trailing dots and spaces
    name = name.strip('. ')
    # Limit length to avoid filesystem issues
    if len(name) > 200:
        name = name[:200]
    return name or "card"


def _build_zip(unique_data: list[bytes | None], slots: list[tuple[str, str]], slot_url_index: list[int]) -> io.BytesIO:
    """Create a ZIP archive containing all card images.

    Each card is named as "{quantity}x {card_name}.png".
    For duplicate copies of the same card, they share the same image data.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Track filenames to handle duplicates
        filename_counts: dict[str, int] = {}

        for slot_idx, (card_name, _) in enumerate(slots):
            uid = slot_url_index[slot_idx]
            if uid >= len(unique_data) or unique_data[uid] is None:
                continue

            data = unique_data[uid]
            assert data is not None  # Already checked above
            # Sanitize card name for filename
            safe_name = _sanitize_filename(card_name)

            # Handle duplicate filenames
            if safe_name in filename_counts:
                filename_counts[safe_name] += 1
                base_name = safe_name
                # Try adding number suffix
                for i in range(2, filename_counts[safe_name] + 10):
                    candidate = f"{base_name}_{i}"
                    if candidate not in filename_counts:
                        safe_name = candidate
                        filename_counts[candidate] = 1
                        break
            else:
                filename_counts[safe_name] = 1

            filename = f"{safe_name}.png"
            zf.writestr(filename, data)

    buf.seek(0)
    return buf


@deck_router.get("/{deck_id}/export/images/stream")
async def export_deck_images_stream(deck_id: str, user_id: str = Depends(get_current_user)):
    """SSE endpoint that streams download progress for image collection, then caches the ZIP."""
    deck = await _verify_deck_ownership(deck_id, user_id)
    cards = await get_deck_card_images(deck_id)
    slots = _expand_slots(cards)

    if not slots:
        raise HTTPException(status_code=400, detail="No card images to export")

    total = len(slots)
    filename = f"{deck['name']}_images.zip"

    async def event_stream():
        _cleanup_image_export_cache()

        # Deduplicate downloads: same URL only fetched once
        unique_urls: dict[str, int] = {}  # url -> index in unique list
        slot_url_index: list[int] = []
        for _, url in slots:
            if url not in unique_urls:
                unique_urls[url] = len(unique_urls)
            slot_url_index.append(unique_urls[url])
        unique_url_list = list(unique_urls.keys())
        unique_count = len(unique_url_list)
        unique_data: list[bytes | None] = [None] * unique_count

        sem = asyncio.Semaphore(10)
        progress_queue: asyncio.Queue[int | None] = asyncio.Queue()

        async def fetch_one(client: httpx.AsyncClient, url: str, uid: int):
            async with sem:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        unique_data[uid] = resp.content
                except Exception as e:
                    logger.warning("Failed to download %s: %s", url, e)
            await progress_queue.put(uid)

        async def download_all():
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                tasks = [fetch_one(client, url, i) for i, url in enumerate(unique_url_list)]
                await asyncio.gather(*tasks)
            await progress_queue.put(None)

        dl_task = asyncio.create_task(download_all())

        completed = 0
        while True:
            idx = await progress_queue.get()
            if idx is None:
                break
            completed += 1
            yield f"data: {json.dumps({'type': 'progress', 'phase': 'download', 'current': completed, 'total': unique_count})}\n\n"

        await dl_task

        yield f"data: {json.dumps({'type': 'progress', 'phase': 'zip', 'current': total, 'total': total})}\n\n"

        # Build ZIP archive
        zip_buf = await asyncio.to_thread(_build_zip, unique_data, slots, slot_url_index)

        export_id = str(uuid4())
        _image_export_cache[export_id] = (zip_buf.getvalue(), filename, _time.time())

        yield f"data: {json.dumps({'type': 'complete', 'export_id': export_id})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@deck_router.get("/{deck_id}/export/images/download/{export_id}")
async def export_images_download(deck_id: str, export_id: str, user_id: str = Depends(get_current_user)):
    """Download a previously generated ZIP by export_id."""
    await _verify_deck_ownership(deck_id, user_id)
    entry = _image_export_cache.pop(export_id, None)
    if not entry:
        raise HTTPException(status_code=404, detail="Export not found or expired")
    zip_bytes, filename, _ = entry
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers=_build_attachment_headers(filename),
    )


# ── Shared (public, read-only) endpoints ──────────────────────────────


@shared_deck_router.get("/{deck_id}")
async def get_shared_deck(deck_id: str):
    """Public read-only view of a deck (no auth required)."""
    deck = await get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


@shared_deck_router.get("/{deck_id}/cards")
async def get_shared_deck_cards(deck_id: str):
    """Public read-only card list for a deck (no auth required)."""
    deck = await get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return await get_deck_cards(deck_id)


@shared_deck_router.get("/{deck_id}/export/text")
async def shared_export_deck_text(deck_id: str):
    """Public text export for a shared deck."""
    deck = await get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    cards = await get_deck_cards_for_export(deck_id)
    if not cards:
        raise HTTPException(status_code=400, detail="Deck is empty")
    main_lines = [f"{c['quantity']} {c['name']}" for c in cards if c["board"] == "mainboard"]
    side_lines = [f"{c['quantity']} {c['name']}" for c in cards if c["board"] == "sideboard"]
    lines = main_lines
    if side_lines:
        lines += ["", "SIDEBOARD"] + side_lines
    content = "\n".join(lines) + "\n"
    filename = f"{deck['name']}.txt"
    return PlainTextResponse(content, headers=_build_attachment_headers(filename))


@shared_deck_router.get("/{deck_id}/export/stream")
async def shared_export_deck_pdf_stream(deck_id: str):
    """Public PDF export stream for a shared deck."""
    deck = await get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    cards = await get_deck_card_images(deck_id)
    slots = _expand_slots(cards)
    if not slots:
        raise HTTPException(status_code=400, detail="No card images to export")

    total = len(slots)
    filename = f"{deck['name']}_cards.pdf"

    async def event_stream():
        _cleanup_export_cache()
        unique_urls: dict[str, int] = {}
        slot_url_index: list[int] = []
        for _, url in slots:
            if url not in unique_urls:
                unique_urls[url] = len(unique_urls)
            slot_url_index.append(unique_urls[url])
        unique_url_list = list(unique_urls.keys())
        unique_count = len(unique_url_list)
        unique_data: list[bytes | None] = [None] * unique_count

        sem = asyncio.Semaphore(10)
        progress_queue: asyncio.Queue[int | None] = asyncio.Queue()

        async def fetch_one(client: httpx.AsyncClient, url: str, uid: int):
            async with sem:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        unique_data[uid] = resp.content
                except Exception as e:
                    logger.warning("Failed to download %s: %s", url, e)
            await progress_queue.put(uid)

        async def download_all():
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                tasks = [fetch_one(client, url, i) for i, url in enumerate(unique_url_list)]
                await asyncio.gather(*tasks)
            await progress_queue.put(None)

        dl_task = asyncio.create_task(download_all())
        completed = 0
        while True:
            idx = await progress_queue.get()
            if idx is None:
                break
            completed += 1
            yield f"data: {json.dumps({'type': 'progress', 'phase': 'download', 'current': completed, 'total': unique_count})}\n\n"
        await dl_task
        yield f"data: {json.dumps({'type': 'progress', 'phase': 'pdf', 'current': total, 'total': total})}\n\n"
        pdf_buf = await asyncio.to_thread(_build_pdf, unique_data, slot_url_index)
        export_id = str(uuid4())
        _export_cache[export_id] = (pdf_buf.getvalue(), filename, _time.time())
        yield f"data: {json.dumps({'type': 'complete', 'export_id': export_id})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@shared_deck_router.get("/{deck_id}/export/download/{export_id}")
async def shared_export_download(deck_id: str, export_id: str):
    """Public download of a previously generated PDF."""
    entry = _export_cache.pop(export_id, None)
    if not entry:
        raise HTTPException(status_code=404, detail="Export not found or expired")
    pdf_bytes, filename, _ = entry
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers=_build_attachment_headers(filename),
    )


@shared_deck_router.get("/{deck_id}/export/images/stream")
async def shared_export_deck_images_stream(deck_id: str):
    """Public image ZIP export stream for a shared deck."""
    deck = await get_deck(deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    cards = await get_deck_card_images(deck_id)
    slots = _expand_slots(cards)
    if not slots:
        raise HTTPException(status_code=400, detail="No card images to export")

    total = len(slots)
    filename = f"{deck['name']}_images.zip"

    async def event_stream():
        _cleanup_image_export_cache()
        unique_urls: dict[str, int] = {}
        slot_url_index: list[int] = []
        for _, url in slots:
            if url not in unique_urls:
                unique_urls[url] = len(unique_urls)
            slot_url_index.append(unique_urls[url])
        unique_url_list = list(unique_urls.keys())
        unique_count = len(unique_url_list)
        unique_data: list[bytes | None] = [None] * unique_count

        sem = asyncio.Semaphore(10)
        progress_queue: asyncio.Queue[int | None] = asyncio.Queue()

        async def fetch_one(client: httpx.AsyncClient, url: str, uid: int):
            async with sem:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        unique_data[uid] = resp.content
                except Exception as e:
                    logger.warning("Failed to download %s: %s", url, e)
            await progress_queue.put(uid)

        async def download_all():
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                tasks = [fetch_one(client, url, i) for i, url in enumerate(unique_url_list)]
                await asyncio.gather(*tasks)
            await progress_queue.put(None)

        dl_task = asyncio.create_task(download_all())
        completed = 0
        while True:
            idx = await progress_queue.get()
            if idx is None:
                break
            completed += 1
            yield f"data: {json.dumps({'type': 'progress', 'phase': 'download', 'current': completed, 'total': unique_count})}\n\n"
        await dl_task
        yield f"data: {json.dumps({'type': 'progress', 'phase': 'zip', 'current': total, 'total': total})}\n\n"
        zip_buf = await asyncio.to_thread(_build_zip, unique_data, slots, slot_url_index)
        export_id = str(uuid4())
        _image_export_cache[export_id] = (zip_buf.getvalue(), filename, _time.time())
        yield f"data: {json.dumps({'type': 'complete', 'export_id': export_id})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@shared_deck_router.get("/{deck_id}/export/images/download/{export_id}")
async def shared_export_images_download(deck_id: str, export_id: str):
    """Public download of a previously generated ZIP."""
    entry = _image_export_cache.pop(export_id, None)
    if not entry:
        raise HTTPException(status_code=404, detail="Export not found or expired")
    zip_bytes, filename, _ = entry
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers=_build_attachment_headers(filename),
    )
