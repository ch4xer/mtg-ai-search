"""Admin endpoints: user listing, role changes, user deletion, DB maintenance."""

import asyncio
import logging
import time
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import require_admin
from .db import delete_user, get_pool, get_user_search_stats, update_user_role
from .maintenance import full_reseed, incremental_sync, regenerate_embeddings

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Background task status tracking ───────────────────────────────────


class TaskStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


_task_state: dict = {
    "reseed": {"status": TaskStatus.IDLE, "message": "", "started_at": None},
    "reembed": {"status": TaskStatus.IDLE, "message": "", "started_at": None},
}


def _set_state(task_name: str, status: TaskStatus, message: str = ""):
    _task_state[task_name] = {
        "status": status,
        "message": message,
        "started_at": _task_state[task_name].get("started_at"),
    }
    if status == TaskStatus.RUNNING and not _task_state[task_name]["started_at"]:
        _task_state[task_name]["started_at"] = time.time()
    if status in (TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.IDLE):
        _task_state[task_name]["started_at"] = None


# ── User management ──────────────────────────────────────────────────


class UpdateRoleRequest(BaseModel):
    role: str


@admin_router.get("/users")
async def admin_list_users(_: str = Depends(require_admin)):
    return await get_user_search_stats()


@admin_router.put("/users/{user_id}/role")
async def admin_update_role(user_id: str, req: UpdateRoleRequest, admin_id: str = Depends(require_admin)):
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
    result = await update_user_role(user_id, req.role)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result


@admin_router.delete("/users/{user_id}", status_code=204)
async def admin_delete_user(user_id: str, admin_id: str = Depends(require_admin)):
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    await delete_user(user_id)


# ── DB maintenance ───────────────────────────────────────────────────


@admin_router.get("/task-status")
async def admin_task_status(_: str = Depends(require_admin)):
    return {k: {"status": v["status"], "message": v["message"]} for k, v in _task_state.items()}


@admin_router.post("/reseed")
async def admin_reseed(_: str = Depends(require_admin)):
    if _task_state["reseed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="重新拉取任务正在运行中")
    if _task_state["reembed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Embedding 生成任务正在运行中，请等待完成")

    _set_state("reseed", TaskStatus.RUNNING, "正在拉取卡牌数据...")
    asyncio.create_task(_run_reseed(with_embeddings=True))
    return {"status": "started", "message": "开始重新拉取卡牌数据（含 embedding）"}


@admin_router.post("/reseed-only")
async def admin_reseed_only(_: str = Depends(require_admin)):
    if _task_state["reseed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="重新拉取任务正在运行中")
    if _task_state["reembed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Embedding 生成任务正在运行中，请等待完成")

    _set_state("reseed", TaskStatus.RUNNING, "正在拉取卡牌数据...")
    asyncio.create_task(_run_reseed(with_embeddings=False))
    return {"status": "started", "message": "开始重新拉取卡牌数据（不含 embedding）"}


@admin_router.post("/reembed")
async def admin_reembed(_: str = Depends(require_admin)):
    if _task_state["reembed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Embedding 生成任务正在运行中")
    if _task_state["reseed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="卡牌拉取任务正在运行中，请等待完成")

    _set_state("reembed", TaskStatus.RUNNING, "正在清除旧 embedding...")
    asyncio.create_task(_run_reembed())
    return {"status": "started", "message": "开始重新生成 embedding"}


async def _run_reseed(with_embeddings: bool = True):
    """Background: re-download Scryfall data and re-insert all cards (+ optionally embeddings)."""
    label = "reseed"
    try:
        count = await full_reseed(
            with_embeddings=with_embeddings,
            status_callback=lambda message: _set_state(label, TaskStatus.RUNNING, message),
        )
        suffix = "" if with_embeddings else "（embedding 未更新）"
        _set_state(label, TaskStatus.DONE, f"完成！已导入 {count} 张卡牌{suffix}")

    except Exception as e:
        logger.exception("[reseed] Failed")
        _set_state(label, TaskStatus.ERROR, f"失败: {e}")


async def _run_reembed():
    """Background: clear and regenerate all embeddings."""
    try:
        await regenerate_embeddings(
            status_callback=lambda message: _set_state("reembed", TaskStatus.RUNNING, message),
        )
        _set_state("reembed", TaskStatus.DONE, "所有 embedding 已重新生成")

    except Exception as e:
        logger.exception("[reembed] Failed")
        _set_state("reembed", TaskStatus.ERROR, f"失败: {e}")


# ── Sync logs & manual sync ─────────────────────────────────────────


@admin_router.get("/sync-logs")
async def admin_sync_logs(_: str = Depends(require_admin)):
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id, started_at, completed_at, status, new_cards, updated_cards, message
           FROM sync_logs ORDER BY started_at DESC LIMIT 30"""
    )
    return [dict(row) for row in rows]


@admin_router.post("/sync")
async def admin_trigger_sync(_: str = Depends(require_admin)):
    if _task_state["reseed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="重新拉取任务正在运行中")

    _set_state("reseed", TaskStatus.RUNNING, "正在检查 Scryfall 更新...")
    asyncio.create_task(_run_sync())
    return {"status": "started", "message": "开始增量同步"}


async def _run_sync():
    """Background: run incremental sync."""
    try:
        result = await incremental_sync(
            status_callback=lambda message: _set_state("reseed", TaskStatus.RUNNING, message),
        )
        if result["skipped"]:
            _set_state("reseed", TaskStatus.DONE, "Scryfall 数据无变更")
        else:
            _set_state(
                "reseed", TaskStatus.DONE,
                f"同步完成！新增 {result['new_cards']} 张卡牌",
            )
    except Exception as e:
        logger.exception("[sync] Failed")
        _set_state("reseed", TaskStatus.ERROR, f"同步失败: {e}")
