from .connection import get_pool
from .helpers import _serialize_user_row


async def search_users(
    q: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    pool = await get_pool()

    where = "TRUE"
    params: list = []
    idx = 1

    if q.strip():
        where = f"(u.username ILIKE ${idx} OR u.email ILIKE ${idx})"
        params.append(f"%{q.strip()}%")
        idx += 1

    total = await pool.fetchval(
        f"SELECT COUNT(*) FROM users u WHERE {where}",
        *params,
    )

    offset = (page - 1) * page_size
    rows = await pool.fetch(
        f"""
        SELECT
            u.id,
            u.username,
            u.role,
            u.email,
            u.email_verified,
            u.created_at,
            u.last_active_at,
            COALESCE(s.total_searches, 0)       AS total_searches,
            COALESCE(s.searches_7d, 0)           AS searches_7d,
            COALESCE(s.searches_3h, 0)           AS searches_3h,
            COALESCE(s.total_tokens, 0)          AS total_tokens,
            COALESCE(s.tokens_7d, 0)             AS tokens_7d,
            COALESCE(s.tokens_3h, 0)             AS tokens_3h
        FROM users u
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*)                                                                  AS total_searches,
                COUNT(*) FILTER (WHERE sl.created_at >= now() - interval '7 days')        AS searches_7d,
                COUNT(*) FILTER (WHERE sl.created_at >= now() - interval '3 hours')       AS searches_3h,
                SUM(sl.tokens_prompt + sl.tokens_completion)                              AS total_tokens,
                SUM(sl.tokens_prompt + sl.tokens_completion) FILTER (WHERE sl.created_at >= now() - interval '7 days')  AS tokens_7d,
                SUM(sl.tokens_prompt + sl.tokens_completion) FILTER (WHERE sl.created_at >= now() - interval '3 hours') AS tokens_3h
            FROM search_logs sl
            WHERE sl.user_id = u.id
        ) s ON TRUE
        WHERE {where}
        ORDER BY u.created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
        page_size,
        offset,
    )

    users = [
        {
            **_serialize_user_row(r),
            "total_searches": int(r["total_searches"]),
            "searches_7d": int(r["searches_7d"]),
            "searches_3h": int(r["searches_3h"]),
            "total_tokens": int(r["total_tokens"]),
            "tokens_7d": int(r["tokens_7d"]),
            "tokens_3h": int(r["tokens_3h"]),
        }
        for r in rows
    ]

    return {
        "users": users,
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


async def delete_user(user_id: str):
    pool = await get_pool()
    await pool.execute("DELETE FROM decks WHERE user_id = $1::uuid", user_id)
    await pool.execute("DELETE FROM users WHERE id = $1::uuid", user_id)


async def update_user_role(user_id: str, role: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE users SET role = $2 WHERE id = $1::uuid RETURNING id, username, role",
        user_id,
        role,
    )
    if not row:
        return None
    return {"id": str(row["id"]), "username": row["username"], "role": row["role"]}
