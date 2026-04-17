import json
import logging
import os
import re

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None
DEFAULT_DATABASE_URL = "postgresql://mtg:mtg_password@localhost:5432/mtg"
_ALLOWED_EMBEDDING_COLUMNS = {"name_embedding", "type_line_embedding", "oracle_text_embedding"}
_MAIN_TYPES = [
    "Creature",
    "Instant",
    "Sorcery",
    "Enchantment",
    "Artifact",
    "Land",
    "Planeswalker",
    "Battle",
    "Kindred",
]


async def get_pool() -> asyncpg.Pool:
    """Get or create the connection pool."""
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
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


def _decode_card_data(value):
    return json.loads(value) if isinstance(value, str) else value


def _serialize_user_row(row) -> dict:
    result = {
        "id": str(row["id"]),
        "username": row["username"],
        "role": row["role"],
        "created_at": row["created_at"].isoformat(),
    }
    if "email" in row.keys():
        result["email"] = row["email"]
        result["email_verified"] = row["email_verified"]
    if "last_active_at" in row.keys():
        result["last_active_at"] = row["last_active_at"].isoformat() if row["last_active_at"] else None
    return result


def _serialize_deck_row(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "format": row["format"],
        "created_at": row["created_at"].isoformat(),
    }


def _serialize_analysis(row) -> dict | None:
    # Nested {"zh": {...}, "en": {...}, "updated_at": "..."} or null.
    if not row["analysis_updated_at"] or not row["analysis_data"]:
        return None
    raw = row["analysis_data"]
    data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    return {
        "zh": data.get("zh"),
        "en": data.get("en"),
        "updated_at": row["analysis_updated_at"].isoformat(),
    }


def _serialize_deck_summary_row(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "format": row["format"],
        "card_count": int(row["card_count"]),
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "analysis": _serialize_analysis(row),
    }


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

    clauses.append("NOT is_playtest")
    where = " AND ".join(clauses)
    query = f"SELECT id FROM cards WHERE {where}"
    logger.info("filter_cards SQL: %s params: %s", query, params)

    rows = await pool.fetch(query, *params)
    return [row["id"] for row in rows]

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
            WHERE id = ANY($2) AND {column} IS NOT NULL AND NOT is_playtest
            ORDER BY distance
            LIMIT $3
        """
        rows = await pool.fetch(query, embedding_str, card_ids, n_results)
    else:
        query = f"""
            SELECT id, {column} <=> $1::halfvec AS distance
            FROM cards
            WHERE {column} IS NOT NULL AND NOT is_playtest
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

    card_map = {row["id"]: _decode_card_data(row["data"]) for row in rows}

    return [card_map[cid] for cid in card_ids if cid in card_map]


async def get_all_keywords() -> list[str]:
    """Return all keyword ability names from the database."""
    pool = await get_pool()
    rows = await pool.fetch("SELECT name FROM keyword_abilities ORDER BY name")
    return [row["name"] for row in rows]


async def text_match_cards(query: str, limit: int = 20) -> list[dict]:
    """Search cards by whole-word match on name, oracle_text, or type_line.

    Returns full card data for matches, deduplicated by name (keeps the
    newest printing), prioritising name matches first.
    """
    pool = await get_pool()
    escaped = re.sub(r'([\\.*+?^${}()|[\]])', r'\\\1', query)
    pattern = r'\m' + escaped + r'\M'
    rows = await pool.fetch(
        """SELECT data FROM (
             SELECT DISTINCT ON (name) data,
                    CASE WHEN name ~* $1 THEN 0 ELSE 1 END AS sort_key
             FROM cards
             WHERE name ~* $1
                OR data->>'oracle_text' ~* $1
                OR data->>'type_line' ~* $1
             ORDER BY name, data->>'released_at' DESC
           ) sub
           ORDER BY sort_key, sub.data->>'name'
           LIMIT $2""",
        pattern, limit,
    )
    return [_decode_card_data(row["data"]) for row in rows]


# ── User functions ──────────────────────────────────────────────────────


async def create_user(username: str, password_hash: str, role: str = "user",
                      email: str | None = None, email_verified: bool = False) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """INSERT INTO users (username, password_hash, role, email, email_verified)
           VALUES ($1, $2, $3, $4, $5)
           RETURNING id, username, role, email, email_verified, created_at""",
        username, password_hash, role, email, email_verified,
    )
    return {
        "id": str(row["id"]), "username": row["username"], "role": row["role"],
        "email": row["email"], "email_verified": row["email_verified"],
    }


