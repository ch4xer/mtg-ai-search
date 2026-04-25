"""Admin endpoints: user listing, role changes, user deletion, DB maintenance."""

from fastapi import APIRouter, Depends

from .auth import require_admin
from .schemas.admin import UpdateRoleRequest, UpdateSettingsRequest
from .services.admin_settings_service import get_settings, update_settings
from .services.admin_stats_service import get_admin_stats
from .services.admin_task_service import (
    start_rebuild_effect_chunks,
    get_task_status,
    list_sync_logs,
    start_reembed,
    start_reseed,
    start_seed_abilities,
    start_sync,
    start_sync_abilities,
)
from .services.admin_user_service import delete_account, list_users, update_role

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


@admin_router.get("/stats")
async def admin_stats(_: str = Depends(require_admin)):
    return await get_admin_stats()


@admin_router.get("/users")
async def admin_list_users(
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    _: str = Depends(require_admin),
):
    return await list_users(q=q, page=page, page_size=page_size)


@admin_router.put("/users/{user_id}/role")
async def admin_update_role(user_id: str, req: UpdateRoleRequest, admin_id: str = Depends(require_admin)):
    return await update_role(user_id, req, admin_id)


@admin_router.delete("/users/{user_id}", status_code=204)
async def admin_delete_user(user_id: str, admin_id: str = Depends(require_admin)):
    await delete_account(user_id, admin_id)


@admin_router.get("/task-status")
async def admin_task_status(_: str = Depends(require_admin)):
    return await get_task_status()


@admin_router.post("/reseed")
async def admin_reseed(_: str = Depends(require_admin)):
    return await start_reseed(with_embeddings=True)


@admin_router.post("/reseed-only")
async def admin_reseed_only(_: str = Depends(require_admin)):
    return await start_reseed(with_embeddings=False)


@admin_router.post("/reembed")
async def admin_reembed(_: str = Depends(require_admin)):
    return await start_reembed()


@admin_router.post("/rebuild-effect-chunks")
async def admin_rebuild_effect_chunks(_: str = Depends(require_admin)):
    return await start_rebuild_effect_chunks()


@admin_router.post("/seed-abilities")
async def admin_seed_abilities(_: str = Depends(require_admin)):
    return await start_seed_abilities()


@admin_router.post("/sync-abilities")
async def admin_sync_abilities(_: str = Depends(require_admin)):
    return await start_sync_abilities()


@admin_router.get("/sync-logs")
async def admin_sync_logs(_: str = Depends(require_admin)):
    return await list_sync_logs()


@admin_router.post("/sync")
async def admin_trigger_sync(force: bool = False, skip_embeddings: bool = False, _: str = Depends(require_admin)):
    return await start_sync(force=force, skip_embeddings=skip_embeddings)


@admin_router.get("/settings")
async def admin_get_settings(_: str = Depends(require_admin)):
    return await get_settings()


@admin_router.put("/settings")
async def admin_update_settings(req: UpdateSettingsRequest, _: str = Depends(require_admin)):
    return await update_settings(req)
