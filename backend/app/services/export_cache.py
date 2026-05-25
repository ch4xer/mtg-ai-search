"""Short-lived in-memory export cache."""

import os
import time
from uuid import uuid4

from fastapi import HTTPException

ExportCache = dict[str, tuple[bytes, str, float]]


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


EXPORT_CACHE_TTL = max(300, _int_env("MTG_EXPORT_CACHE_TTL_SECONDS", 12 * 60 * 60))


def put_export(cache: ExportCache, data: bytes, filename: str) -> str:
    cleanup_exports(cache)
    export_id = str(uuid4())
    cache[export_id] = (data, filename, time.time())
    return export_id


def get_export(cache: ExportCache, export_id: str) -> tuple[bytes, str]:
    cleanup_exports(cache)
    entry = cache.get(export_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Export not found or expired")
    data, filename, _ = entry
    cache[export_id] = (data, filename, time.time())
    return data, filename


def cleanup_exports(cache: ExportCache) -> None:
    now = time.time()
    expired = [key for key, value in cache.items() if now - value[2] > EXPORT_CACHE_TTL]
    for key in expired:
        del cache[key]
