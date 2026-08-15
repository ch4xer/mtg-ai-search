"""MTGCH Chinese card metadata synchronization."""

import asyncio
import json
import logging
import os
import time
from typing import Any

import httpx

from ..config import USER_AGENT
from ..repositories.database import get_pool
from .task_progress import StatusCallback, emit_status

logger = logging.getLogger(__name__)

MTGCH_API_BASE_URL = os.getenv("MTGCH_API_BASE_URL", "https://mtgch.com/api/v1").rstrip("/")
MTGCH_API_TIMEOUT_SECONDS = float(os.getenv("MTGCH_API_TIMEOUT_SECONDS", "4"))
MTGCH_API_CONCURRENCY = max(1, int(os.getenv("MTGCH_API_CONCURRENCY", "1")))
MTGCH_REQUEST_DELAY_SECONDS = max(0.0, float(os.getenv("MTGCH_REQUEST_DELAY_SECONDS", "0.5")))
MTGCH_MAX_RETRIES = max(0, int(os.getenv("MTGCH_MAX_RETRIES", "5")))
MTGCH_RETRY_BASE_SECONDS = max(0.5, float(os.getenv("MTGCH_RETRY_BASE_SECONDS", "2")))
MTGCH_RETRY_MAX_SECONDS = max(MTGCH_RETRY_BASE_SECONDS, float(os.getenv("MTGCH_RETRY_MAX_SECONDS", "120")))
MTGCH_SYNC_ENABLED = os.getenv("MTGCH_SYNC_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
MTGCH_SYNC_BATCH_SIZE = max(1, int(os.getenv("MTGCH_SYNC_BATCH_SIZE", "100")))


class _MtgchThrottle:
    def __init__(self, min_interval_seconds: float) -> None:
        self._min_interval_seconds = min_interval_seconds
        self._next_request_at = 0.0
        self._lock = asyncio.Lock()

    async def wait_for_slot(self) -> None:
        if self._min_interval_seconds <= 0:
            return

        async with self._lock:
            now = time.monotonic()
            if self._next_request_at > now:
                await asyncio.sleep(self._next_request_at - now)
            self._next_request_at = time.monotonic() + self._min_interval_seconds

    async def cool_down(self, seconds: float) -> None:
        if seconds <= 0:
            return

        async with self._lock:
            self._next_request_at = max(self._next_request_at, time.monotonic() + seconds)


async def sync_mtgch_translations(
    *,
    status_callback: StatusCallback = None,
    force: bool = False,
    limit: int | None = None,
) -> dict[str, int | bool]:
    """Fetch MTGCH Chinese metadata for local default prints and persist it."""
    if not MTGCH_SYNC_ENABLED:
        return _empty_result(skipped=True)

    requested_limit = max(0, limit or 0)
    print_rows = await _select_prints_for_translation(force=force, limit=requested_limit)
    total = len(print_rows)
    if total == 0:
        emit_status(status_callback, "中文卡牌信息已是最新")
        return _empty_result(skipped=False)

    emit_status(status_callback, f"正在同步中文卡牌信息（0/{total}）...")
    stats = {
        "requested": total,
        "synced": 0,
        "empty": 0,
        "not_found": 0,
        "failed": 0,
        "skipped": False,
    }

    timeout = httpx.Timeout(MTGCH_API_TIMEOUT_SECONDS, connect=min(2.0, MTGCH_API_TIMEOUT_SECONDS))
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    semaphore = asyncio.Semaphore(MTGCH_API_CONCURRENCY)
    throttle = _MtgchThrottle(MTGCH_REQUEST_DELAY_SECONDS)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        async def fetch_with_limit(row: dict[str, str]) -> dict[str, Any]:
            async with semaphore:
                return await _fetch_translation_row(client, row, throttle)

        for start in range(0, total, MTGCH_SYNC_BATCH_SIZE):
            batch = print_rows[start : start + MTGCH_SYNC_BATCH_SIZE]
            results = await asyncio.gather(*(fetch_with_limit(row) for row in batch))
            persistable = [result for result in results if result["status"] != "failed"]
            if persistable:
                await _upsert_translation_rows(persistable)

            for result in results:
                status = result["status"]
                if status == "ok":
                    stats["synced"] += 1
                elif status == "empty":
                    stats["empty"] += 1
                elif status == "not_found":
                    stats["not_found"] += 1
                else:
                    stats["failed"] += 1

            done = min(start + len(batch), total)
            emit_status(
                status_callback,
                f"正在同步中文卡牌信息（{done}/{total}，成功 {stats['synced']}，失败 {stats['failed']}）...",
            )

    logger.info(
        "[mtgch] Translation sync complete: requested=%d synced=%d empty=%d not_found=%d failed=%d",
        stats["requested"],
        stats["synced"],
        stats["empty"],
        stats["not_found"],
        stats["failed"],
    )
    return stats


async def _select_prints_for_translation(*, force: bool, limit: int) -> list[dict[str, str]]:
    pool = await get_pool()
    params: list[Any] = [force]
    limit_clause = ""
    if limit > 0:
        params.append(limit)
        limit_clause = f"LIMIT ${len(params)}"

    sql = f"""
        WITH default_prints AS (
            SELECT DISTINCT ON (card_id)
                   id AS print_id, card_id, released_at
            FROM card_prints
            ORDER BY card_id, released_at DESC NULLS LAST, id
        )
        SELECT dp.print_id, dp.card_id
        FROM default_prints dp
        LEFT JOIN card_print_translations zt
          ON zt.print_id = dp.print_id
         AND zt.lang = 'zhs'
        WHERE $1::boolean OR zt.print_id IS NULL
        ORDER BY dp.released_at DESC NULLS LAST, dp.print_id
        {limit_clause}
    """

    rows = await pool.fetch(sql, *params)
    return [{"print_id": row["print_id"], "card_id": row["card_id"]} for row in rows]


async def _fetch_translation_row(
    client: httpx.AsyncClient,
    row: dict[str, str],
    throttle: _MtgchThrottle,
) -> dict[str, Any]:
    print_id = row["print_id"]
    for attempt in range(MTGCH_MAX_RETRIES + 1):
        try:
            await throttle.wait_for_slot()
            response = await client.get(f"{MTGCH_API_BASE_URL}/card/{print_id}/", params={"view": 0})
            if response.status_code == 404:
                return _translation_row(row, status="not_found")
            if response.status_code == 429:
                retry_after = _retry_after_seconds(response, attempt)
                await throttle.cool_down(retry_after)
                if attempt < MTGCH_MAX_RETRIES:
                    logger.info("MTGCH rate limited; retrying print %s after %.1fs", print_id, retry_after)
                    continue
                return _translation_row(row, status="failed", last_error="MTGCH rate limited after retries")

            response.raise_for_status()
            translation = _normalize_mtgch_card(response.json())
            if translation is None:
                return _translation_row(row, status="empty")
            return _translation_row(row, status="ok", translation=translation)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            if attempt < MTGCH_MAX_RETRIES:
                retry_after = _retry_after_seconds(None, attempt)
                await throttle.cool_down(retry_after)
                logger.info("MTGCH transient fetch error for print %s; retrying after %.1fs: %s", print_id, retry_after, exc)
                continue
            logger.info("MTGCH translation fetch failed for print %s: %s", print_id, exc)
            return _translation_row(row, status="failed", last_error=str(exc)[:500])
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.info("MTGCH translation fetch failed for print %s: %s", print_id, exc)
            return _translation_row(row, status="failed", last_error=str(exc)[:500])

    return _translation_row(row, status="failed", last_error="MTGCH fetch failed")


def _retry_after_seconds(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        raw_retry_after = response.headers.get("Retry-After")
        if raw_retry_after:
            try:
                return min(MTGCH_RETRY_MAX_SECONDS, max(1.0, float(raw_retry_after)))
            except ValueError:
                pass
    return min(MTGCH_RETRY_MAX_SECONDS, MTGCH_RETRY_BASE_SECONDS * (2 ** attempt))


def _translation_row(
    row: dict[str, str],
    *,
    status: str,
    translation: dict[str, Any] | None = None,
    last_error: str = "",
) -> dict[str, Any]:
    translation = translation or {}
    return {
        "print_id": row["print_id"],
        "card_id": row["card_id"],
        "status": status,
        "name": translation.get("name"),
        "type_line": translation.get("type_line"),
        "oracle_text": translation.get("oracle_text"),
        "flavor_text": translation.get("flavor_text"),
        "set_name": translation.get("set_name"),
        "card_faces": translation.get("card_faces"),
        "last_error": last_error,
    }


async def _upsert_translation_rows(rows: list[dict[str, Any]]) -> None:
    pool = await get_pool()
    values = [
        (
            row["print_id"],
            row["card_id"],
            "zhs",
            "mtgch",
            row["status"],
            row["name"],
            row["type_line"],
            row["oracle_text"],
            row["flavor_text"],
            row["set_name"],
            json.dumps(row["card_faces"], ensure_ascii=False) if row["card_faces"] else None,
            row["last_error"],
        )
        for row in rows
    ]
    async with pool.acquire() as conn:
        await conn.executemany(
            """INSERT INTO card_print_translations (
                   print_id, card_id, lang, source, status,
                   name, type_line, oracle_text, flavor_text, set_name,
                   card_faces, last_error
               ) VALUES (
                   $1, $2, $3, $4, $5,
                   $6, $7, $8, $9, $10,
                   $11::jsonb, $12
               )
               ON CONFLICT (print_id) DO UPDATE SET
                   card_id = EXCLUDED.card_id,
                   lang = EXCLUDED.lang,
                   source = EXCLUDED.source,
                   status = EXCLUDED.status,
                   name = EXCLUDED.name,
                   type_line = EXCLUDED.type_line,
                   oracle_text = EXCLUDED.oracle_text,
                   flavor_text = EXCLUDED.flavor_text,
                   set_name = EXCLUDED.set_name,
                   card_faces = EXCLUDED.card_faces,
                   synced_at = now(),
                   last_error = EXCLUDED.last_error""",
            values,
        )


def _empty_result(*, skipped: bool) -> dict[str, int | bool]:
    return {
        "requested": 0,
        "synced": 0,
        "empty": 0,
        "not_found": 0,
        "failed": 0,
        "skipped": skipped,
    }


def _normalize_mtgch_card(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    raw_faces = _ordered_faces(payload)
    faces = [_normalize_mtgch_face(face) for face in raw_faces]
    faces = [face for face in faces if _has_translation(face)]
    if not faces:
        return None

    return {
        "source": "mtgch",
        "name": _join_face_field(faces, "name"),
        "type_line": _join_face_field(faces, "type_line"),
        "oracle_text": _join_face_field(faces, "oracle_text", separator="\n//\n"),
        "flavor_text": _join_face_field(faces, "flavor_text", separator="\n//\n"),
        "set_name": _clean_text(payload.get("set_translated_name")),
        "card_faces": faces,
    }


def _ordered_faces(payload: dict[str, Any]) -> list[dict[str, Any]]:
    faces = [payload]
    other_faces = payload.get("other_faces")
    if isinstance(other_faces, list):
        faces.extend(face for face in other_faces if isinstance(face, dict))

    def face_sort_key(face: dict[str, Any]) -> int:
        face_index = face.get("face_index")
        return face_index if isinstance(face_index, int) and face_index >= 0 else 0

    return sorted(faces, key=face_sort_key)


def _normalize_mtgch_face(face: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _translated_name(face),
        "type_line": _translated_field(face, "zhs_type_line", "atomic_translated_type"),
        "oracle_text": _translated_field(face, "zhs_text", "atomic_translated_text"),
        "flavor_text": _translated_field(face, "zhs_flavor_text", "atomic_translated_flavor_text"),
        "set_name": _clean_text(face.get("set_translated_name")),
    }


def _translated_name(face: dict[str, Any]) -> str | None:
    return _first_text(
        face,
        "zhs_face_name",
        "atomic_official_name",
        "atomic_translated_name",
        "zhs_name",
        "full_official_name",
        "full_translated_name",
    )


def _translated_field(face: dict[str, Any], official_key: str, translated_key: str) -> str | None:
    official = _clean_text(face.get(official_key))
    translated = _clean_text(face.get(translated_key))
    if official and (_contains_cjk(official) or not translated):
        return official
    return translated or official


def _first_text(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _clean_text(data.get(key))
        if value:
            return value
    return None


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.replace("\\n", "\n").strip()
    return value or None


def _join_face_field(faces: list[dict[str, Any]], field: str, separator: str = " // ") -> str | None:
    values = [face.get(field) for face in faces if face.get(field)]
    if not values:
        return None
    return separator.join(values)


def _has_translation(face: dict[str, Any]) -> bool:
    return any(face.get(field) for field in ("name", "type_line", "oracle_text", "flavor_text"))


def _contains_cjk(value: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" for char in value)
