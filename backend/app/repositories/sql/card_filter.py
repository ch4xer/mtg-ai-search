import logging

from .connection import get_pool
from .helpers import _parse_condition

logger = logging.getLogger(__name__)


async def filter_cards(filters: dict) -> list[str]:
    pool = await get_pool()

    clauses: list[str] = []
    params: list = []
    idx = 1

    for key, value in filters.items():
        if value is None:
            continue

        if key == "colors":
            clauses.append(f"colors @> ${idx}::text[]")
            params.append(value.split())
            idx += 1
        elif key == "type":
            for word in value.split():
                clauses.append(f"type_line ILIKE ${idx}")
                params.append(f"%{word}%")
                idx += 1
        elif key == "keywords":
            clauses.append(f"keywords && ${idx}::text[]")
            params.append(value)
            idx += 1
        elif key == "layout":
            clauses.append(f"layout = ${idx}")
            params.append(value)
            idx += 1
        elif key in ("cmc", "power", "toughness", "released_at", "mana_cost"):
            idx = _append_condition_filter(clauses, params, idx, key, value)

    if not clauses:
        return []

    where = " AND ".join(clauses)
    query = f"SELECT id FROM cards WHERE {where}"
    logger.info("filter_cards SQL: %s params: %s", query, params)

    rows = await pool.fetch(query, *params)
    return [row["id"] for row in rows]


def _append_condition_filter(clauses: list[str], params: list, idx: int, key: str, value: str) -> int:
    op, val = _parse_condition(value)
    if key == "cmc":
        clauses.append(f"{key} {op} ${idx}::real")
        params.append(float(val))
    elif key in ("power", "toughness"):
        clauses.append(f"CAST(NULLIF({key}, '*') AS real) {op} ${idx}::real")
        params.append(float(val))
    elif key == "released_at":
        from datetime import date as date_type

        clauses.append(
            f"EXISTS (SELECT 1 FROM card_prints cp WHERE cp.card_id = cards.id AND cp.released_at {op} ${idx}::date)"
        )
        params.append(date_type.fromisoformat(val))
    elif key == "mana_cost":
        clauses.append(f"{key} {op} ${idx}")
        params.append(val)
    return idx + 1
