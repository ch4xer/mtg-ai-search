"""Admin maintenance task orchestration."""

import asyncio

from ..repositories.admin import get_sync_logs
from .admin_task_runners import (
    run_rebuild_effect_chunks,
    run_reembed,
    run_reseed,
    run_seed_abilities,
    run_sync,
    run_sync_abilities,
)
from .admin_task_state import TaskStatus, ensure_task_not_running, get_task_state_snapshot, set_task_state


async def get_task_status() -> dict:
    return get_task_state_snapshot()


async def start_reseed(with_embeddings: bool = True) -> dict:
    ensure_task_not_running("reseed", "重新拉取任务正在运行中")
    ensure_task_not_running("reembed", "Embedding 生成任务正在运行中，请等待完成")
    ensure_task_not_running("effect_chunks", "效果分段任务正在运行中，请等待完成")
    ensure_task_not_running("seed_abilities", "关键词初始化任务正在运行中，请等待完成")

    set_task_state("reseed", TaskStatus.RUNNING, "正在拉取卡牌数据...")
    asyncio.create_task(run_reseed(with_embeddings=with_embeddings))
    suffix = "（含 embedding）" if with_embeddings else "（不含 embedding）"
    return {"status": "started", "message": f"开始重新拉取卡牌数据{suffix}"}


async def start_reembed() -> dict:
    ensure_task_not_running("reembed", "Embedding 生成任务正在运行中")
    ensure_task_not_running("reseed", "卡牌拉取任务正在运行中，请等待完成")
    ensure_task_not_running("effect_chunks", "效果分段任务正在运行中，请等待完成")
    ensure_task_not_running("seed_abilities", "关键词初始化任务正在运行中，请等待完成")

    set_task_state("reembed", TaskStatus.RUNNING, "正在清除旧 embedding...")
    asyncio.create_task(run_reembed())
    return {"status": "started", "message": "开始重新生成 embedding"}


async def start_rebuild_effect_chunks() -> dict:
    ensure_task_not_running("effect_chunks", "效果分段任务正在运行中")
    ensure_task_not_running("reembed", "Embedding 生成任务正在运行中，请等待完成")
    ensure_task_not_running("reseed", "卡牌拉取任务正在运行中，请等待完成")
    ensure_task_not_running("seed_abilities", "关键词初始化任务正在运行中，请等待完成")

    set_task_state("effect_chunks", TaskStatus.RUNNING, "正在重建卡牌效果分段...")
    asyncio.create_task(run_rebuild_effect_chunks())
    return {"status": "started", "message": "开始重建卡牌效果分段"}


async def start_seed_abilities() -> dict:
    ensure_task_not_running("seed_abilities", "关键词任务正在运行中")
    ensure_task_not_running("reembed", "Embedding 生成任务正在运行中，请等待完成")
    ensure_task_not_running("effect_chunks", "效果分段任务正在运行中，请等待完成")

    set_task_state("seed_abilities", TaskStatus.RUNNING, "正在检查关键词数据...")
    asyncio.create_task(run_seed_abilities())
    return {"status": "started", "message": "开始重建关键词数据库"}


async def start_sync_abilities() -> dict:
    ensure_task_not_running("seed_abilities", "关键词任务正在运行中")
    ensure_task_not_running("reembed", "Embedding 生成任务正在运行中，请等待完成")
    ensure_task_not_running("effect_chunks", "效果分段任务正在运行中，请等待完成")

    set_task_state("seed_abilities", TaskStatus.RUNNING, "正在检查 Scryfall 关键词...")
    asyncio.create_task(run_sync_abilities())
    return {"status": "started", "message": "开始增量同步关键词"}


async def list_sync_logs() -> list[dict]:
    return await get_sync_logs()


async def start_sync(force: bool = False, skip_embeddings: bool = False) -> dict:
    ensure_task_not_running("reseed", "重新拉取任务正在运行中")
    ensure_task_not_running("reembed", "Embedding 生成任务正在运行中，请等待完成")
    ensure_task_not_running("effect_chunks", "效果分段任务正在运行中，请等待完成")
    ensure_task_not_running("seed_abilities", "关键词初始化任务正在运行中")

    if force and skip_embeddings:
        message = "开始强制刷新（仅更新数据，不重新生成 embedding）"
    elif force:
        message = "开始强制刷新（更新所有数据）"
    else:
        message = "开始增量同步"

    set_task_state("reseed", TaskStatus.RUNNING, "正在检查 Scryfall 更新...")
    asyncio.create_task(run_sync(force=force, skip_embeddings=skip_embeddings))
    return {"status": "started", "message": message}
