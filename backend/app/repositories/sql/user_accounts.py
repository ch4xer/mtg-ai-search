from .connection import get_pool
from .helpers import _serialize_user_row


async def create_user(
    username: str,
    password_hash: str,
    role: str = "user",
    email: str | None = None,
    email_verified: bool = False,
) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO users (username, password_hash, role, email, email_verified)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING id, username, role, email, email_verified, created_at""",
        username,
        password_hash,
        role,
        email,
        email_verified,
    )
    return {
        "id": str(row["id"]),
        "username": row["username"],
        "role": row["role"],
        "email": row["email"],
        "email_verified": row["email_verified"],
    }


async def get_user_by_username(username: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, password_hash, role, email, email_verified FROM users WHERE username = $1",
        username,
    )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "username": row["username"],
        "password_hash": row["password_hash"],
        "role": row["role"],
        "email": row["email"],
        "email_verified": row["email_verified"],
    }


async def get_user_by_email(email: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, role, email, email_verified FROM users WHERE email = $1",
        email,
    )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "username": row["username"],
        "role": row["role"],
        "email": row["email"],
        "email_verified": row["email_verified"],
    }


async def get_user_by_id(user_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, role, email, email_verified, created_at, last_active_at FROM users WHERE id = $1::uuid",
        user_id,
    )
    if not row:
        return None
    return _serialize_user_row(row)


async def update_last_active(user_id: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET last_active_at = now() WHERE id = $1::uuid",
        user_id,
    )


async def update_user_password(user_id: str, password_hash: str) -> bool:
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE users SET password_hash = $1 WHERE id = $2::uuid",
        password_hash,
        user_id,
    )
    return result == "UPDATE 1"