async def get_user_by_username(username: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, password_hash, role, email, email_verified FROM users WHERE username = $1",
        username,
    )
    if not row:
        return None
    return {
        "id": str(row["id"]), "username": row["username"],
        "password_hash": row["password_hash"], "role": row["role"],
        "email": row["email"], "email_verified": row["email_verified"],
    }


async def get_user_by_email(email: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, role, email, email_verified FROM users WHERE email = $1",
        email,
    )
    if not row:
        return None
    return {
        "id": str(row["id"]), "username": row["username"], "role": row["role"],
        "email": row["email"], "email_verified": row["email_verified"],
    }


MAX_VERIFICATION_ATTEMPTS = 5


async def set_verification_code(user_id: str, code: str, expires_at) -> None:
    pool = await get_pool()
    await pool.execute(
        """UPDATE users SET verification_code = $1, verification_code_expires_at = $2,
                           verification_attempts = 0
           WHERE id = $3::uuid""",
        code, expires_at, user_id,
    )


async def verify_user_email(user_id: str, code: str) -> str:
    """Check the verification code and mark email as verified.

    Returns: "ok", "invalid", or "too_many_attempts".
    """
    pool = await get_pool()
    # Check attempt count first
    row = await pool.fetchrow(
        "SELECT verification_attempts, verification_code, verification_code_expires_at FROM users WHERE id = $1::uuid",
        user_id,
    )
    if not row:
        return "invalid"
    if row["verification_attempts"] >= MAX_VERIFICATION_ATTEMPTS:
        return "too_many_attempts"

    # Increment attempts
    await pool.execute(
        "UPDATE users SET verification_attempts = verification_attempts + 1 WHERE id = $1::uuid",
        user_id,
    )

    # Try to verify
    matched = await pool.fetchrow(
        """UPDATE users SET email_verified = TRUE, verification_code = NULL,
                           verification_code_expires_at = NULL, verification_attempts = 0
           WHERE id = $1::uuid AND verification_code = $2
             AND verification_code_expires_at > now()
           RETURNING id""",
        user_id, code,
    )
    return "ok" if matched else "invalid"


async def update_last_active(user_id: str) -> None:
    """Touch the last_active_at timestamp for a user."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE users SET last_active_at = now() WHERE id = $1::uuid",
        user_id,
    )


async def update_user_password(user_id: str, password_hash: str) -> bool:
    """Update a user's password hash. Returns True if the user was found."""
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE users SET password_hash = $1 WHERE id = $2::uuid",
        password_hash, user_id,
    )
    return result == "UPDATE 1"


async def get_user_by_id(user_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, username, role, email, email_verified, created_at, last_active_at FROM users WHERE id = $1::uuid",
        user_id,
    )
    if not row:
        return None
    return _serialize_user_row(row)


async def list_all_users() -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch("SELECT id, username, role, email, email_verified, created_at, last_active_at FROM users ORDER BY created_at")
    return [_serialize_user_row(row) for row in rows]


