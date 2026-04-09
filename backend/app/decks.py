import asyncio
import io
import json
import logging
import time as _time
from urllib.parse import quote
from uuid import uuid4

import httpx
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from .db import (
    add_card_to_deck,
    create_deck,
    create_user,
    delete_deck,
    delete_user,
    get_cards_by_names,
    get_deck,
    get_deck_card_images,
    get_deck_cards,
    get_deck_cards_for_export,
    get_user_by_username,
    get_user_decks,
    list_all_users,
    remove_card_from_deck,
    update_deck,
    update_user_role,
)

logger = logging.getLogger(__name__)

# ── Auth Router ─────────────────────────────────────────────────────────

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


@auth_router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    if len(req.username) < 2:
        raise HTTPException(status_code=400, detail="Username must be at least 2 characters")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    existing = await get_user_by_username(req.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    pw_hash = hash_password(req.password)
    user = await create_user(req.username, pw_hash)
    return AuthResponse(
        access_token=create_access_token(user["id"]),
        refresh_token=create_refresh_token(user["id"]),
        user=user,
    )


@auth_router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = await get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    user_info = {"id": user["id"], "username": user["username"], "role": user["role"]}
    return AuthResponse(
        access_token=create_access_token(user["id"]),
        refresh_token=create_refresh_token(user["id"]),
        user=user_info,
    )


@auth_router.post("/refresh")
async def refresh(req: RefreshRequest):
    user_id = decode_token(req.refresh_token, expected_type="refresh")
    return {"access_token": create_access_token(user_id)}


# ── Deck Router ─────────────────────────────────────────────────────────

deck_router = APIRouter(prefix="/api/decks", tags=["decks"])


class CreateDeckRequest(BaseModel):
    name: str


class UpdateDeckRequest(BaseModel):
    name: str


class AddCardRequest(BaseModel):
    card_id: str
    quantity: int = 1
    image_url: str | None = None
    display_url: str | None = None


async def _verify_deck_ownership(deck_id: str, user_id: str) -> dict:
    """Fetch deck and verify it belongs to the user. Raises 404 if not found or not owned."""
    deck = await get_deck(deck_id)
    if not deck or deck["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


@deck_router.get("")
async def list_decks(user_id: str = Depends(get_current_user)):
    return await get_user_decks(user_id)


@deck_router.post("", status_code=201)
async def create_deck_endpoint(req: CreateDeckRequest, user_id: str = Depends(get_current_user)):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Deck name cannot be empty")
    return await create_deck(user_id, req.name.strip())


@deck_router.put("/{deck_id}")
async def update_deck_endpoint(deck_id: str, req: UpdateDeckRequest, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="Deck name cannot be empty")
    return await update_deck(deck_id, req.name.strip())


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
    update_image = "image_url" in req.model_fields_set or "display_url" in req.model_fields_set
    return await add_card_to_deck(deck_id, req.card_id, req.quantity, req.image_url, req.display_url, update_image)


@deck_router.delete("/{deck_id}/cards/{card_id}", status_code=204)
async def remove_card(deck_id: str, card_id: str, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    await remove_card_from_deck(deck_id, card_id)


# ── Deck Import / Export (text) ────────────────────────────────────────


def _parse_decklist(text: str) -> list[tuple[int, str]]:
    """Parse a decklist text into [(quantity, card_name), ...].
    Accepts formats like '1 Sol Ring' or 'Sol Ring' (defaults to qty 1).
    Blank lines and lines starting with '#' or '//' are skipped.
    """
    import re
    entries: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        m = re.match(r"^(\d+)\s+(.+)$", line)
        if m:
            entries.append((int(m.group(1)), m.group(2).strip()))
        else:
            entries.append((1, line))
    return entries


@deck_router.get("/{deck_id}/export/text")
async def export_deck_text(deck_id: str, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)
    deck = await get_deck(deck_id)
    cards = await get_deck_cards_for_export(deck_id)
    if not cards:
        raise HTTPException(status_code=400, detail="Deck is empty")
    lines = [f"{c['quantity']} {c['name']}" for c in cards]
    content = "\n".join(lines) + "\n"
    filename = f"{deck['name']}.txt"
    return PlainTextResponse(
        content,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


class ImportDeckRequest(BaseModel):
    text: str


@deck_router.post("/{deck_id}/import")
async def import_deck(deck_id: str, req: ImportDeckRequest, user_id: str = Depends(get_current_user)):
    await _verify_deck_ownership(deck_id, user_id)

    entries = _parse_decklist(req.text)
    if not entries:
        raise HTTPException(status_code=400, detail="No cards found in text")

    # Look up all card names
    unique_names = list({name for _, name in entries})
    name_to_id = await get_cards_by_names(unique_names)

    added = []
    not_found = []
    for qty, name in entries:
        card_id = name_to_id.get(name.lower())
        if card_id:
            await add_card_to_deck(deck_id, card_id, qty)
            added.append({"name": name, "quantity": qty})
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


def _build_pdf(image_data_list: list[bytes | None]) -> io.BytesIO:
    """Generate a 3x3 card-grid PDF from downloaded image data."""
    page_w, page_h = A4
    x_gap, y_gap = FIX_W, FIX_H
    grid_w = COLS * CARD_W + (COLS - 1) * x_gap
    grid_h = ROWS * CARD_H + (ROWS - 1) * y_gap
    x_offset = (page_w - grid_w) / 2
    y_offset = (page_h - grid_h) / 2

    def _draw_cut_guides(c):
        c.saveState()
        c.setStrokeColorRGB(0.65, 0.65, 0.65)
        c.setLineWidth(0.5)
        c.setDash(4, 4)
        guide_left = x_offset
        guide_right = x_offset + COLS * CARD_W
        guide_top = page_h - y_offset
        guide_bottom = page_h - y_offset - ROWS * CARD_H
        for col in range(1, COLS):
            gx = x_offset + col * CARD_W
            c.line(gx, guide_bottom, gx, guide_top)
        for row in range(1, ROWS):
            gy = page_h - y_offset - row * CARD_H
            c.line(guide_left, gy, guide_right, gy)
        c.restoreState()

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    slot_index = 0

    for img_bytes in image_data_list:
        if img_bytes is None:
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
        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        bg = Image.new("RGBA", pil_img.size, (0, 0, 0, 255))
        bg.paste(pil_img, (0, 0), pil_img)
        flat = bg.convert("RGB")
        flat_buf = io.BytesIO()
        flat.save(flat_buf, format="PNG")
        flat_buf.seek(0)
        c.drawImage(ImageReader(flat_buf), x, y, width=CARD_W, height=CARD_H, preserveAspectRatio=True)
        slot_index += 1

    _draw_cut_guides(c)
    c.save()
    buf.seek(0)
    return buf


@deck_router.get("/{deck_id}/export/stream")
async def export_deck_pdf_stream(deck_id: str, user_id: str = Depends(get_current_user)):
    """SSE endpoint that streams download progress, then caches the PDF."""
    await _verify_deck_ownership(deck_id, user_id)
    deck = await get_deck(deck_id)
    cards = await get_deck_card_images(deck_id)
    slots = _expand_slots(cards)

    if not slots:
        raise HTTPException(status_code=400, detail="No card images to export")

    total = len(slots)
    filename = f"{deck['name']}_cards.pdf"

    async def event_stream():
        _cleanup_export_cache()

        sem = asyncio.Semaphore(10)
        image_data_list: list[bytes | None] = [None] * total
        progress_queue: asyncio.Queue[int | None] = asyncio.Queue()

        async def fetch_one(client: httpx.AsyncClient, url: str, idx: int):
            async with sem:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        image_data_list[idx] = resp.content
                except Exception as e:
                    logger.warning("Failed to download %s: %s", url, e)
            await progress_queue.put(idx)

        async def download_all():
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                tasks = [fetch_one(client, url, i) for i, (_, url) in enumerate(slots)]
                await asyncio.gather(*tasks)
            await progress_queue.put(None)

        dl_task = asyncio.create_task(download_all())

        completed = 0
        while True:
            idx = await progress_queue.get()
            if idx is None:
                break
            completed += 1
            yield f"data: {json.dumps({'type': 'progress', 'phase': 'download', 'current': completed, 'total': total})}\n\n"

        await dl_task

        yield f"data: {json.dumps({'type': 'progress', 'phase': 'pdf', 'current': total, 'total': total})}\n\n"

        pdf_buf = await asyncio.to_thread(_build_pdf, image_data_list)

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
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# ── Admin Router ───────────────────────────────────────────────────────

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


class UpdateRoleRequest(BaseModel):
    role: str


@admin_router.get("/users")
async def admin_list_users(_: str = Depends(require_admin)):
    return await list_all_users()


@admin_router.put("/users/{user_id}/role")
async def admin_update_role(user_id: str, req: UpdateRoleRequest, admin_id: str = Depends(require_admin)):
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
    result = await update_user_role(user_id, req.role)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@admin_router.delete("/users/{user_id}", status_code=204)
async def admin_delete_user(user_id: str, admin_id: str = Depends(require_admin)):
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    await delete_user(user_id)
