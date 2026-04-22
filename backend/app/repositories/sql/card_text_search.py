import re

from .connection import get_pool
from .card_result_rows import CARD_RESULT_COLUMNS, DEFAULT_PRINT_JOIN, serialize_card_result


async def text_match_cards(query: str, limit: int = 20) -> list[dict]:
    pool = await get_pool()
    escaped = re.sub(r"([\\.*+?^${}()|[\]])", r"\\\1", query)
    pattern = r"\m" + escaped + r"\M"
    rows = await pool.fetch(
        f"""SELECT {CARD_RESULT_COLUMNS},
                  CASE WHEN c.name ~* $1 THEN 0 ELSE 1 END AS sort_key
           FROM cards c
           {DEFAULT_PRINT_JOIN}
           WHERE NOT COALESCE(c.is_unofficial, FALSE)
             AND (
                 c.name ~* $1
                 OR c.oracle_text ~* $1
                 OR c.type_line ~* $1
             )
           ORDER BY sort_key, c.name
           LIMIT $2""",
        pattern,
        limit,
    )
    return [serialize_card_result(row) for row in rows]
