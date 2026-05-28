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
            column = _color_filter_column(key)
            mode, symbols = _parse_color_filter(value)
            operator = "&&" if mode == "any" else "@>"
            clauses.append(f"COALESCE({column}, ARRAY[]::text[]) {operator} ${idx}::text[]")
            params.append(symbols)
            idx += 1
            if mode == "exact":
                clauses.append(f"cardinality(COALESCE({column}, ARRAY[]::text[])) = ${idx}")
                params.append(len(symbols))
                idx += 1
        elif key == "excluded_colors":
            column = _color_filter_column(key.removeprefix("excluded_"))
            _, symbols = _parse_color_filter(value)
            clauses.append(f"NOT (COALESCE({column}, ARRAY[]::text[]) && ${idx}::text[])")
            params.append(symbols)
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
        elif key in ("cmc", "power", "toughness", "released_at"):
            idx = _append_condition_filter(clauses, params, idx, key, value)

    if not clauses:
        return []

    where = " AND ".join(["NOT COALESCE(is_unofficial, FALSE)", *clauses])
    query = f"SELECT id FROM cards WHERE {where}"
    logger.info("filter_cards SQL: %s params: %s", query, params)

    rows = await pool.fetch(query, *params)
    return [row["id"] for row in rows]


def _parse_color_filter(value: str) -> tuple[str, list[str]]:
    raw = str(value or "").strip()
    if raw.startswith("="):
        raw = raw[1:].strip()
        return "exact", raw.split()
    if raw.lower().startswith("any:"):
        raw = raw[4:].strip()
        return "any", raw.split()
    return "all", raw.split()


def _color_filter_column(key: str) -> str:
    return "colors"


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
    return idx + 1
