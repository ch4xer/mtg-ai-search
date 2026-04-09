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
            SELECT id, {column} <=> $1::halfvec AS distance
            FROM cards
            WHERE id = ANY($2) AND {column} IS NOT NULL
            ORDER BY distance
            LIMIT $3
        """
        rows = await pool.fetch(query, embedding_str, card_ids, n_results)
    else:
        query = f"""
            SELECT id, {column} <=> $1::halfvec AS distance
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
        SELECT name, description, embedding <=> $1::halfvec AS distance
        FROM keyword_abilities
        WHERE embedding IS NOT NULL AND embedding <=> $1::halfvec < $3
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


async def create_user(username: str, password_hash: str, role: str = "user") -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, $3) RETURNING id, username, role, created_at",
        username, password_hash, role,
    )
    return {"id": str(row["id"]), "username": row["username"], "role": row["role"]}


async def get_user_by_username(username: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, password_hash, role FROM users WHERE username = $1",
        username,
    )
    if not row:
        return None
    return {"id": str(row["id"]), "username": row["username"], "password_hash": row["password_hash"], "role": row["role"]}


async def get_user_by_id(user_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, role, created_at FROM users WHERE id = $1::uuid",
        user_id,
    )
    if not row:
        return None
    return {"id": str(row["id"]), "username": row["username"], "role": row["role"], "created_at": row["created_at"].isoformat()}


async def list_all_users() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch("SELECT id, username, role, created_at FROM users ORDER BY created_at")
    return [
        {"id": str(r["id"]), "username": r["username"], "role": r["role"], "created_at": r["created_at"].isoformat()}
        for r in rows
    ]


async def delete_user(user_id: str):
    pool = await get_pool()
    await pool.execute("DELETE FROM decks WHERE user_id = $1::uuid", user_id)
    await pool.execute("DELETE FROM users WHERE id = $1::uuid", user_id)


async def update_user_role(user_id: str, role: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE users SET role = $2 WHERE id = $1::uuid RETURNING id, username, role",
        user_id, role,
    )
    if not row:
        return None
    return {"id": str(row["id"]), "username": row["username"], "role": row["role"]}


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
        """SELECT dc.card_id, dc.quantity, dc.added_at, dc.image_url, dc.display_url, c.data
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           WHERE dc.deck_id = $1::uuid
           ORDER BY dc.added_at DESC""",
        deck_id,
    )
    return [
        {
            "card_id": r["card_id"],
            "card": json.loads(r["data"]) if isinstance(r["data"], str) else r["data"],
            "quantity": r["quantity"],
            "image_url": r["image_url"],
            "display_url": r["display_url"],
            "added_at": r["added_at"].isoformat(),
        }
        for r in rows
    ]


async def add_card_to_deck(
    deck_id: str, card_id: str, quantity: int = 1,
    image_url: str | None = None, display_url: str | None = None,
    update_image: bool = False,
) -> dict:
    pool = await get_pool()
    if update_image:
        row = await pool.fetchrow(
            """INSERT INTO deck_cards (deck_id, card_id, quantity, image_url, display_url)
               VALUES ($1::uuid, $2, $3, $4, $5)
               ON CONFLICT (deck_id, card_id)
               DO UPDATE SET quantity = deck_cards.quantity + EXCLUDED.quantity,
                             image_url = $4,
                             display_url = $5
               RETURNING card_id, quantity""",
            deck_id, card_id, quantity, image_url, display_url,
        )
    else:
        row = await pool.fetchrow(
            """INSERT INTO deck_cards (deck_id, card_id, quantity, image_url, display_url)
               VALUES ($1::uuid, $2, $3, $4, $5)
               ON CONFLICT (deck_id, card_id)
               DO UPDATE SET quantity = deck_cards.quantity + EXCLUDED.quantity,
                             image_url = COALESCE(EXCLUDED.image_url, deck_cards.image_url),
                             display_url = COALESCE(EXCLUDED.display_url, deck_cards.display_url)
               RETURNING card_id, quantity""",
            deck_id, card_id, quantity, image_url, display_url,
        )
    return {"card_id": row["card_id"], "quantity": row["quantity"]}


async def remove_card_from_deck(deck_id: str, card_id: str):
    pool = await get_pool()
    await pool.execute("DELETE FROM deck_cards WHERE deck_id = $1::uuid AND card_id = $2", deck_id, card_id)


async def get_cards_by_names(names: list[str]) -> dict[str, str]:
    """Look up card IDs by exact name (case-insensitive). Returns {name_lower: card_id}.

    Also matches double-faced cards by front face name (before ' // ').
    """
    if not names:
        return {}
    pool = await get_pool()
    lowered = [n.lower() for n in names]
    rows = await pool.fetch(
        """SELECT id, name FROM cards
           WHERE LOWER(name) = ANY($1)
              OR LOWER(split_part(name, ' // ', 1)) = ANY($1)""",
        lowered,
    )
    result: dict[str, str] = {}
    for row in rows:
        full = row["name"].lower()
        front = full.split(" // ")[0]
        # Map both full name and front face name to the card id
        if full not in result:
            result[full] = row["id"]
        if front not in result:
            result[front] = row["id"]
    return result


