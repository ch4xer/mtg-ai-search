"""Deterministic random-card and function-tag metadata queries."""

from .card_result_rows import get_cards_by_ids
from .connection import get_pool


async def get_random_playable_card(exclude_card_id: str | None = None) -> dict | None:
    """Return one official, non-playtest oracle card."""
    pool = await get_pool()
    card_id = await pool.fetchval(
        """SELECT id
           FROM cards
           WHERE NOT COALESCE(is_unofficial, FALSE)
             AND NOT COALESCE(is_playtest, FALSE)
             AND ($1::text IS NULL OR id <> $1)
           ORDER BY random()
           LIMIT 1""",
        exclude_card_id,
    )
    if card_id is None and exclude_card_id:
        card_id = await pool.fetchval(
            """SELECT id
               FROM cards
               WHERE NOT COALESCE(is_unofficial, FALSE)
                 AND NOT COALESCE(is_playtest, FALSE)
               ORDER BY random()
               LIMIT 1"""
        )
    cards = await get_cards_by_ids([card_id]) if card_id else []
    return cards[0] if cards else None


async def get_card_function_tags(card_id: str) -> dict | None:
    """Return a card identity and all of its currently active function tags."""
    pool = await get_pool()
    card = await pool.fetchrow("SELECT id, name FROM cards WHERE id = $1", card_id)
    if card is None:
        return None

    rows = await pool.fetch(
        """SELECT ctt.tag, tt.label
           FROM card_tagger_tags ctt
           JOIN tagger_tags tt
             ON tt.tag_type = ctt.tag_type
            AND tt.tag = ctt.tag
           WHERE ctt.card_id = $1
             AND ctt.tag_type = 'function'
             AND tt.removed_at IS NULL
           ORDER BY ctt.tag""",
        card_id,
    )
    return {
        "card_id": card["id"],
        "card_name": card["name"],
        "tags": [{"tag": row["tag"], "label": row["label"]} for row in rows],
    }
