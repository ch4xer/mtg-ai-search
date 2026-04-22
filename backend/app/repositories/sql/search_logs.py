from .connection import get_pool

async def log_search(user_id: str | None, query: str, tokens_prompt: int, tokens_completion: int,
                     ip_address: str | None = None):
    """Log a search request with optional user and token usage."""
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO search_logs (user_id, query, tokens_prompt, tokens_completion, ip_address) VALUES ($1::uuid, $2, $3, $4, $5)",
        user_id, query, tokens_prompt, tokens_completion, ip_address,
    )

async def get_user_hourly_search_count(user_id: str) -> int:
    """Count AI searches in the last hour for a given user."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT COUNT(*) AS cnt FROM search_logs WHERE user_id = $1::uuid AND created_at >= now() - interval '1 hour'",
        user_id,
    )
    return int(row["cnt"]) if row else 0

async def get_ip_hourly_search_count(ip_address: str) -> int:
    """Count AI searches in the last hour for a given IP address."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT COUNT(*) AS cnt FROM search_logs WHERE ip_address = $1 AND user_id IS NULL AND created_at >= now() - interval '1 hour'",
        ip_address,
    )
    return int(row["cnt"]) if row else 0

