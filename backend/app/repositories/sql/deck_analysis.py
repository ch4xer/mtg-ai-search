import json

from .connection import get_pool


async def get_deck_cards_for_analysis(deck_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT split_part(c.name, ' // ', 1) AS name,
                  COALESCE(c.type_line, '') AS type_line,
                  COALESCE(c.mana_cost, '') AS mana_cost,
                  COALESCE(c.oracle_text, '') AS oracle_text,
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
    pool = await get_pool()
    row = await pool.fetchrow(
        """UPDATE decks
              SET analysis_data       = $1::jsonb,
                  analysis_updated_at = now()
           WHERE id = $2::uuid
           RETURNING analysis_data, analysis_updated_at""",
        json.dumps(analysis),
        deck_id,
    )
    raw = row["analysis_data"]
    data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    return {
        "zh": data.get("zh"),
        "en": data.get("en"),
        "updated_at": row["analysis_updated_at"].isoformat(),
    }
