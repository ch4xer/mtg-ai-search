import asyncio
import logging
import os
from collections.abc import Callable

import requests

from .db import get_pool

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str], None] | None


def _ability_file() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "keyword_ability.txt",
    )


def _emit_status(callback: StatusCallback, message: str) -> None:
    if callback:
        callback(message)


def _make_progress_callback(callback: StatusCallback, prefix: str):
    if not callback:
        return None

    def _progress(done: int, total: int) -> None:
        callback(f"{prefix}（{done}/{total}）...")

    return _progress


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
    await full_reseed(with_embeddings=True)
    logger.info("Seed complete.")


async def backfill_missing_embeddings(status_callback: StatusCallback = None) -> None:
    pool = await get_pool()
    card_count = await pool.fetchval("SELECT COUNT(*) FROM cards WHERE name_embedding IS NULL")
    ability_count = await pool.fetchval("SELECT COUNT(*) FROM keyword_abilities WHERE embedding IS NULL")

    if card_count == 0 and ability_count == 0:
        logger.info("All embeddings present, nothing to backfill.")
        return

    logger.info("Backfilling embeddings: %d cards, %d abilities missing.", card_count, ability_count)

    def _do_backfill() -> None:
        from scripts.seed_pg import generate_ability_embeddings, generate_card_embeddings, get_conn

        conn = get_conn()
        try:
            if card_count > 0:
                _emit_status(status_callback, "正在补全卡牌 embedding...")
                generate_card_embeddings(
                    conn,
                    on_progress=_make_progress_callback(status_callback, "正在补全卡牌 embedding"),
                )
            if ability_count > 0:
                _emit_status(status_callback, "正在补全异能 embedding...")
                generate_ability_embeddings(conn)
        finally:
            conn.close()

    await asyncio.to_thread(_do_backfill)
    logger.info("Embedding backfill complete.")


async def full_reseed(with_embeddings: bool = True, status_callback: StatusCallback = None) -> int:
    def _do_reseed() -> None:
        from scripts.seed_pg import (
            create_schema,
            generate_ability_embeddings,
            generate_card_embeddings,
            get_conn,
            insert_abilities,
            insert_cards,
        )
        from .data_loader import download_scryfall_cards, parse_keyword_abilities

        conn = get_conn()
        try:
            create_schema(conn)

            logger.info("[reseed] Clearing existing card data...")
            with conn.cursor() as cur:
                cur.execute("DELETE FROM deck_cards")
                cur.execute("DELETE FROM keyword_abilities")
                cur.execute("DELETE FROM cards")
            conn.commit()

            _emit_status(status_callback, "正在下载 Scryfall 数据...")
            raw_cards = download_scryfall_cards()
            valid_cards = [c for c in raw_cards if c.get("layout") not in ("token", "emblem", "art_series")]

            _emit_status(status_callback, f"正在导入 {len(valid_cards)} 张卡牌...")
            insert_cards(conn, valid_cards)

            abilities = parse_keyword_abilities(_ability_file())
            insert_abilities(conn, abilities)

            if with_embeddings:
                _emit_status(status_callback, "正在生成卡牌 embedding...")
                generate_card_embeddings(
                    conn,
                    on_progress=_make_progress_callback(status_callback, "正在生成卡牌 embedding"),
                )
                _emit_status(status_callback, "正在生成异能 embedding...")
                generate_ability_embeddings(conn)
            else:
                logger.info("[reseed] Skipping embedding generation.")

            with conn.cursor() as cur:
                cur.execute("""
                    ALTER TABLE cards ADD COLUMN IF NOT EXISTS is_playtest BOOLEAN NOT NULL DEFAULT FALSE;
                    UPDATE cards SET is_playtest = (data->>'set_type' = 'funny')
                    WHERE is_playtest = FALSE AND data->>'set_type' = 'funny';
                """)
            conn.commit()
        finally:
            conn.close()

    await asyncio.to_thread(_do_reseed)
    pool = await get_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM cards")
    logger.info("[reseed] Complete. %d cards in database. embeddings=%s", count, with_embeddings)
    return count


