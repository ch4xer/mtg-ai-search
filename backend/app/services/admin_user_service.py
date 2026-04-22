"""Admin user management workflows."""

from fastapi import HTTPException

from ..repositories.users import delete_user, search_users, update_user_role
from ..schemas.admin import UpdateRoleRequest


async def list_users(q: str = "", page: int = 1, page_size: int = 20) -> dict:
    return await search_users(q=q, page=page, page_size=page_size)


async def update_role(user_id: str, req: UpdateRoleRequest, admin_id: str) -> dict:
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    if req.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")

    result = await update_user_role(user_id, req.role)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return result


async def delete_account(user_id: str, admin_id: str) -> None:
    if user_id == admin_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    await delete_user(user_id)

