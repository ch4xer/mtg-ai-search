"""Admin endpoints: user listing, role changes, user deletion, DB maintenance."""

import asyncio
import logging
import time
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import require_admin
from .config import get_rate_limits, update_rate_limits
from .db import delete_user, get_pool, search_users, update_user_role
from .maintenance import (
    full_reseed,
    incremental_sync,
    regenerate_embeddings,
    seed_abilities_if_empty,
    sync_abilities_incremental,
)

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Dashboard stats ─────────────────────────────────────────────────


@admin_router.get("/stats")
async def admin_stats(_: str = Depends(require_admin)):
    pool = await get_pool()

    # Database stats
    total_cards = await pool.fetchval("SELECT COUNT(*) FROM cards")
    total_abilities = await pool.fetchval("SELECT COUNT(*) FROM keyword_abilities")
    cards_missing = await pool.fetchval("SELECT COUNT(*) FROM cards WHERE name_embedding IS NULL")
    abilities_missing = await pool.fetchval("SELECT COUNT(*) FROM keyword_abilities WHERE embedding IS NULL")
    last_sync = await pool.fetchval("SELECT value FROM app_meta WHERE key = 'last_sync_updated_at'")

    # Search stats (aggregated)
    row = await pool.fetchrow("""
        SELECT
            COUNT(*) FILTER (WHERE created_at >= now() - interval '1 day') AS today_count,
            COUNT(*) FILTER (WHERE created_at >= now() - interval '7 days') AS week_count,
            COUNT(*) FILTER (WHERE created_at >= now() - interval '30 days') AS month_count,
            COALESCE(SUM(tokens_prompt + tokens_completion)
                FILTER (WHERE created_at >= now() - interval '1 day'), 0) AS today_tokens,
            COALESCE(SUM(tokens_prompt + tokens_completion)
                FILTER (WHERE created_at >= now() - interval '7 days'), 0) AS week_tokens,
            COALESCE(SUM(tokens_prompt + tokens_completion)
                FILTER (WHERE created_at >= now() - interval '30 days'), 0) AS month_tokens,
            COUNT(*) FILTER (WHERE created_at >= now() - interval '7 days'
                AND user_id IS NULL) AS anon_7d,
            COUNT(*) FILTER (WHERE created_at >= now() - interval '7 days'
                AND user_id IS NOT NULL) AS reg_7d
        FROM search_logs
    """)

    # Popular queries (last 7 days)
    popular = await pool.fetch("""
        SELECT query, COUNT(*) AS cnt
        FROM search_logs
        WHERE created_at >= now() - interval '7 days'
        GROUP BY query
        ORDER BY cnt DESC
        LIMIT 20
    """)

    return {
        "database": {
            "total_cards": int(total_cards),
            "total_abilities": int(total_abilities),
            "cards_missing_embeddings": int(cards_missing),
            "abilities_missing_embeddings": int(abilities_missing),
            "last_sync_at": last_sync,
        },
        "searches": {
            "today": {"count": int(row["today_count"]), "tokens": int(row["today_tokens"])},
            "week": {"count": int(row["week_count"]), "tokens": int(row["week_tokens"])},
            "month": {"count": int(row["month_count"]), "tokens": int(row["month_tokens"])},
            "anonymous_7d": int(row["anon_7d"]),
            "registered_7d": int(row["reg_7d"]),
        },
        "popular_queries": [
            {"query": r["query"], "count": int(r["cnt"])} for r in popular
        ],
    }


# ── Background task status tracking ───────────────────────────────────


class TaskStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


