import json
import os
import re
import logging

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL", "postgresql://mtg:mtg_password@localhost:5432/mtg")
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
        logger.info("Created asyncpg connection pool")
    return _pool


async def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Closed asyncpg connection pool")


# Operators allowed in condition expressions like ">5", ">=2020-01-01"
_CONDITION_RE = re.compile(r"^(>=|<=|>|<|=)\s*(.+)$")


def _parse_condition(expr: str) -> tuple[str, str]:
    """Parse a condition expression like '>5' into (operator, value)."""
    m = _CONDITION_RE.match(expr.strip())
    if not m:
        return ("=", expr.strip())
    return (m.group(1), m.group(2).strip())


async def filter_cards(filters: dict) -> list[str]:
    """Filter cards by structured conditions. Returns list of card IDs.

    filters keys: released_at, layout, mana_cost, cmc, power, toughness, colors
    - Enumerable (colors, layout): exact match, e.g. "B R", "transform"
    - Non-enumerable (cmc, power, toughness, released_at, mana_cost): condition expr, e.g. ">5"
    """
    pool = await get_pool()

    clauses: list[str] = []
    params: list = []
    idx = 1

    for key, value in filters.items():
        if value is None:
            continue

        if key == "colors":
            # "B R" means colors must contain both B and R
            color_list = value.split()
            clauses.append(f"colors @> ${idx}::text[]")
            params.append(color_list)
            idx += 1

        elif key == "layout":
            clauses.append(f"layout = ${idx}")
            params.append(value)
            idx += 1

        elif key in ("cmc", "power", "toughness", "released_at", "mana_cost"):
            op, val = _parse_condition(value)
            col = key
            if key in ("cmc",):
                clauses.append(f"{col} {op} ${idx}::real")
                params.append(float(val))
            elif key in ("power", "toughness"):
                # power/toughness are TEXT, cast for numeric comparison
                clauses.append(f"CAST(NULLIF({col}, '*') AS real) {op} ${idx}::real")
                params.append(float(val))
            elif key == "released_at":
                clauses.append(f"{col} {op} ${idx}::date")
                params.append(val)
            elif key == "mana_cost":
                clauses.append(f"{col} {op} ${idx}")
                params.append(val)
            idx += 1

    if not clauses:
        return []

    where = " AND ".join(clauses)
    query = f"SELECT id FROM cards WHERE {where}"
    logger.info("filter_cards SQL: %s params: %s", query, params)

    rows = await pool.fetch(query, *params)
    return [row["id"] for row in rows]


_ALLOWED_EMBEDDING_COLUMNS = {"name_embedding", "type_line_embedding", "oracle_text_embedding"}


async def vector_search_cards(
    column: str,
    query_embedding: list[float],
    n_results: int = 20,
    card_ids: list[str] | None = None,
) -> list[tuple[str, float]]:
    """Vector search on a specific embedding column. Returns [(id, distance), ...]."""
    if column not in _ALLOWED_EMBEDDING_COLUMNS:
        raise ValueError(f"Invalid embedding column: {column!r}")

    pool = await get_pool()
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    if card_ids:
        query = f"""
            SELECT id, {column} <=> $1::vector AS distance
            FROM cards
            WHERE id = ANY($2) AND {column} IS NOT NULL
            ORDER BY distance
            LIMIT $3
        """
        rows = await pool.fetch(query, embedding_str, card_ids, n_results)
    else:
        query = f"""
            SELECT id, {column} <=> $1::vector AS distance
            FROM cards
            WHERE {column} IS NOT NULL
            ORDER BY distance
            LIMIT $2
        """
        rows = await pool.fetch(query, embedding_str, n_results)

    return [(row["id"], row["distance"]) for row in rows]


async def search_abilities(
    query_embedding: list[float],
    n_results: int = 5,
    distance_threshold: float = 0.2,
) -> list[dict]:
    """Search keyword abilities by vector similarity."""
    pool = await get_pool()
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    rows = await pool.fetch(
        """
        SELECT name, description, embedding <=> $1::vector AS distance
        FROM keyword_abilities
        WHERE embedding IS NOT NULL AND embedding <=> $1::vector < $3
        ORDER BY distance
        LIMIT $2
        """,
        embedding_str,
        n_results,
        distance_threshold,
    )

    return [
        {"name": row["name"], "description": row["description"], "distance": row["distance"]}
        for row in rows
    ]


async def get_cards_by_ids(card_ids: list[str]) -> list[dict]:
    """Retrieve full card data by IDs, preserving order."""
    if not card_ids:
        return []

    pool = await get_pool()
    rows = await pool.fetch("SELECT id, data FROM cards WHERE id = ANY($1)", card_ids)

    card_map = {}
    for row in rows:
        card_map[row["id"]] = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]

    return [card_map[cid] for cid in card_ids if cid in card_map]
