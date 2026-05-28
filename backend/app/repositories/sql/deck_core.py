from .connection import get_pool
from .helpers import _serialize_analysis, _serialize_deck_row, _serialize_deck_summary_row


_DEFAULT_COVER_LATERAL_SQL = """
LEFT JOIN LATERAL (
    SELECT COALESCE(dc_cover.display_url, cp.image_art_crop, dp.image_art_crop) AS cover_image_url
    FROM deck_cards dc_cover
    JOIN cards c_cover ON c_cover.id = dc_cover.card_id
    LEFT JOIN card_prints cp ON cp.id = dc_cover.print_id
    LEFT JOIN LATERAL (
        SELECT image_art_crop
        FROM card_prints
        WHERE card_id = dc_cover.card_id
        ORDER BY released_at DESC NULLS LAST
        LIMIT 1
    ) dp ON dc_cover.print_id IS NULL
    WHERE dc_cover.deck_id = d.id
      AND dc_cover.board = 'mainboard'
      AND c_cover.type_line ILIKE '%Creature%'
      AND COALESCE(dc_cover.display_url, cp.image_art_crop, dp.image_art_crop) IS NOT NULL
    ORDER BY COALESCE(c_cover.cmc, -1) DESC, c_cover.name ASC, dc_cover.added_at ASC
    LIMIT 1
) default_cover ON TRUE
"""


async def create_deck(user_id: str, name: str, format: str = "undefined") -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO decks (user_id, name, format) VALUES ($1::uuid, $2, $3) RETURNING id, name, format, cover_image_url, created_at",
        user_id, name, format,
    )
    return _serialize_deck_row(row)


async def get_user_decks(user_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        f"""SELECT d.id, d.name, d.format, d.created_at, d.updated_at,
                  COALESCE(d.cover_image_url, default_cover.cover_image_url) AS cover_image_url,
                  d.analysis_data, d.analysis_updated_at,
                  COALESCE(SUM(dc.quantity), 0) AS card_count,
                  COALESCE(SUM(dc.quantity) FILTER (WHERE dc.board = 'mainboard'), 0) AS mainboard_card_count,
                  ARRAY(
                    SELECT color_order.color_symbol
                    FROM unnest(ARRAY['W','U','B','R','G']::text[]) AS color_order(color_symbol)
                    WHERE EXISTS (
                      SELECT 1
                      FROM deck_cards dc_color
                      JOIN cards c_color ON c_color.id = dc_color.card_id
                      WHERE dc_color.deck_id = d.id
                        AND dc_color.board = 'mainboard'
                        AND color_order.color_symbol = ANY(
                          COALESCE(c_color.color_identity, c_color.colors, ARRAY[]::text[])
                        )
                    )
                  ) AS colors
           FROM decks d
           {_DEFAULT_COVER_LATERAL_SQL}
           LEFT JOIN deck_cards dc ON dc.deck_id = d.id
           WHERE d.user_id = $1::uuid
           GROUP BY d.id, default_cover.cover_image_url
           ORDER BY d.updated_at DESC""",
        user_id,
    )
    return [_serialize_deck_summary_row(row) for row in rows]


async def get_deck(deck_id: str) -> dict | None:
    pool = await get_pool()
    row = await pool.fetchrow(
        f"""SELECT d.id, d.user_id, d.name, d.format,
                  COALESCE(d.cover_image_url, default_cover.cover_image_url) AS cover_image_url,
                  d.created_at, d.updated_at,
                  d.analysis_data, d.analysis_updated_at
           FROM decks d
           {_DEFAULT_COVER_LATERAL_SQL}
           WHERE d.id = $1::uuid""",
        deck_id,
    )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "format": row["format"],
        "cover_image_url": row["cover_image_url"],
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


async def update_deck_cover(deck_id: str, cover_image_url: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """UPDATE decks
           SET cover_image_url = $1, updated_at = now()
           WHERE id = $2::uuid
           RETURNING id, cover_image_url, updated_at""",
        cover_image_url,
        deck_id,
    )
    return {
        "id": str(row["id"]),
        "cover_image_url": row["cover_image_url"],
        "updated_at": row["updated_at"].isoformat(),
    }


async def delete_deck(deck_id: str):
    pool = await get_pool()
    await pool.execute("DELETE FROM decks WHERE id = $1::uuid", deck_id)
