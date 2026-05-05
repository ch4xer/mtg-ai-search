"""Background runners for admin maintenance tasks."""

import logging

from ..maintenance import (
    full_reseed,
    incremental_sync,
)
from .keyword_sync_service import sync_abilities_incremental
from .tag_search_service import sync_function_tag_card_links
from .admin_task_state import TaskStatus, set_task_state

logger = logging.getLogger(__name__)


async def run_reseed():
    label = "reseed"
    try:
        count = await full_reseed(
            status_callback=lambda message: set_task_state(label, TaskStatus.RUNNING, message),
        )
        set_task_state(label, TaskStatus.DONE, f"完成！已导入 {count} 张卡牌")
    except Exception as exc:
        logger.exception("[reseed] Failed")
        set_task_state(label, TaskStatus.ERROR, f"失败: {exc}")


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


async def run_sync_function_tags(only_failed: bool = False, limit: int | None = None):
    try:
        result = await sync_function_tag_card_links(
            status_callback=lambda msg: set_task_state("tag_sync", TaskStatus.RUNNING, msg),
            only_failed=only_failed,
            limit=limit,
        )
        details = []
        if result["removed_function_tags"]:
            details.append(f"软删除 {result['removed_function_tags']} 个旧 tag")
        if result["failed_tags"]:
            details.append(f"失败 {result['failed_tags']} 个 tag")
        suffix = f"，{'，'.join(details)}" if details else ""
        set_task_state(
            "tag_sync",
            TaskStatus.DONE,
            f"完成！已同步 {result['processed_tags']}/{result['total_tags']} 个 tag，写入 {result['linked_cards']} 条卡牌关系{suffix}",
        )
    except Exception as exc:
        logger.exception("[tag_sync] Failed")
        set_task_state("tag_sync", TaskStatus.ERROR, f"失败: {exc}")


async def run_sync(force: bool = False):
    try:
        result = await incremental_sync(
            force=force,
            status_callback=lambda message: set_task_state("reseed", TaskStatus.RUNNING, message),
        )
        if result["skipped"]:
            set_task_state("reseed", TaskStatus.DONE, "Scryfall 数据无变更")
        else:
            set_task_state(
                "reseed",
                TaskStatus.DONE,
                f"同步完成！新增 {result['new_cards']} 张卡牌，更新 {result['new_prints']} 个版本",
            )
    except Exception as exc:
        logger.exception("[sync] Failed")
        set_task_state("reseed", TaskStatus.ERROR, f"同步失败: {exc}")
