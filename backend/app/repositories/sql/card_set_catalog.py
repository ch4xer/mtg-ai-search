"""Queries for the card-set selector used by Exact Match."""

from .connection import get_pool


async def get_card_set_catalog() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT cp.set_code,
                  MAX(cp.set_name) AS set_name,
                  MAX(zt.set_name) FILTER (WHERE zt.set_name IS NOT NULL) AS zh_set_name,
                  MAX(cp.set_type) AS set_type,
                  MIN(cp.released_at) AS released_at,
                  COUNT(DISTINCT cp.card_id) AS card_count
           FROM card_prints cp
           LEFT JOIN card_print_translations zt
             ON zt.print_id = cp.id
            AND zt.lang = 'zhs'
            AND zt.status = 'ok'
           WHERE cp.set_code IS NOT NULL
             AND cp.set_code <> ''
           GROUP BY cp.set_code
           ORDER BY released_at DESC NULLS LAST, cp.set_code"""
    )
    return [
        {
            "code": row["set_code"],
            "name": row["set_name"],
            "zh_name": row["zh_set_name"],
            "set_type": row["set_type"],
            "released_at": row["released_at"].isoformat() if row["released_at"] else None,
            "card_count": int(row["card_count"]),
        }
        for row in rows
    ]
