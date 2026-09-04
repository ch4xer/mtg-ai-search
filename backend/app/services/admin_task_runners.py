"""Background runners for admin maintenance tasks."""

import logging

from ..config import get_tag_bootstrap_config
from ..maintenance import (
    full_reseed,
    incremental_sync,
)
from .keyword_sync_service import sync_abilities_incremental
from .mtgch_service import sync_mtgch_translations
from .admin_task_state import TaskStatus, set_task_state
from .tag_search_service import (
    build_tag_expansion_cache,
    generate_missing_tag_embeddings,
    sync_function_tag_card_links,
)

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
        refreshed = result.get("refreshed", 0)
        if added:
            names = "、".join(result["added_names"][:5])
            suffix = "等" if added > 5 else ""
            set_task_state(
                "seed_abilities",
                TaskStatus.DONE,
                f"完成！新增 {added} 个关键词（{names}{suffix}），处理 {refreshed} 条双语说明",
            )
        elif refreshed:
            set_task_state("seed_abilities", TaskStatus.DONE, f"完成！处理 {refreshed} 条双语说明")
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


async def run_generate_tag_embeddings():
    try:
        config = get_tag_bootstrap_config()
        generated = 0
        embedded = 0
        failed_batches = 0

        while True:
            set_task_state("tag_embeddings", TaskStatus.RUNNING, "正在生成 function tag 语义扩展文本...")
            expansion_result = await build_tag_expansion_cache(
                limit=config["expansion_batch_size"],
                batch_size=config["expansion_batch_size"],
                sample_size=config["sample_size"],
                scryfall_delay_seconds=config["scryfall_delay_seconds"],
                print_embedding_text=config["print_embedding_text"],
            )
            generated += int(expansion_result.get("generated") or 0)
            failed_batches += int(expansion_result.get("failed_batches") or 0)
            if int(expansion_result.get("generated") or 0) == 0:
                break

        while True:
            set_task_state("tag_embeddings", TaskStatus.RUNNING, "正在生成缺失的 function tag embeddings...")
            embedding_result = await generate_missing_tag_embeddings(
                limit=config["embedding_batch_size"],
                batch_size=config["embedding_batch_size"],
                print_embedding_text=config["print_embedding_text"],
            )
            embedded += int(embedding_result.get("processed") or 0)
            failed_batches += int(embedding_result.get("failed_batches") or 0)
            if int(embedding_result.get("processed") or 0) == 0:
                break

        suffix = f"，失败批次 {failed_batches}" if failed_batches else ""
        set_task_state(
            "tag_embeddings",
            TaskStatus.DONE,
            f"完成！生成 {generated} 个 tag 语义扩展，写入 {embedded} 个 embeddings{suffix}",
        )
    except Exception as exc:
        logger.exception("[tag_embeddings] Failed")
        set_task_state("tag_embeddings", TaskStatus.ERROR, f"失败: {exc}")


async def run_sync_card_translations():
    try:
        result = await sync_mtgch_translations(
            status_callback=lambda msg: set_task_state("card_translations", TaskStatus.RUNNING, msg),
        )
        if result["skipped"]:
            set_task_state("card_translations", TaskStatus.DONE, "中文卡牌信息同步已关闭")
            return

        synced = result["synced"]
        empty = result["empty"]
        not_found = result["not_found"]
        failed = result["failed"]
        suffix = []
        if empty:
            suffix.append(f"无中文信息 {empty} 张")
        if not_found:
            suffix.append(f"未找到 {not_found} 张")
        if failed:
            suffix.append(f"失败 {failed} 张")
        detail = f"，{'，'.join(suffix)}" if suffix else ""
        set_task_state("card_translations", TaskStatus.DONE, f"完成！补全中文信息 {synced} 张{detail}")
    except Exception as exc:
        logger.exception("[card_translations] Failed")
        set_task_state("card_translations", TaskStatus.ERROR, f"失败: {exc}")


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
