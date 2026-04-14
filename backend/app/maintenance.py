import asyncio
import logging
import os
from collections.abc import Callable

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
            generate_ability_embeddings,
            generate_card_embeddings,
            get_conn,
            insert_abilities,
            insert_cards,
        )
        from .data_loader import download_scryfall_cards, parse_keyword_abilities

        conn = get_conn()
        try:
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
