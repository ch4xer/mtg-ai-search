"""Image slot expansion and concurrent download helpers for deck exports."""

import asyncio
import logging
from collections.abc import AsyncIterator
from time import perf_counter

import httpx

logger = logging.getLogger(__name__)

ImageSlot = tuple[str, str]
DownloadEvent = tuple[dict, list[bytes | None] | None, list[int] | None]


def expand_card_image_slots(cards: list[dict]) -> list[ImageSlot]:
    slots: list[ImageSlot] = []
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
    success_count = 0
    failed_count = 0
    logger.info(
        "[deck-export] image download start unique=%d slots=%d concurrency=10",
        unique_count,
        len(slots),
    )

    async def fetch_one(client: httpx.AsyncClient, url: str, uid: int):
        nonlocal downloaded_bytes, failed_count, success_count
        async with sem:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    content = resp.content
                    unique_data[uid] = content
                    downloaded_bytes += len(content)
                    success_count += 1
                else:
                    failed_count += 1
                    logger.warning("Failed to download %s: HTTP %d", url, resp.status_code)
            except Exception as exc:
                failed_count += 1
                logger.warning("Failed to download %s: %s", url, exc)
        await progress_queue.put(uid)

    async def download_all():
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            await asyncio.gather(*(fetch_one(client, url, i) for i, url in enumerate(unique_url_list)))
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
    logger.info(
        "[deck-export] image download complete unique=%d success=%d failed=%d bytes=%.2fMiB took %.2fs",
        unique_count,
        success_count,
        failed_count,
        downloaded_bytes / (1024 * 1024),
        perf_counter() - started,
    )
    yield {}, unique_data, slot_url_index