_task_state: dict = {
    "reseed": {"status": TaskStatus.IDLE, "message": "", "started_at": None},
    "reembed": {"status": TaskStatus.IDLE, "message": "", "started_at": None},
    "seed_abilities": {"status": TaskStatus.IDLE, "message": "", "started_at": None},
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
async def admin_list_users(
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    _: str = Depends(require_admin),
):
    return await search_users(q=q, page=page, page_size=page_size)


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
    if _task_state["seed_abilities"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="关键词初始化任务正在运行中，请等待完成")

    _set_state("reseed", TaskStatus.RUNNING, "正在拉取卡牌数据...")
    asyncio.create_task(_run_reseed(with_embeddings=True))
    return {"status": "started", "message": "开始重新拉取卡牌数据（含 embedding）"}


@admin_router.post("/reseed-only")
async def admin_reseed_only(_: str = Depends(require_admin)):
    if _task_state["reseed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="重新拉取任务正在运行中")
    if _task_state["reembed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Embedding 生成任务正在运行中，请等待完成")
    if _task_state["seed_abilities"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="关键词初始化任务正在运行中，请等待完成")

    _set_state("reseed", TaskStatus.RUNNING, "正在拉取卡牌数据...")
    asyncio.create_task(_run_reseed(with_embeddings=False))
    return {"status": "started", "message": "开始重新拉取卡牌数据（不含 embedding）"}


@admin_router.post("/reembed")
async def admin_reembed(_: str = Depends(require_admin)):
    if _task_state["reembed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Embedding 生成任务正在运行中")
    if _task_state["reseed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="卡牌拉取任务正在运行中，请等待完成")
    if _task_state["seed_abilities"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="关键词初始化任务正在运行中，请等待完成")

    _set_state("reembed", TaskStatus.RUNNING, "正在清除旧 embedding...")
    asyncio.create_task(_run_reembed())
    return {"status": "started", "message": "开始重新生成 embedding"}


@admin_router.post("/seed-abilities")
async def admin_seed_abilities(_: str = Depends(require_admin)):
    if _task_state["seed_abilities"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="关键词任务正在运行中")
    if _task_state["reembed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Embedding 生成任务正在运行中，请等待完成")

    _set_state("seed_abilities", TaskStatus.RUNNING, "正在检查关键词数据...")
    asyncio.create_task(_run_seed_abilities())
    return {"status": "started", "message": "开始重建关键词数据库"}


@admin_router.post("/sync-abilities")
async def admin_sync_abilities(_: str = Depends(require_admin)):
    if _task_state["seed_abilities"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="关键词任务正在运行中")
    if _task_state["reembed"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Embedding 生成任务正在运行中，请等待完成")

    _set_state("seed_abilities", TaskStatus.RUNNING, "正在检查 Scryfall 关键词...")
    asyncio.create_task(_run_sync_abilities())
    return {"status": "started", "message": "开始增量同步关键词"}


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


async def _run_seed_abilities():
    """Background: clear and re-import keyword abilities."""
    try:
        pool = await get_pool()

        # 清空现有关键词数据
        logger.info("[seed_abilities] Clearing existing keyword abilities...")
        _set_state("seed_abilities", TaskStatus.RUNNING, "正在清空关键词数据...")
        await pool.execute("DELETE FROM keyword_abilities")
        logger.info("[seed_abilities] Keyword abilities table cleared.")

        # 重新下载并导入
        _set_state("seed_abilities", TaskStatus.RUNNING, "正在下载规则文件...")

        def _do_seed() -> None:
            from scripts.seed_pg import generate_ability_embeddings, get_conn

            from .maintenance import _refresh_abilities_from_rules

            status = lambda msg: _set_state("seed_abilities", TaskStatus.RUNNING, msg)

            conn = get_conn()
            try:
                _refresh_abilities_from_rules(conn, status_callback=status)
                status("正在生成关键词 embedding...")
                generate_ability_embeddings(conn)
                logger.info("[seed_abilities] Generated embeddings.")
            finally:
                conn.close()

        await asyncio.to_thread(_do_seed)

        count_after = await pool.fetchval("SELECT COUNT(*) FROM keyword_abilities")
        logger.info("[seed_abilities] Complete. %d abilities imported.", count_after)
        _set_state("seed_abilities", TaskStatus.DONE, f"完成！已导入 {count_after} 个关键词")

    except Exception as e:
        logger.exception("[seed_abilities] Failed")
        _set_state("seed_abilities", TaskStatus.ERROR, f"失败: {e}")


async def _run_sync_abilities():
    """Background: add missing Scryfall ability keywords without touching existing rows."""
    try:
        result = await sync_abilities_incremental(
            status_callback=lambda msg: _set_state("seed_abilities", TaskStatus.RUNNING, msg),
        )
        added = result["added"]
        if added:
            names = "、".join(result["added_names"][:5])
            suffix = "等" if added > 5 else ""
            _set_state(
                "seed_abilities", TaskStatus.DONE,
                f"完成！新增 {added} 个关键词（{names}{suffix}）",
            )
        else:
            _set_state("seed_abilities", TaskStatus.DONE, "完成！无新关键词需要添加")

    except Exception as e:
        logger.exception("[sync_abilities] Failed")
        _set_state("seed_abilities", TaskStatus.ERROR, f"失败: {e}")


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
    if _task_state["seed_abilities"]["status"] == TaskStatus.RUNNING:
        raise HTTPException(status_code=409, detail="关键词初始化任务正在运行中")

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


# ── Settings ───────────────────────────────────────────────────────


class UpdateSettingsRequest(BaseModel):
    anon_hourly_limit: int | None = None
    user_hourly_limit: int | None = None


@admin_router.get("/settings")
async def admin_get_settings(_: str = Depends(require_admin)):
    limits = get_rate_limits()
    return {
        "anon_hourly_limit": limits["anon_hourly"],
        "user_hourly_limit": limits["user_hourly"],
    }


@admin_router.put("/settings")
async def admin_update_settings(req: UpdateSettingsRequest, _: str = Depends(require_admin)):
    if req.anon_hourly_limit is not None and req.anon_hourly_limit < 0:
        raise HTTPException(status_code=400, detail="匿名用户限制不能为负数")
    if req.user_hourly_limit is not None and req.user_hourly_limit < 0:
        raise HTTPException(status_code=400, detail="注册用户限制不能为负数")

    limits = update_rate_limits(
        anon_hourly=req.anon_hourly_limit,
        user_hourly=req.user_hourly_limit,
    )

    # Persist to app_meta so settings survive restarts
    pool = await get_pool()
    if req.anon_hourly_limit is not None:
        await pool.execute(
            """INSERT INTO app_meta (key, value) VALUES ('anon_hourly_limit', $1)
               ON CONFLICT (key) DO UPDATE SET value = $1""",
            str(req.anon_hourly_limit),
        )
    if req.user_hourly_limit is not None:
        await pool.execute(
            """INSERT INTO app_meta (key, value) VALUES ('user_hourly_limit', $1)
               ON CONFLICT (key) DO UPDATE SET value = $1""",
            str(req.user_hourly_limit),
        )

    return {
        "anon_hourly_limit": limits["anon_hourly"],
        "user_hourly_limit": limits["user_hourly"],
    }
