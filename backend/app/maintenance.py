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


def _download_ability_file(status_callback: StatusCallback = None) -> str:
    """总是从官方规则页面重新下载最新的 702 章节，写入本地缓存。"""
    filepath = _ability_file()
    _emit_status(status_callback, "正在下载万智牌规则文件...")
    logger.info("Downloading keyword abilities from Wizards...")
    try:
        from scripts.extract_keywords import download_and_extract_keywords

        download_and_extract_keywords(filepath)
        _emit_status(status_callback, "已下载关键词规则文件")
        logger.info("Downloaded keyword abilities to %s", filepath)
        return filepath
    except Exception as e:
        logger.exception("Failed to download keyword abilities: %s", e)
        raise


def _emit_status(callback: StatusCallback, message: str) -> None:
    if callback:
        callback(message)


def _make_progress_callback(callback: StatusCallback, prefix: str):
    if not callback:
        return None

    def _progress(done: int, total: int) -> None:
        callback(f"{prefix}（{done}/{total}）...")

    return _progress


def _refresh_abilities_from_rules(conn, status_callback: StatusCallback = None) -> list[str]:
    """Re-download rules 702, summarize with DeepSeek, and upsert keyword_abilities.

    Always pulls a fresh copy from Wizards so we never drift behind the
    published rules. Then uses DeepSeek to generate concise one-sentence
    descriptions for better embedding matching.
    insert_abilities uses ON CONFLICT to update descriptions
    and null the embedding only when the description actually changed.
    Returns names of keywords that didn't previously exist in the DB.
    Does NOT generate embeddings — caller should run generate_ability_embeddings().
    """
    from scripts.seed_pg import insert_abilities

    from .data_loader import parse_keyword_abilities

    filepath = _download_ability_file(status_callback)
    abilities = parse_keyword_abilities(filepath)

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM keyword_abilities")
        existing_ids = {row[0] for row in cur.fetchall()}

    parsed_ids = {name.lower().replace(" ", "_"): name for name in abilities.keys()}
    new_names = sorted(name for kid, name in parsed_ids.items() if kid not in existing_ids)

    _emit_status(status_callback, "正在生成关键词摘要...")
    insert_abilities(
        conn,
        abilities,
        on_progress=_make_progress_callback(status_callback, "正在生成摘要"),
    )

    if new_names:
        logger.info("[keyword-sync] %d new abilities from rules 702: %s", len(new_names), new_names)
        _emit_status(status_callback, f"发现 {len(new_names)} 个新关键词")
    else:
        logger.info("[keyword-sync] No new abilities in rules 702.")
    return new_names


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


async def seed_abilities_if_empty(status_callback: StatusCallback = None) -> None:
    """If keyword_abilities is empty, download rules 702 and import."""
    pool = await get_pool()
    try:
        count = await pool.fetchval("SELECT COUNT(*) FROM keyword_abilities")
    except Exception:
        count = 0

    if count > 0:
        logger.info("Database has %d keyword abilities, skipping seed.", count)
        return

    logger.info("No keyword abilities found. Downloading and importing...")
    _emit_status(status_callback, "正在初始化关键词数据...")

    def _do_seed() -> None:
        from scripts.seed_pg import generate_ability_embeddings, get_conn

        conn = get_conn()
        try:
            _refresh_abilities_from_rules(conn, status_callback)
            _emit_status(status_callback, "正在生成关键词 embedding...")
            generate_ability_embeddings(conn)
        finally:
            conn.close()

    await asyncio.to_thread(_do_seed)
    logger.info("Keyword abilities seed complete.")


async def sync_abilities_incremental(status_callback: StatusCallback = None) -> dict:
    """Re-download rules 702 and add any newly introduced keyword abilities.

    Returns {"added": int, "added_names": list[str]}.
    """
    result = {"added": 0, "added_names": []}

    def _do_sync() -> None:
        from scripts.seed_pg import generate_ability_embeddings, get_conn

        conn = get_conn()
        try:
            added = _refresh_abilities_from_rules(conn, status_callback)
            result["added"] = len(added)
            result["added_names"] = added
            # Always run embedding generation: description edits null old embeddings.
            _emit_status(status_callback, "正在生成关键词 embedding...")
            generate_ability_embeddings(conn)
        finally:
            conn.close()

    await asyncio.to_thread(_do_sync)
    logger.info("[abilities-sync] Complete. %d added.", result["added"])
    return result


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
    """完全重新导入卡牌数据（不影响关键词数据）。使用 unique_artwork 支持多版本。"""
    def _do_reseed() -> None:
        from scripts.seed_pg import (
            create_schema,
            generate_card_embeddings,
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

            _emit_status(status_callback, "正在下载并导入 Scryfall 数据...")
            insert_cards_and_prints(conn)

            if with_embeddings:
                _emit_status(status_callback, "正在生成卡牌 embedding...")
                generate_card_embeddings(
                    conn,
                    on_progress=_make_progress_callback(status_callback, "正在生成卡牌 embedding"),
                )
            else:
                logger.info("[reseed] Skipping embedding generation.")
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
    """Fetch the updated_at timestamp of the unique_artwork bulk data from Scryfall."""
    try:
        resp = requests.get("https://api.scryfall.com/bulk-data", timeout=15)
        resp.raise_for_status()
        for entry in resp.json()["data"]:
            if entry["type"] == "unique_artwork":
                return entry["updated_at"]
    except Exception as e:
        logger.warning("[sync] Failed to check Scryfall bulk data: %s", e)
    return None


async def incremental_sync(status_callback: StatusCallback = None, force: bool = False, skip_embeddings: bool = False) -> dict:
    """Download Scryfall unique_artwork data, upsert cards and prints.

    If force=True, skip the timestamp check and always sync.
    If skip_embeddings=True, don't regenerate embeddings (only update card data).

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
            from scripts.seed_pg import generate_ability_embeddings, generate_card_embeddings, get_conn, insert_cards_and_prints

            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM cards")
                    cards_before = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM card_prints")
                    prints_before = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM cards WHERE name_embedding IS NULL")
                    stale_before = cur.fetchone()[0]

                _emit_status(status_callback, "正在下载并同步卡牌数据...")
                insert_cards_and_prints(conn)

                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM cards")
                    cards_after = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM card_prints")
                    prints_after = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM cards WHERE name_embedding IS NULL")
                    stale_after = cur.fetchone()[0]
                conn.commit()

                stats["new_cards"] = cards_after - cards_before
                stats["new_prints"] = prints_after - prints_before
                stats["updated_cards"] = max(0, stale_after - stale_before - stats["new_cards"])

                if skip_embeddings:
                    logger.info("[sync] Skipping embedding generation.")
                    _emit_status(status_callback, "数据已更新（跳过 embedding）")
                else:
                    _emit_status(status_callback, "正在为新/变更卡牌生成 embedding...")
                    generate_card_embeddings(
                        conn,
                        on_progress=_make_progress_callback(status_callback, "正在生成 embedding"),
                    )

                    _emit_status(status_callback, "正在刷新规则 702 关键词...")
                    _refresh_abilities_from_rules(conn, status_callback)
                    _emit_status(status_callback, "正在生成关键词 embedding...")
                    generate_ability_embeddings(conn)
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