async def search_users(
    q: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Search and paginate users with search stats."""
    pool = await get_pool()

    where = "TRUE"
    params: list = []
    idx = 1

    if q.strip():
        where = f"(u.username ILIKE ${idx} OR u.email ILIKE ${idx})"
        params.append(f"%{q.strip()}%")
        idx += 1

    total = await pool.fetchval(
        f"SELECT COUNT(*) FROM users u WHERE {where}",
        *params,
    )

    offset = (page - 1) * page_size
    rows = await pool.fetch(f"""
        SELECT
            u.id,
            u.username,
            u.role,
            u.email,
            u.email_verified,
            u.created_at,
            u.last_active_at,
            COALESCE(s.total_searches, 0)       AS total_searches,
            COALESCE(s.searches_7d, 0)           AS searches_7d,
            COALESCE(s.searches_3h, 0)           AS searches_3h,
            COALESCE(s.total_tokens, 0)          AS total_tokens,
            COALESCE(s.tokens_7d, 0)             AS tokens_7d,
            COALESCE(s.tokens_3h, 0)             AS tokens_3h
        FROM users u
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*)                                                                  AS total_searches,
                COUNT(*) FILTER (WHERE sl.created_at >= now() - interval '7 days')        AS searches_7d,
                COUNT(*) FILTER (WHERE sl.created_at >= now() - interval '3 hours')       AS searches_3h,
                SUM(sl.tokens_prompt + sl.tokens_completion)                              AS total_tokens,
                SUM(sl.tokens_prompt + sl.tokens_completion) FILTER (WHERE sl.created_at >= now() - interval '7 days')  AS tokens_7d,
                SUM(sl.tokens_prompt + sl.tokens_completion) FILTER (WHERE sl.created_at >= now() - interval '3 hours') AS tokens_3h
            FROM search_logs sl
            WHERE sl.user_id = u.id
        ) s ON TRUE
        WHERE {where}
        ORDER BY u.created_at DESC
        LIMIT ${idx} OFFSET ${idx + 1}
    """, *params, page_size, offset)

    users = [
        {
            **_serialize_user_row(r),
            "total_searches": int(r["total_searches"]),
            "searches_7d": int(r["searches_7d"]),
            "searches_3h": int(r["searches_3h"]),
            "total_tokens": int(r["total_tokens"]),
            "tokens_7d": int(r["tokens_7d"]),
            "tokens_3h": int(r["tokens_3h"]),
        }
        for r in rows
    ]

    return {
        "users": users,
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


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


async def create_deck(user_id: str, name: str, format: str = "undefined") -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO decks (user_id, name, format) VALUES ($1::uuid, $2, $3) RETURNING id, name, format, created_at",
        user_id, name, format,
    )
    return _serialize_deck_row(row)


async def get_user_decks(user_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT d.id, d.name, d.format, d.created_at, d.updated_at,
                  d.analysis_data, d.analysis_updated_at,
                  COALESCE(SUM(dc.quantity), 0) AS card_count
           FROM decks d
           LEFT JOIN deck_cards dc ON dc.deck_id = d.id
           WHERE d.user_id = $1::uuid
           GROUP BY d.id
           ORDER BY d.updated_at DESC""",
        user_id,
    )
    return [_serialize_deck_summary_row(row) for row in rows]


async def get_deck(deck_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT id, user_id, name, format, created_at, updated_at,
                  analysis_data, analysis_updated_at
           FROM decks WHERE id = $1::uuid""",
        deck_id,
    )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "format": row["format"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "analysis": _serialize_analysis(row),
    }


async def update_deck(deck_id: str, name: str, format: str | None = None) -> dict:
    pool = await get_pool()
    if format is None:
        row = await pool.fetchrow(
            "UPDATE decks SET name = $1, updated_at = now() WHERE id = $2::uuid RETURNING id, name, format, updated_at",
            name, deck_id,
        )
    else:
        row = await pool.fetchrow(
            "UPDATE decks SET name = $1, format = $2, updated_at = now() WHERE id = $3::uuid RETURNING id, name, format, updated_at",
            name, format, deck_id,
        )
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "format": row["format"],
        "updated_at": row["updated_at"].isoformat(),
    }


async def delete_deck(deck_id: str):
    pool = await get_pool()
    await pool.execute("DELETE FROM decks WHERE id = $1::uuid", deck_id)


async def get_deck_cards(deck_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT dc.card_id, dc.quantity, dc.added_at, dc.image_url, dc.display_url, dc.board, c.data
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           WHERE dc.deck_id = $1::uuid
           ORDER BY dc.added_at DESC""",
        deck_id,
    )
    return [
        {
            "card_id": r["card_id"],
            "card": _decode_card_data(r["data"]),
            "quantity": r["quantity"],
            "image_url": r["image_url"],
            "display_url": r["display_url"],
            "board": r["board"],
            "added_at": r["added_at"].isoformat(),
        }
        for r in rows
    ]


async def add_card_to_deck(
    deck_id: str, card_id: str, quantity: int = 1,
    image_url: str | None = None, display_url: str | None = None,
    update_image: bool = False, board: str = "mainboard",
) -> dict:
    pool = await get_pool()
    if update_image:
        row = await pool.fetchrow(
            """INSERT INTO deck_cards (deck_id, card_id, quantity, image_url, display_url, board)
               VALUES ($1::uuid, $2, $3, $4, $5, $6)
               ON CONFLICT (deck_id, card_id, board)
               DO UPDATE SET quantity = deck_cards.quantity + EXCLUDED.quantity,
                             image_url = $4,
                             display_url = $5
               RETURNING card_id, quantity, board""",
            deck_id, card_id, quantity, image_url, display_url, board,
        )
    else:
        row = await pool.fetchrow(
            """INSERT INTO deck_cards (deck_id, card_id, quantity, image_url, display_url, board)
               VALUES ($1::uuid, $2, $3, $4, $5, $6)
               ON CONFLICT (deck_id, card_id, board)
               DO UPDATE SET quantity = deck_cards.quantity + EXCLUDED.quantity,
                             image_url = COALESCE(EXCLUDED.image_url, deck_cards.image_url),
                             display_url = COALESCE(EXCLUDED.display_url, deck_cards.display_url)
               RETURNING card_id, quantity, board""",
            deck_id, card_id, quantity, image_url, display_url, board,
        )
    return {"card_id": row["card_id"], "quantity": row["quantity"], "board": row["board"]}


