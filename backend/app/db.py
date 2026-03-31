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
            # "B R" means colors must contain both B and R; "C" for colorless
            color_list = value.split()
            clauses.append(f"colors @> ${idx}::text[]")
            params.append(color_list)
            idx += 1

        elif key == "type":
            # "Creature Avatar" means type_line must contain both words
            for word in value.split():
                clauses.append(f"type_line ILIKE ${idx}")
                params.append(f"%{word}%")
                idx += 1

        elif key == "keywords":
            # keywords && ARRAY[...] means at least one keyword matches
            clauses.append(f"keywords && ${idx}::text[]")
            params.append(value)  # already a list
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
                from datetime import date as date_type
                clauses.append(f"{col} {op} ${idx}::date")
                params.append(date_type.fromisoformat(val))
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


# ── User functions ──────────────────────────────────────────────────────


async def create_user(username: str, password_hash: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO users (username, password_hash) VALUES ($1, $2) RETURNING id, username, created_at",
        username, password_hash,
    )
    return {"id": str(row["id"]), "username": row["username"]}


async def get_user_by_username(username: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, password_hash FROM users WHERE username = $1",
        username,
    )
    if not row:
        return None
    return {"id": str(row["id"]), "username": row["username"], "password_hash": row["password_hash"]}


# ── Deck functions ──────────────────────────────────────────────────────


async def create_deck(user_id: str, name: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO decks (user_id, name) VALUES ($1::uuid, $2) RETURNING id, name, created_at",
        user_id, name,
    )
    return {"id": str(row["id"]), "name": row["name"], "created_at": row["created_at"].isoformat()}


async def get_user_decks(user_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT d.id, d.name, d.created_at, d.updated_at,
                  COALESCE(SUM(dc.quantity), 0) AS card_count
           FROM decks d
           LEFT JOIN deck_cards dc ON dc.deck_id = d.id
           WHERE d.user_id = $1::uuid
           GROUP BY d.id
           ORDER BY d.updated_at DESC""",
        user_id,
    )
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "card_count": int(r["card_count"]),
            "created_at": r["created_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
        }
        for r in rows
    ]


async def get_deck(deck_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT id, user_id, name, created_at, updated_at FROM decks WHERE id = $1::uuid", deck_id)
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


async def update_deck(deck_id: str, name: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE decks SET name = $1, updated_at = now() WHERE id = $2::uuid RETURNING id, name, updated_at",
        name, deck_id,
    )
    return {"id": str(row["id"]), "name": row["name"], "updated_at": row["updated_at"].isoformat()}


async def delete_deck(deck_id: str):
    pool = await get_pool()
    await pool.execute("DELETE FROM decks WHERE id = $1::uuid", deck_id)


async def get_deck_cards(deck_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT dc.card_id, dc.quantity, dc.added_at, c.data
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           WHERE dc.deck_id = $1::uuid
           ORDER BY dc.added_at DESC""",
        deck_id,
    )
    return [
        {
            "card": json.loads(r["data"]) if isinstance(r["data"], str) else r["data"],
            "quantity": r["quantity"],
            "added_at": r["added_at"].isoformat(),
        }
        for r in rows
    ]


async def add_card_to_deck(deck_id: str, card_id: str, quantity: int = 1) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO deck_cards (deck_id, card_id, quantity)
           VALUES ($1::uuid, $2, $3)
           ON CONFLICT (deck_id, card_id)
           DO UPDATE SET quantity = deck_cards.quantity + EXCLUDED.quantity
           RETURNING card_id, quantity""",
        deck_id, card_id, quantity,
    )
    return {"card_id": row["card_id"], "quantity": row["quantity"]}


async def remove_card_from_deck(deck_id: str, card_id: str):
    pool = await get_pool()
    await pool.execute("DELETE FROM deck_cards WHERE deck_id = $1::uuid AND card_id = $2", deck_id, card_id)
