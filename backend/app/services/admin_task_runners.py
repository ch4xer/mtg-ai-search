"""Background runners for admin maintenance tasks."""

import asyncio
import logging

from ..maintenance import full_reseed, incremental_sync, regenerate_embeddings, sync_abilities_incremental
from ..repositories.database import get_pool
from .admin_task_state import TaskStatus, set_task_state

logger = logging.getLogger(__name__)


async def run_reseed(with_embeddings: bool = True):
    label = "reseed"
    try:
        count = await full_reseed(
            with_embeddings=with_embeddings,
            status_callback=lambda message: set_task_state(label, TaskStatus.RUNNING, message),
        )
        suffix = "" if with_embeddings else "（embedding 未更新）"
        set_task_state(label, TaskStatus.DONE, f"完成！已导入 {count} 张卡牌{suffix}")
    except Exception as exc:
        logger.exception("[reseed] Failed")
        set_task_state(label, TaskStatus.ERROR, f"失败: {exc}")


async def run_reembed():
    try:
        await regenerate_embeddings(
            status_callback=lambda message: set_task_state("reembed", TaskStatus.RUNNING, message),
        )
        set_task_state("reembed", TaskStatus.DONE, "所有 embedding 已重新生成")
    except Exception as exc:
        logger.exception("[reembed] Failed")
        set_task_state("reembed", TaskStatus.ERROR, f"失败: {exc}")


async def run_seed_abilities():
    try:
        pool = await get_pool()
        logger.info("[seed_abilities] Clearing existing keyword abilities...")
        set_task_state("seed_abilities", TaskStatus.RUNNING, "正在清空关键词数据...")
        await pool.execute("DELETE FROM keyword_abilities")
        logger.info("[seed_abilities] Keyword abilities table cleared.")

        set_task_state("seed_abilities", TaskStatus.RUNNING, "正在下载规则文件...")
        await asyncio.to_thread(_seed_abilities_sync)

        count_after = await pool.fetchval("SELECT COUNT(*) FROM keyword_abilities")
        logger.info("[seed_abilities] Complete. %d abilities imported.", count_after)
        set_task_state("seed_abilities", TaskStatus.DONE, f"完成！已导入 {count_after} 个关键词")
    except Exception as exc:
        logger.exception("[seed_abilities] Failed")
        set_task_state("seed_abilities", TaskStatus.ERROR, f"失败: {exc}")


def _seed_abilities_sync() -> None:
    from scripts.seed_pg import generate_ability_embeddings, get_conn

    from ..maintenance import _refresh_abilities_from_rules

    status = lambda msg: set_task_state("seed_abilities", TaskStatus.RUNNING, msg)
    conn = get_conn()
    try:
        _refresh_abilities_from_rules(conn, status_callback=status)
        status("正在生成关键词 embedding...")
        generate_ability_embeddings(conn)
        logger.info("[seed_abilities] Generated embeddings.")
    finally:
        conn.close()


async def run_sync_abilities():
    try:
        result = await sync_abilities_incremental(
            status_callback=lambda msg: set_task_state("seed_abilities", TaskStatus.RUNNING, msg),
        )
        added = result["added"]
        if added:
            names = "、".join(result["added_names"][:5])
            suffix = "等" if added > 5 else ""
            set_task_state("seed_abilities", TaskStatus.DONE, f"完成！新增 {added} 个关键词（{names}{suffix}）")
        else:
            set_task_state("seed_abilities", TaskStatus.DONE, "完成！无新关键词需要添加")
    except Exception as exc:
        logger.exception("[sync_abilities] Failed")
        set_task_state("seed_abilities", TaskStatus.ERROR, f"失败: {exc}")


async def run_sync(force: bool = False, skip_embeddings: bool = False):
    try:
        result = await incremental_sync(
            force=force,
            skip_embeddings=skip_embeddings,
            status_callback=lambda message: set_task_state("reseed", TaskStatus.RUNNING, message),
        )
        if result["skipped"]:
            set_task_state("reseed", TaskStatus.DONE, "Scryfall 数据无变更")
        else:
            suffix = "（跳过 embedding）" if skip_embeddings else ""
            set_task_state(
                "reseed",
                TaskStatus.DONE,
                f"同步完成！新增 {result['new_cards']} 张卡牌，更新 {result['new_prints']} 个版本{suffix}",
            )
    except Exception as exc:
        logger.exception("[sync] Failed")
        set_task_state("reseed", TaskStatus.ERROR, f"同步失败: {exc}")
