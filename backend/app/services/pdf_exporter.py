"""PDF deck image export builder."""

import io

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

CARD_W = 2.5 * inch
CARD_H = 3.5 * inch
COLS, ROWS = 3, 3
CARDS_PER_PAGE = COLS * ROWS
FIX_W = 0
FIX_H = 0


def build_pdf(unique_data: list[bytes | None], slot_url_index: list[int]) -> io.BytesIO:
    page_w, page_h = A4
    grid_w = COLS * CARD_W + (COLS - 1) * FIX_W
    grid_h = ROWS * CARD_H + (ROWS - 1) * FIX_H
    x_offset = (page_w - grid_w) / 2
    y_offset = (page_h - grid_h) / 2

    def draw_card_background(c, x: float, y: float):
        c.saveState()
        c.setFillColorRGB(0, 0, 0)
        c.rect(x, y, CARD_W, CARD_H, stroke=0, fill=1)
        c.restoreState()

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

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    slot_index = 0
    for uid in slot_url_index:
        if uid not in readers:
            slot_index += 1
            continue
        pos = slot_index % CARDS_PER_PAGE
        if pos == 0 and slot_index > 0:
            c.showPage()
        col = pos % COLS
        row = pos // COLS
        x = x_offset + col * (CARD_W + FIX_W)
        y = page_h - y_offset - (row + 1) * CARD_H - row * FIX_H
        draw_card_background(c, x, y)
        c.drawImage(readers[uid], x, y, width=CARD_W, height=CARD_H, preserveAspectRatio=True)
        slot_index += 1

    c.save()
    buf.seek(0)
    return buf
