"""Admin maintenance task orchestration."""

import asyncio

from ..repositories.admin import get_sync_logs
from .admin_task_runners import (
    run_reseed,
    run_sync,
    run_sync_abilities,
    run_sync_function_tags,
)
from .admin_task_state import TaskStatus, ensure_task_not_running, get_task_state_snapshot, set_task_state


RUNNING_MESSAGES = {
    "reseed": "卡牌同步任务正在运行中，请等待完成",
    "seed_abilities": "关键词任务正在运行中，请等待完成",
    "tag_sync": "Tag 同步任务正在运行中，请等待完成",
}


async def get_task_status() -> dict:
    return get_task_state_snapshot()


def _ensure_idle(*task_names: str) -> None:
    """Keep admin maintenance jobs serialized to avoid DB write conflicts."""
    for task_name in task_names:
        ensure_task_not_running(task_name, RUNNING_MESSAGES[task_name])


async def start_reseed() -> dict:
    _ensure_idle("reseed", "seed_abilities", "tag_sync")

    set_task_state("reseed", TaskStatus.RUNNING, "正在拉取卡牌数据...")
    asyncio.create_task(run_reseed())
    return {"status": "started", "message": "开始重新拉取卡牌数据"}


async def start_sync_abilities() -> dict:
    _ensure_idle("seed_abilities", "tag_sync")

    set_task_state("seed_abilities", TaskStatus.RUNNING, "正在检查 Scryfall 关键词...")
    asyncio.create_task(run_sync_abilities())
    return {"status": "started", "message": "开始增量同步关键词"}


async def start_sync_function_tags(only_failed: bool = False, limit: int | None = None) -> dict:
    _ensure_idle("tag_sync", "reseed", "seed_abilities")

    set_task_state("tag_sync", TaskStatus.RUNNING, "正在更新 function tag 列表...")
    asyncio.create_task(run_sync_function_tags(only_failed=only_failed, limit=limit))
    return {"status": "started", "message": "开始同步 Function Tags 与卡牌关系"}


async def list_sync_logs() -> list[dict]:
    return await get_sync_logs()


async def start_sync(force: bool = False) -> dict:
    _ensure_idle("reseed", "seed_abilities", "tag_sync")

    message = "开始强制刷新数据" if force else "开始增量同步"

    set_task_state("reseed", TaskStatus.RUNNING, "正在检查 Scryfall 更新...")
    asyncio.create_task(run_sync(force=force))
    return {"status": "started", "message": message}
