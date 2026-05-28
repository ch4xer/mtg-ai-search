"""Image slot expansion and concurrent download helpers for deck exports."""

import asyncio
import hashlib
import logging
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from time import perf_counter, time, time_ns

import httpx

logger = logging.getLogger(__name__)

ImageSlot = tuple[str, str]
DownloadEvent = tuple[dict, list[bytes | None] | None, list[int] | None]


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


IMAGE_CACHE_DIR = Path(os.environ.get("MTG_IMAGE_CACHE_DIR", Path(tempfile.gettempdir()) / "mtg-ai-search-image-cache"))
IMAGE_CACHE_TTL_SECONDS = _int_env("MTG_IMAGE_CACHE_TTL_SECONDS", 7 * 24 * 60 * 60)
IMAGE_CACHE_MAX_BYTES = _int_env("MTG_IMAGE_CACHE_MAX_BYTES", 512 * 1024 * 1024)
IMAGE_CACHE_CLEANUP_INTERVAL = 60
DOWNLOAD_RETRIES = 3
DOWNLOAD_RETRY_BASE_DELAY = 0.5
_image_cache_cleanup_lock = asyncio.Lock()
_image_cache_last_cleanup = 0.0


def expand_card_image_slots(cards: list[dict]) -> list[ImageSlot]:
    slots: list[ImageSlot] = []
    for card in cards:
        url = card.get("png_url")
        if url:
            for _ in range(card["quantity"]):
                slots.append((card["name"], url))
        back_url = card.get("back_png_url")
        if back_url:
            back_name = card.get("back_name") or card["name"] + " (Back)"
            for _ in range(card["quantity"]):
                slots.append((back_name, back_url))
    return slots


def _image_cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return IMAGE_CACHE_DIR / f"{digest}.img"


def _read_cached_image(url: str) -> bytes | None:
    path = _image_cache_path(url)
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    except OSError:
        return None

    if IMAGE_CACHE_TTL_SECONDS > 0 and time() - stat.st_mtime > IMAGE_CACHE_TTL_SECONDS:
        try:
            path.unlink()
        except OSError:
            pass
        return None

    try:
        data = path.read_bytes()
        os.utime(path, None)
        return data
    except OSError:
        return None


def _write_cached_image(url: str, content: bytes) -> None:
    if not content or IMAGE_CACHE_MAX_BYTES <= 0:
        return

    path = _image_cache_path(url)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{time_ns()}.tmp")
    try:
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(content)
        os.replace(tmp_path, path)
    except OSError:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def _cleanup_image_cache() -> None:
    if IMAGE_CACHE_MAX_BYTES <= 0:
        return

    try:
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    now_ts = time()
    entries: list[tuple[Path, int, float]] = []
    for path in IMAGE_CACHE_DIR.glob("*.img"):
        try:
            stat = path.stat()
        except OSError:
            continue

        if IMAGE_CACHE_TTL_SECONDS > 0 and now_ts - stat.st_mtime > IMAGE_CACHE_TTL_SECONDS:
            try:
                path.unlink()
            except OSError:
                pass
            continue

        entries.append((path, stat.st_size, stat.st_mtime))

    total_bytes = sum(size for _, size, _ in entries)
    if total_bytes <= IMAGE_CACHE_MAX_BYTES:
        return

    for path, size, _ in sorted(entries, key=lambda item: item[2]):
        try:
            path.unlink()
            total_bytes -= size
        except OSError:
            pass
        if total_bytes <= IMAGE_CACHE_MAX_BYTES:
            break


async def _cleanup_image_cache_if_needed() -> None:
    global _image_cache_last_cleanup

    now_ts = time()
    if now_ts - _image_cache_last_cleanup < IMAGE_CACHE_CLEANUP_INTERVAL:
        return

    async with _image_cache_cleanup_lock:
        now_ts = time()
        if now_ts - _image_cache_last_cleanup < IMAGE_CACHE_CLEANUP_INTERVAL:
            return
        await asyncio.to_thread(_cleanup_image_cache)
        _image_cache_last_cleanup = now_ts


async def download_unique_images(slots: list[ImageSlot]) -> AsyncIterator[DownloadEvent]:
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
    started = perf_counter()
    downloaded_bytes = 0
    cached_bytes = 0
    success_count = 0
    cache_hit_count = 0
    failed_count = 0
    logger.info(
        "[deck-export] image download start unique=%d slots=%d concurrency=10",
        unique_count,
        len(slots),
    )

    async def download_url(client: httpx.AsyncClient, url: str) -> bytes | None:
        for attempt in range(DOWNLOAD_RETRIES):
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.content
                if resp.status_code < 500:
                    logger.warning("Failed to download %s: HTTP %d", url, resp.status_code)
                    break
                logger.warning("Failed to download %s: HTTP %d attempt=%d", url, resp.status_code, attempt + 1)
            except Exception as exc:
                logger.warning("Failed to download %s: %s attempt=%d", url, exc, attempt + 1)
            if attempt < DOWNLOAD_RETRIES - 1:
                await asyncio.sleep(DOWNLOAD_RETRY_BASE_DELAY * (attempt + 1))
        return None

    async def fetch_one(client: httpx.AsyncClient, url: str, uid: int):
        nonlocal cached_bytes, cache_hit_count, downloaded_bytes, failed_count, success_count
        cached = await asyncio.to_thread(_read_cached_image, url)
        if cached is not None:
            unique_data[uid] = cached
            cached_bytes += len(cached)
            cache_hit_count += 1
            await progress_queue.put(uid)
            return

        async with sem:
            content = await download_url(client, url)
            if content is None:
                failed_count += 1
                await progress_queue.put(uid)
                return

            unique_data[uid] = content
            downloaded_bytes += len(content)
            success_count += 1
            await asyncio.to_thread(_write_cached_image, url, content)
        await progress_queue.put(uid)

    async def download_all():
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            await asyncio.gather(*(fetch_one(client, url, i) for i, url in enumerate(unique_url_list)))
        await _cleanup_image_cache_if_needed()
        await progress_queue.put(None)

    download_task = asyncio.create_task(download_all())
    completed = 0
    while True:
        idx = await progress_queue.get()
        if idx is None:
            break
        completed += 1
        yield {"type": "progress", "phase": "download", "current": completed, "total": unique_count}, None, None

    await download_task
    missing_count = sum(1 for data in unique_data if data is None)
    logger.info(
        "[deck-export] image download complete unique=%d success=%d cache_hits=%d failed=%d missing=%d downloaded=%.2fMiB cached=%.2fMiB took=%.2fs",
        unique_count,
        success_count,
        cache_hit_count,
        failed_count,
        missing_count,
        downloaded_bytes / (1024 * 1024),
        cached_bytes / (1024 * 1024),
        perf_counter() - started,
    )
    yield {}, unique_data, slot_url_index
