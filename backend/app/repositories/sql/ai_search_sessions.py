import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from .connection import get_pool


def _normalize_uuid(value: str) -> str | None:
    try:
        return str(UUID(value))
    except (TypeError, ValueError):
        return None


def _decode_plan(value) -> dict:
    if isinstance(value, (str, bytes)):
        return json.loads(value)
    return value if isinstance(value, dict) else {}


async def create_ai_search_session(
    *,
    query: str,
    plan: dict,
    user_id: str | None,
    ip_address: str | None,
    ttl_seconds: int,
) -> str:
    pool = await get_pool()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(1, ttl_seconds))
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM ai_search_sessions WHERE expires_at <= now()")
        row = await conn.fetchrow(
            """
            INSERT INTO ai_search_sessions (user_id, query, plan, ip_address, expires_at)
            VALUES ($1::uuid, $2, $3::jsonb, $4, $5)
            RETURNING id
            """,
            user_id,
            query,
            json.dumps(plan),
            ip_address,
            expires_at,
        )
    return str(row["id"])


async def get_ai_search_session(
    *,
    search_id: str,
    user_id: str | None,
    ip_address: str | None,
) -> dict | None:
    normalized_id = _normalize_uuid(search_id)
    if normalized_id is None:
        return None

    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT id, user_id, query, plan, ip_address, created_at, expires_at
        FROM ai_search_sessions
        WHERE id = $1::uuid
          AND expires_at > now()
          AND (
                ($2::uuid IS NOT NULL AND user_id = $2::uuid)
             OR ($2::uuid IS NULL AND user_id IS NULL AND ip_address = $3)
          )
        """,
        normalized_id,
        user_id,
        ip_address,
    )
    if not row:
        return None

    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]) if row["user_id"] else None,
        "query": row["query"],
        "plan": _decode_plan(row["plan"]),
        "ip_address": row["ip_address"],
        "created_at": row["created_at"].isoformat(),
        "expires_at": row["expires_at"].isoformat(),
    }