async def remove_card_from_deck(deck_id: str, card_id: str, board: str | None = None):
    pool = await get_pool()
    if board:
        await pool.execute(
            "DELETE FROM deck_cards WHERE deck_id = $1::uuid AND card_id = $2 AND board = $3",
            deck_id, card_id, board,
        )
    else:
        await pool.execute(
            "DELETE FROM deck_cards WHERE deck_id = $1::uuid AND card_id = $2",
            deck_id, card_id,
        )


async def update_deck_card_image(
    deck_id: str,
    card_id: str,
    image_url: str | None,
    display_url: str | None,
    board: str | None = None,
) -> dict | None:
    """Update the image override for a deck card without touching quantity.

    Passing None for either url resets that override (card falls back to the default image).
    Returns the updated row or None if the card is not in the deck.
    """
    pool = await get_pool()
    if board:
        row = await pool.fetchrow(
            """UPDATE deck_cards
               SET image_url = $3, display_url = $4
               WHERE deck_id = $1::uuid AND card_id = $2 AND board = $5
               RETURNING card_id, quantity, image_url, display_url, board""",
            deck_id, card_id, image_url, display_url, board,
        )
    else:
        row = await pool.fetchrow(
            """UPDATE deck_cards
               SET image_url = $3, display_url = $4
               WHERE deck_id = $1::uuid AND card_id = $2
               RETURNING card_id, quantity, image_url, display_url, board""",
            deck_id, card_id, image_url, display_url,
        )
    if not row:
        return None
    return {
        "card_id": row["card_id"],
        "quantity": row["quantity"],
        "image_url": row["image_url"],
        "display_url": row["display_url"],
        "board": row["board"],
    }


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


async def get_cards_by_printing(
    keys: list[tuple[str, str, str]],
) -> dict[tuple[str, str, str], str]:
    """Look up card IDs by (name_lower, set_lower, collector_number).

    Returns {(name_lower, set_lower, collector): card_id} for matches.
    Also matches double-faced cards by front face name (before ' // ').
    """
    if not keys:
        return {}
    pool = await get_pool()
    names = [k[0] for k in keys]
    sets = [k[1] for k in keys]
    collectors = [k[2] for k in keys]
    rows = await pool.fetch(
        """SELECT c.id,
                  LOWER(c.name) AS name_l,
                  LOWER(split_part(c.name, ' // ', 1)) AS front_l,
                  LOWER(c.data->>'set') AS set_l,
                  c.data->>'collector_number' AS col
           FROM cards c
           JOIN unnest($1::text[], $2::text[], $3::text[]) AS k(name_l, set_l, col)
             ON (LOWER(c.name) = k.name_l
                 OR LOWER(split_part(c.name, ' // ', 1)) = k.name_l)
            AND LOWER(c.data->>'set') = k.set_l
            AND c.data->>'collector_number' = k.col""",
        names, sets, collectors,
    )
    result: dict[tuple[str, str, str], str] = {}
    for row in rows:
        key_full = (row["name_l"], row["set_l"], row["col"])
        key_front = (row["front_l"], row["set_l"], row["col"])
        if key_full not in result:
            result[key_full] = row["id"]
        if key_front not in result:
            result[key_front] = row["id"]
    return result


async def get_deck_cards_for_analysis(deck_id: str) -> list[dict]:
    """Fetch cards for Deepseek analysis: front-face name, type, mana cost, oracle text.

    Returns rows ordered by board so the payload can be formatted with a
    MAINBOARD block followed by an optional SIDEBOARD block.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT split_part(c.name, ' // ', 1)               AS name,
                  COALESCE(c.data->>'type_line', '')          AS type_line,
                  COALESCE(c.data->>'mana_cost', '')          AS mana_cost,
                  COALESCE(c.data->>'oracle_text', '')        AS oracle_text,
                  dc.quantity,
                  dc.board
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           WHERE dc.deck_id = $1::uuid
           ORDER BY dc.board, name""",
        deck_id,
    )
    return [dict(r) for r in rows]