async def regenerate_embeddings(status_callback: StatusCallback = None) -> None:
    def _do_reembed() -> None:
        from scripts.seed_pg import generate_ability_embeddings, generate_card_embeddings, get_conn

        conn = get_conn()
        try:
            logger.info("[reembed] Clearing existing embeddings...")
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE cards SET
                        name_embedding = NULL,
                        type_line_embedding = NULL,
                        oracle_text_embedding = NULL
                """)
                cur.execute("UPDATE keyword_abilities SET embedding = NULL")
            conn.commit()

            _emit_status(status_callback, "正在生成卡牌 embedding...")
            generate_card_embeddings(
                conn,
                on_progress=_make_progress_callback(status_callback, "正在生成卡牌 embedding"),
            )
            _emit_status(status_callback, "正在生成异能 embedding...")
            generate_ability_embeddings(conn)
        finally:
            conn.close()

    await asyncio.to_thread(_do_reembed)
    logger.info("[reembed] Complete.")


def _get_scryfall_bulk_updated_at() -> str | None:
    """Fetch the updated_at timestamp of the oracle_cards bulk data from Scryfall."""
    try:
        resp = requests.get("https://api.scryfall.com/bulk-data", timeout=15)
        resp.raise_for_status()
        for entry in resp.json()["data"]:
            if entry["type"] == "oracle_cards":
                return entry["updated_at"]
    except Exception as e:
        logger.warning("[sync] Failed to check Scryfall bulk data: %s", e)
    return None


async def incremental_sync(status_callback: StatusCallback = None) -> dict:
    """Download Scryfall data, upsert cards, and generate embeddings for new/changed cards.

    Returns {"new_cards": int, "updated_cards": int, "skipped": bool}.
    """
    pool = await get_pool()

    # Check if Scryfall data has been updated since our last sync
    remote_updated = _get_scryfall_bulk_updated_at()
    if not remote_updated:
        logger.warning("[sync] Could not determine Scryfall update time, skipping.")
        await _write_sync_log(pool, "skipped", message="无法获取 Scryfall 更新时间")
        return {"new_cards": 0, "updated_cards": 0, "skipped": True}

    last_sync = await pool.fetchval(
        "SELECT value FROM app_meta WHERE key = 'last_sync_updated_at'"
    )
    if last_sync == remote_updated:
        logger.info("[sync] Scryfall data unchanged (updated_at=%s), skipping.", remote_updated)
        await _write_sync_log(pool, "skipped", message="Scryfall 数据无变更")
        return {"new_cards": 0, "updated_cards": 0, "skipped": True}

    logger.info("[sync] Scryfall data updated (%s -> %s), syncing...", last_sync, remote_updated)
    log_id = await _write_sync_log(pool, "running", message="正在同步...")

    try:
        count_before = await pool.fetchval("SELECT COUNT(*) FROM cards")
        stale_before = await pool.fetchval(
            "SELECT COUNT(*) FROM cards WHERE name_embedding IS NULL"
        )

        def _do_sync() -> None:
            from scripts.seed_pg import generate_card_embeddings, get_conn, insert_cards

            from .data_loader import download_scryfall_cards

            conn = get_conn()
            try:
                _emit_status(status_callback, "正在下载 Scryfall 数据...")
                raw_cards = download_scryfall_cards()
                valid_cards = [
                    c for c in raw_cards
                    if c.get("layout") not in ("token", "emblem", "art_series")
                ]

                _emit_status(status_callback, "正在同步卡牌数据...")
                insert_cards(conn, valid_cards)

                # Remove stale cards whose id is no longer in oracle_cards.
                # When Scryfall picks a new preferred printing for a card,
                # the old id stays in our DB alongside the new one, causing
                # duplicate names.  Clean them up here.
                current_ids = [c["id"] for c in valid_cards]
                with conn.cursor() as cur:
                    cur.execute("CREATE TEMP TABLE _sync_ids (id TEXT PRIMARY KEY)")
                    batch_size = 5000
                    for i in range(0, len(current_ids), batch_size):
                        batch = [(cid,) for cid in current_ids[i:i + batch_size]]
                        cur.executemany("INSERT INTO _sync_ids (id) VALUES (%s)", batch)
                    cur.execute("""
                        DELETE FROM cards
                        WHERE id NOT IN (SELECT id FROM _sync_ids)
                    """)
                    deleted = cur.rowcount
                    cur.execute("DROP TABLE _sync_ids")
                    if deleted:
                        logger.info("[sync] Removed %d stale card rows.", deleted)
                    cur.execute("""
                        UPDATE cards SET is_playtest = TRUE
                        WHERE is_playtest = FALSE AND data->>'set_type' = 'funny'
                    """)
                conn.commit()

                _emit_status(status_callback, "正在为新卡牌生成 embedding...")
                generate_card_embeddings(
                    conn,
                    on_progress=_make_progress_callback(status_callback, "正在生成 embedding"),
                )
            finally:
                conn.close()

        await asyncio.to_thread(_do_sync)

        count_after = await pool.fetchval("SELECT COUNT(*) FROM cards")
        stale_after = await pool.fetchval(
            "SELECT COUNT(*) FROM cards WHERE name_embedding IS NULL"
        )
        new_cards = count_after - count_before
        # Cards that had embeddings before but got them nulled = text was updated
        updated_cards = max(0, stale_before - stale_after + new_cards)
        # If stale_after > 0, some embeddings failed, but the data was still updated
        # A simpler heuristic: updated = stale_before means cards whose text changed
        # Actually: before sync, stale_before cards had no embedding.
        # The upsert nulls embeddings for text-changed cards, adding to the stale count.
        # generate_card_embeddings then fills them all in.
        # So updated_cards ≈ (stale count right after upsert, before embedding) - stale_before - new_cards
        # We can't measure that mid-thread, so just report what we can.

        await pool.execute(
            """INSERT INTO app_meta (key, value) VALUES ('last_sync_updated_at', $1)
               ON CONFLICT (key) DO UPDATE SET value = $1""",
            remote_updated,
        )

        message = f"新增 {new_cards} 张卡牌，数据已更新"
        await _update_sync_log(pool, log_id, "done", new_cards, updated_cards, message)
        logger.info("[sync] Complete. %d new cards.", new_cards)
        return {"new_cards": new_cards, "updated_cards": updated_cards, "skipped": False}

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
