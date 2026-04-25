from .connection import get_pool
from .helpers import _serialize_user_row


async def get_api_key_status(user_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT api_key_hash, api_key_created_at
           FROM users
           WHERE id = $1::uuid""",
        user_id,
    )
    if not row:
        return None
    return {
        "has_api_key": bool(row["api_key_hash"]),
        "created_at": row["api_key_created_at"].isoformat() if row["api_key_created_at"] else None,
    }


async def set_user_api_key(user_id: str, api_key_hash: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """UPDATE users
           SET api_key_hash = $2,
               api_key_created_at = now()
           WHERE id = $1::uuid
           RETURNING api_key_created_at""",
        user_id,
        api_key_hash,
    )
    if not row:
        return None
    return {"created_at": row["api_key_created_at"].isoformat()}


async def get_user_by_api_key_hash(api_key_hash: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT id, username, role, email, email_verified, created_at, last_active_at
           FROM users
           WHERE api_key_hash = $1""",
        api_key_hash,
    )
    return _serialize_user_row(row) if row else None
