import asyncio
import logging

import requests

from .repositories.database import get_pool
from .services.task_progress import StatusCallback, emit_status

logger = logging.getLogger(__name__)


async def seed_cards_if_empty() -> None:
    pool = await get_pool()
    try:
        count = await pool.fetchval("SELECT COUNT(*) FROM cards")
    except Exception:
        count = 0

    if count > 0:
        logger.info("Database has %d cards, skipping seed.", count)
        return

    logger.info("No card data found. Running seed.")
    await full_reseed()
    logger.info("Seed complete.")


async def full_reseed(status_callback: StatusCallback = None) -> int:
    """Rebuild local card and printing data from the configured Scryfall bulk file."""
    def _do_reseed() -> None:
        from scripts.seed_pg import (
            create_schema,
            get_conn,
            insert_cards_and_prints,
        )

        conn = get_conn()
        try:
            create_schema(conn)

            logger.info("[reseed] Clearing existing card data...")
            with conn.cursor() as cur:
                cur.execute("DELETE FROM deck_cards")
                cur.execute("DELETE FROM card_prints")
                cur.execute("DELETE FROM cards")
            conn.commit()

            emit_status(status_callback, "正在下载并导入 Scryfall 数据...")
            insert_cards_and_prints(conn)
        finally:
            conn.close()

    await asyncio.to_thread(_do_reseed)
    pool = await get_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM cards")
    logger.info("[reseed] Complete. %d cards in database.", count)
    return count


def _get_scryfall_bulk_updated_at() -> str | None:
    """Fetch the updated_at timestamp of the configured Scryfall bulk data."""
    try:
        from app.data_loader import BULK_DATA_TYPE

        resp = requests.get("https://api.scryfall.com/bulk-data", timeout=15)
        resp.raise_for_status()
        for entry in resp.json()["data"]:
            if entry["type"] == BULK_DATA_TYPE:
                return entry["updated_at"]
    except Exception as e:
        logger.warning("[sync] Failed to check Scryfall bulk data: %s", e)
    return None


async def incremental_sync(status_callback: StatusCallback = None, force: bool = False) -> dict:
    """Download Scryfall all_cards data, upsert cards and prints.

    If force=True, skip the timestamp check and always sync.

    Returns {"new_cards": int, "updated_cards": int, "new_prints": int, "skipped": bool}.
    """
    pool = await get_pool()

    # Check if Scryfall data has been updated since our last sync (skip if force)
    if not force:
        remote_updated = _get_scryfall_bulk_updated_at()
        if not remote_updated:
            logger.warning("[sync] Could not determine Scryfall update time, skipping.")
            await _write_sync_log(pool, "skipped", message="无法获取 Scryfall 更新时间")
            return {"new_cards": 0, "updated_cards": 0, "new_prints": 0, "skipped": True}

        last_sync = await pool.fetchval(
            "SELECT value FROM app_meta WHERE key = 'last_sync_updated_at'"
        )
        if last_sync == remote_updated:
            logger.info("[sync] Scryfall data unchanged (updated_at=%s), skipping.", remote_updated)
            await _write_sync_log(pool, "skipped", message="Scryfall 数据无变更")
            return {"new_cards": 0, "updated_cards": 0, "new_prints": 0, "skipped": True}

        logger.info("[sync] Scryfall data updated (%s -> %s), syncing...", last_sync, remote_updated)
    else:
        logger.info("[sync] Force sync requested, skipping timestamp check.")
        remote_updated = _get_scryfall_bulk_updated_at() or "unknown"

    log_id = await _write_sync_log(pool, "running", message="正在同步...")

    stats: dict[str, int] = {"new_cards": 0, "updated_cards": 0, "new_prints": 0}

    try:
        def _do_sync() -> None:
            from scripts.seed_pg import (
                get_conn,
                insert_cards_and_prints,
            )

            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM cards")
                    cards_before = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM card_prints")
                    prints_before = cur.fetchone()[0]

                emit_status(status_callback, "正在下载并同步卡牌数据...")
                insert_cards_and_prints(conn)

                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM cards")
                    cards_after = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM card_prints")
                    prints_after = cur.fetchone()[0]
                conn.commit()

                stats["new_cards"] = cards_after - cards_before
                stats["new_prints"] = prints_after - prints_before
                stats["updated_cards"] = 0
                emit_status(status_callback, "数据已更新")
            finally:
                conn.close()

        await asyncio.to_thread(_do_sync)

        await pool.execute(
            """INSERT INTO app_meta (key, value) VALUES ('last_sync_updated_at', $1)
               ON CONFLICT (key) DO UPDATE SET value = $1""",
            remote_updated,
        )

        new_cards = stats["new_cards"]
        updated_cards = stats["updated_cards"]
        new_prints = stats["new_prints"]
        message = f"新增 {new_cards} 张卡牌，{new_prints} 个版本，更新 {updated_cards} 张" if (new_cards or updated_cards or new_prints) else "数据已同步（无变更）"
        await _update_sync_log(pool, log_id, "done", new_cards, updated_cards, message)
        logger.info("[sync] Complete. %d new cards, %d new prints, %d updated.", new_cards, new_prints, updated_cards)
        return {"new_cards": new_cards, "updated_cards": updated_cards, "new_prints": new_prints, "skipped": False}

    except Exception as e:
        logger.exception("[sync] Failed")
        await _update_sync_log(pool, log_id, "error", 0, 0, f"同步失败: {e}")
        raise


async def _write_sync_log(pool, status: str, *, message: str = "") -> str:
    """Insert a sync log entry and return its ID."""
    row = await pool.fetchrow(
        """INSERT INTO sync_logs (status, message) VALUES ($1, $2) RETURNING id""",
        status, message,
    )
    return str(row["id"])

async def _update_sync_log(
    pool, log_id: str, status: str, new_cards: int, updated_cards: int, message: str,
) -> None:
    """Update an existing sync log entry."""
    await pool.execute(
        """UPDATE sync_logs
           SET status = $1, new_cards = $2, updated_cards = $3,
               message = $4, completed_at = now()
           WHERE id = $5::uuid""",
        status, new_cards, updated_cards, message, log_id,
    )