async def update_deck_analysis(deck_id: str, analysis: dict) -> dict:
    """Persist the bilingual analysis blob ({zh: {...}, en: {...}})."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """UPDATE decks
              SET analysis_data       = $1::jsonb,
                  analysis_updated_at = now()
           WHERE id = $2::uuid
           RETURNING analysis_data, analysis_updated_at""",
        json.dumps(analysis), deck_id,
    )
    raw = row["analysis_data"]
    data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    return {
        "zh": data.get("zh"),
        "en": data.get("en"),
        "updated_at": row["analysis_updated_at"].isoformat(),
    }


async def get_deck_cards_for_export(deck_id: str) -> list[dict]:
    """Get card names, quantities, and board for text export.

    Uses only the front face name for double-faced cards.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT split_part(c.name, ' // ', 1) AS name, dc.quantity, dc.board
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           WHERE dc.deck_id = $1::uuid
           ORDER BY dc.board, name""",
        deck_id,
    )
    return [{"name": r["name"], "quantity": r["quantity"], "board": r["board"]} for r in rows]

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

    # ── Total count (deduplicated by name) ──
    total = await pool.fetchval(
        f"SELECT COUNT(*) FROM (SELECT DISTINCT ON (name) id FROM cards WHERE {where} ORDER BY name, data->>'released_at' DESC) sub",
        *params,
    )

    # ── Paginated results (deduplicated by name, newest printing) ──
    offset = (page - 1) * page_size
    limit_idx = idx
    offset_idx = idx + 1
    rows = await pool.fetch(
        f"""SELECT data FROM (
              SELECT DISTINCT ON (name) data
              FROM cards WHERE {where}
              ORDER BY name, data->>'released_at' DESC
            ) sub
            ORDER BY sub.data->>'name'
            LIMIT ${limit_idx} OFFSET ${offset_idx}""",
        *params, page_size, offset,
    )
    cards = [_decode_card_data(row["data"]) for row in rows]

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


# ── Search log functions ───────────────────────────────────────────────


async def log_search(user_id: str | None, query: str, tokens_prompt: int, tokens_completion: int,
                     ip_address: str | None = None):
    """Log a search request with optional user and token usage."""
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO search_logs (user_id, query, tokens_prompt, tokens_completion, ip_address) VALUES ($1::uuid, $2, $3, $4, $5)",
        user_id, query, tokens_prompt, tokens_completion, ip_address,
    )


async def get_user_search_stats() -> list[dict]:
    """Get per-user search counts and token usage for total, 7 days, and 3 hours."""
    pool = await get_pool()
    rows = await pool.fetch("""
        SELECT
            u.id,
            u.username,
            u.role,
            u.email,
            u.email_verified,
            u.created_at,
            u.last_active_at,
            COALESCE(s.total_searches, 0)       AS total_searches,
            COALESCE(s.searches_7d, 0)           AS searches_7d,
            COALESCE(s.searches_3h, 0)           AS searches_3h,
            COALESCE(s.total_tokens, 0)          AS total_tokens,
            COALESCE(s.tokens_7d, 0)             AS tokens_7d,
            COALESCE(s.tokens_3h, 0)             AS tokens_3h
        FROM users u
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*)                                                                  AS total_searches,
                COUNT(*) FILTER (WHERE sl.created_at >= now() - interval '7 days')        AS searches_7d,
                COUNT(*) FILTER (WHERE sl.created_at >= now() - interval '3 hours')       AS searches_3h,
                SUM(sl.tokens_prompt + sl.tokens_completion)                              AS total_tokens,
                SUM(sl.tokens_prompt + sl.tokens_completion) FILTER (WHERE sl.created_at >= now() - interval '7 days')  AS tokens_7d,
                SUM(sl.tokens_prompt + sl.tokens_completion) FILTER (WHERE sl.created_at >= now() - interval '3 hours') AS tokens_3h
            FROM search_logs sl
            WHERE sl.user_id = u.id
        ) s ON TRUE
        ORDER BY u.created_at
    """)
    return [
        {
            **_serialize_user_row(r),
            "total_searches": int(r["total_searches"]),
            "searches_7d": int(r["searches_7d"]),
            "searches_3h": int(r["searches_3h"]),
            "total_tokens": int(r["total_tokens"]),
            "tokens_7d": int(r["tokens_7d"]),
            "tokens_3h": int(r["tokens_3h"]),
        }
        for r in rows
    ]


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
