"""Short-lived in-memory export cache."""

import time
from uuid import uuid4

from fastapi import HTTPException

ExportCache = dict[str, tuple[bytes, str, float]]

EXPORT_CACHE_TTL = 300


def put_export(cache: ExportCache, data: bytes, filename: str) -> str:
    cleanup_exports(cache)
    export_id = str(uuid4())
    cache[export_id] = (data, filename, time.time())
    return export_id


def pop_export(cache: ExportCache, export_id: str) -> tuple[bytes, str]:
    entry = cache.pop(export_id, None)
    if not entry:
        raise HTTPException(status_code=404, detail="Export not found or expired")
    data, filename, _ = entry
    return data, filename


def cleanup_exports(cache: ExportCache) -> None:
    now = time.time()
    expired = [key for key, value in cache.items() if now - value[2] > EXPORT_CACHE_TTL]
    for key in expired:
        del cache[key]