async def get_deck_cards_for_export(deck_id: str) -> list[dict]:
    """Get card names and quantities for text export.

    Uses only the front face name for double-faced cards.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT split_part(c.name, ' // ', 1) AS name, dc.quantity
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           WHERE dc.deck_id = $1::uuid
           ORDER BY name""",
        deck_id,
    )
    return [{"name": r["name"], "quantity": r["quantity"]} for r in rows]


_MAIN_TYPES = [
    "Creature", "Instant", "Sorcery", "Enchantment", "Artifact",
    "Land", "Planeswalker", "Battle", "Kindred",
]


async def discover_cards(
    q: str = "",
    colors: list[str] | None = None,
    types: list[str] | None = None,
    rarities: list[str] | None = None,
    keywords: list[str] | None = None,
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    power_min: float | None = None,
    power_max: float | None = None,
    subtypes: list[str] | None = None,
    toughness_min: float | None = None,
    toughness_max: float | None = None,
    include_playtest: bool = False,
    page: int = 1,
    page_size: int = 60,
) -> dict:
    """Discover cards with full-text keyword search, faceted filters, and pagination.

    Keyword search: space-separated terms are AND-ed.
    Each term matches case-insensitively against name, type_line, or oracle_text.
    """
    pool = await get_pool()

    clauses: list[str] = []
    params: list = []
    idx = 1

    # Exclude playtest cards by default
    if not include_playtest:
        clauses.append("NOT is_playtest")

    # Keyword search — each space-separated token must appear somewhere
    if q.strip():
        for token in q.strip().split():
            clauses.append(
                f"(name ILIKE ${idx} OR type_line ILIKE ${idx} OR oracle_text ILIKE ${idx})"
            )
            params.append(f"%{token}%")
            idx += 1

    # Color filter — card has at least one of the selected colors
    if colors:
        clauses.append(f"colors && ${idx}::text[]")
        params.append(colors)
        idx += 1

    # Type filter — card type_line contains at least one of the selected types
    if types:
        type_conds = []
        for t in types:
            type_conds.append(f"type_line ILIKE ${idx}")
            params.append(f"%{t}%")
            idx += 1
        clauses.append(f"({' OR '.join(type_conds)})")

    # Subtype filter — matches subtypes after the em dash in type_line
    if subtypes:
        sub_conds = []
        for st in subtypes:
            sub_conds.append(f"split_part(type_line, '\u2014', 2) ILIKE ${idx}")
            params.append(f"%{st}%")
            idx += 1
        clauses.append(f"({' OR '.join(sub_conds)})")

    # Rarity filter
    if rarities:
        clauses.append(f"data->>'rarity' = ANY(${idx}::text[])")
        params.append(rarities)
        idx += 1

    # Keyword abilities filter — card has at least one of the selected keywords
    if keywords:
        clauses.append(f"keywords && ${idx}::text[]")
        params.append(keywords)
        idx += 1

    # CMC range
    if cmc_min is not None:
        clauses.append(f"cmc >= ${idx}::real")
        params.append(float(cmc_min))
        idx += 1
    if cmc_max is not None:
        clauses.append(f"cmc <= ${idx}::real")
        params.append(float(cmc_max))
        idx += 1

    # Power range (only match numeric values via regex)
    if power_min is not None:
        clauses.append(f"power ~ '^[0-9]+\\.?[0-9]*$' AND CAST(power AS real) >= ${idx}::real")
        params.append(float(power_min))
        idx += 1
    if power_max is not None:
        clauses.append(f"power ~ '^[0-9]+\\.?[0-9]*$' AND CAST(power AS real) <= ${idx}::real")
        params.append(float(power_max))
        idx += 1

    # Toughness range (only match numeric values via regex)
    if toughness_min is not None:
        clauses.append(f"toughness ~ '^[0-9]+\\.?[0-9]*$' AND CAST(toughness AS real) >= ${idx}::real")
        params.append(float(toughness_min))
        idx += 1
    if toughness_max is not None:
        clauses.append(f"toughness ~ '^[0-9]+\\.?[0-9]*$' AND CAST(toughness AS real) <= ${idx}::real")
        params.append(float(toughness_max))
        idx += 1

    where = " AND ".join(clauses) if clauses else "TRUE"

    # ── Total count ──
    total = await pool.fetchval(f"SELECT COUNT(*) FROM cards WHERE {where}", *params)

    # ── Paginated results ──
    offset = (page - 1) * page_size
    limit_idx = idx
    offset_idx = idx + 1
    rows = await pool.fetch(
        f"SELECT data FROM cards WHERE {where} ORDER BY name LIMIT ${limit_idx} OFFSET ${offset_idx}",
        *params, page_size, offset,
    )
    cards = [
        json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
        for row in rows
    ]

    # ── Facet counts (computed from the fully-filtered set) ──

    # Colors
    color_rows = await pool.fetch(
        f"SELECT c AS val, COUNT(*) AS cnt FROM cards, unnest(colors) AS c WHERE {where} GROUP BY c ORDER BY cnt DESC",
        *params,
    )
    color_facets = {r["val"]: int(r["cnt"]) for r in color_rows}

    # Rarity
    rarity_rows = await pool.fetch(
        f"SELECT data->>'rarity' AS val, COUNT(*) AS cnt FROM cards WHERE {where} AND data->>'rarity' IS NOT NULL GROUP BY val ORDER BY cnt DESC",
        *params,
    )
    rarity_facets = {r["val"]: int(r["cnt"]) for r in rarity_rows}

    # Types — count each main type via FILTER
    type_cases = ", ".join(
        f"COUNT(*) FILTER (WHERE type_line ILIKE '%%{t}%%') AS \"{t}\""
        for t in _MAIN_TYPES
    )
    type_row = await pool.fetchrow(
        f"SELECT {type_cases} FROM cards WHERE {where}",
        *params,
    )
    type_facets = {t: int(type_row[t]) for t in _MAIN_TYPES if type_row[t]}

    # Keywords (top 30)
    kw_rows = await pool.fetch(
        f"SELECT k AS val, COUNT(*) AS cnt FROM cards, unnest(keywords) AS k WHERE {where} GROUP BY k ORDER BY cnt DESC LIMIT 30",
        *params,
    )
    keyword_facets = [{"name": r["val"], "count": int(r["cnt"])} for r in kw_rows]

    # Subtypes — extract words after the em dash (top 40)
    subtype_rows = await pool.fetch(
        f"""SELECT s AS val, COUNT(*) AS cnt
            FROM (
                SELECT unnest(string_to_array(
                    trim(split_part(type_line, '\u2014', 2)), ' '
                )) AS s
                FROM cards
                WHERE {where} AND type_line LIKE '%%\u2014%%'
            ) sub
            WHERE s != ''
            GROUP BY s ORDER BY cnt DESC LIMIT 40""",
        *params,
    )
    subtype_facets = [{"name": r["val"], "count": int(r["cnt"])} for r in subtype_rows]

    # CMC / power / toughness ranges
    # Use regex to only cast values that are pure numbers (int or decimal)
    range_row = await pool.fetchrow(
        f"""SELECT
                MIN(cmc) AS cmc_min, MAX(cmc) AS cmc_max,
                MIN(CAST(power AS real)) FILTER (WHERE power ~ '^[0-9]+\\.?[0-9]*$') AS power_min,
                MAX(CAST(power AS real)) FILTER (WHERE power ~ '^[0-9]+\\.?[0-9]*$') AS power_max,
                MIN(CAST(toughness AS real)) FILTER (WHERE toughness ~ '^[0-9]+\\.?[0-9]*$') AS toughness_min,
                MAX(CAST(toughness AS real)) FILTER (WHERE toughness ~ '^[0-9]+\\.?[0-9]*$') AS toughness_max
            FROM cards WHERE {where}""",
        *params,
    )

    return {
        "results": cards,
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "facets": {
            "colors": color_facets,
            "types": type_facets,
            "rarities": rarity_facets,
            "keywords": keyword_facets,
            "subtypes": subtype_facets,
            "cmc_range": {
                "min": float(range_row["cmc_min"]) if range_row["cmc_min"] is not None else 0,
                "max": float(range_row["cmc_max"]) if range_row["cmc_max"] is not None else 0,
            },
            "power_range": {
                "min": float(range_row["power_min"]) if range_row["power_min"] is not None else 0,
                "max": float(range_row["power_max"]) if range_row["power_max"] is not None else 0,
            },
            "toughness_range": {
                "min": float(range_row["toughness_min"]) if range_row["toughness_min"] is not None else 0,
                "max": float(range_row["toughness_max"]) if range_row["toughness_max"] is not None else 0,
            },
        },
    }


async def get_deck_card_images(deck_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT dc.quantity, c.name,
                  COALESCE(dc.image_url,
                           c.image_png,
                           c.data->'image_uris'->>'png',
                           c.data->'card_faces'->0->'image_uris'->>'png') AS png_url,
                  c.data->'card_faces'->1->'image_uris'->>'png' AS back_png_url,
                  c.data->'card_faces'->1->>'name' AS back_name
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           WHERE dc.deck_id = $1::uuid
           ORDER BY dc.added_at""",
        deck_id,
    )
    return [dict(r) for r in rows]
