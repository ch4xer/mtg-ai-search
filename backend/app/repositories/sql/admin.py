"""Admin SQL queries."""

from .connection import get_pool


async def get_dashboard_stats() -> dict:
    pool = await get_pool()

    total_cards = await pool.fetchval("SELECT COUNT(*) FROM cards")
    total_abilities = await pool.fetchval("SELECT COUNT(*) FROM keyword_abilities")
    cards_missing = await pool.fetchval("SELECT COUNT(*) FROM cards WHERE name_embedding IS NULL")
    abilities_missing = await pool.fetchval("SELECT COUNT(*) FROM keyword_abilities WHERE embedding IS NULL")
    last_sync = await pool.fetchval("SELECT value FROM app_meta WHERE key = 'last_sync_updated_at'")

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
        "popular_queries": [{"query": r["query"], "count": int(r["cnt"])} for r in popular],
    }


async def get_sync_logs(limit: int = 30) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id, started_at, completed_at, status, new_cards, updated_cards, message
           FROM sync_logs ORDER BY started_at DESC LIMIT $1""",
        limit,
    )
    return [dict(row) for row in rows]


async def persist_rate_limit_settings(anon_hourly_limit: int | None, user_hourly_limit: int | None) -> None:
    pool = await get_pool()
    if anon_hourly_limit is not None:
        await pool.execute(
            """INSERT INTO app_meta (key, value) VALUES ('anon_hourly_limit', $1)
               ON CONFLICT (key) DO UPDATE SET value = $1""",
            str(anon_hourly_limit),
        )
    if user_hourly_limit is not None:
        await pool.execute(
            """INSERT INTO app_meta (key, value) VALUES ('user_hourly_limit', $1)
               ON CONFLICT (key) DO UPDATE SET value = $1""",
            str(user_hourly_limit),
        )

