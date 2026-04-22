"""ZIP deck image export builder."""

import io
import re
import zipfile

from .image_download_service import ImageSlot


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name).strip(". ")
    if len(name) > 200:
        name = name[:200]
    return name or "card"


def build_zip(unique_data: list[bytes | None], slots: list[ImageSlot], slot_url_index: list[int]) -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        filename_counts: dict[str, int] = {}
        for slot_idx, (card_name, _) in enumerate(slots):
            uid = slot_url_index[slot_idx]
            if uid >= len(unique_data) or unique_data[uid] is None:
                continue

            safe_name = sanitize_filename(card_name)
            if safe_name in filename_counts:
                filename_counts[safe_name] += 1
                base_name = safe_name
                for i in range(2, filename_counts[safe_name] + 10):
                    candidate = f"{base_name}_{i}"
                    if candidate not in filename_counts:
                        safe_name = candidate
                        filename_counts[candidate] = 1
                        break
            else:
                filename_counts[safe_name] = 1

            zf.writestr(f"{safe_name}.png", unique_data[uid])
    buf.seek(0)
    return buf

