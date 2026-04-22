from .connection import get_pool
from .helpers import _serialize_analysis, _serialize_deck_row, _serialize_deck_summary_row


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
            name,
            deck_id,
        )
    else:
        row = await pool.fetchrow(
            "UPDATE decks SET name = $1, format = $2, updated_at = now() WHERE id = $3::uuid RETURNING id, name, format, updated_at",
            name,
            format,
            deck_id,
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
