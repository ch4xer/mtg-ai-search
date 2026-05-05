"""Keyword ability sync used by Exact Match filters.

Keyword abilities are now deterministic filter data only. This module keeps
that responsibility separate from card data maintenance and does not generate
or depend on embeddings.
"""

import asyncio
import logging
from pathlib import Path

from ..repositories.database import get_pool
from .task_progress import StatusCallback, emit_status, make_progress_callback

logger = logging.getLogger(__name__)


def _ability_file() -> str:
    return str(Path(__file__).resolve().parents[2] / "data" / "keyword_ability.txt")


def _download_ability_file(status_callback: StatusCallback = None) -> str:
    """Download the latest rule 702 keyword ability cache from Wizards."""
    filepath = _ability_file()
    emit_status(status_callback, "正在下载万智牌规则文件...")
    logger.info("Downloading keyword abilities from Wizards...")
    try:
        from scripts.extract_keywords import download_and_extract_keywords

        download_and_extract_keywords(filepath)
        emit_status(status_callback, "已下载关键词规则文件")
        logger.info("Downloaded keyword abilities to %s", filepath)
        return filepath
    except Exception as exc:
        logger.exception("Failed to download keyword abilities: %s", exc)
        raise


def _refresh_abilities_from_rules(conn, status_callback: StatusCallback = None) -> list[str]:
    """Refresh keyword_abilities from rule 702 and return newly added names."""
    from scripts.seed_pg import insert_abilities

    from ..data_loader import parse_keyword_abilities

    filepath = _download_ability_file(status_callback)
    abilities = parse_keyword_abilities(filepath)

    with conn.cursor() as cur:
        cur.execute("SELECT id FROM keyword_abilities")
        existing_ids = {row[0] for row in cur.fetchall()}

    parsed_ids = {name.lower().replace(" ", "_"): name for name in abilities.keys()}
    new_names = sorted(name for keyword_id, name in parsed_ids.items() if keyword_id not in existing_ids)

    emit_status(status_callback, "正在生成关键词摘要...")
    insert_abilities(
        conn,
        abilities,
        on_progress=make_progress_callback(status_callback, "正在生成摘要"),
    )

    if new_names:
        logger.info("[keyword-sync] %d new abilities from rules 702: %s", len(new_names), new_names)
        emit_status(status_callback, f"发现 {len(new_names)} 个新关键词")
    else:
        logger.info("[keyword-sync] No new abilities in rules 702.")
    return new_names


async def seed_abilities_if_empty(status_callback: StatusCallback = None) -> None:
    """Initialize keyword_abilities only when Exact Match has no keyword data."""
    pool = await get_pool()
    try:
        count = await pool.fetchval("SELECT COUNT(*) FROM keyword_abilities")
    except Exception:
        count = 0

    if count > 0:
        logger.info("Database has %d keyword abilities, skipping seed.", count)
        return

    logger.info("No keyword abilities found. Running keyword sync.")
    emit_status(status_callback, "正在初始化关键词数据...")
    await sync_abilities_incremental(status_callback=status_callback)
    logger.info("Keyword abilities seed complete.")


async def sync_abilities_incremental(status_callback: StatusCallback = None) -> dict:
    """Refresh keyword abilities without clearing the existing table."""
    result = {"added": 0, "added_names": []}

    def _do_sync() -> None:
        from scripts.seed_pg import get_conn

        conn = get_conn()
        try:
            added = _refresh_abilities_from_rules(conn, status_callback)
            result["added"] = len(added)
            result["added_names"] = added
        finally:
            conn.close()

    await asyncio.to_thread(_do_sync)
    logger.info("[abilities-sync] Complete. %d added.", result["added"])
    return result
