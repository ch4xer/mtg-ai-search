from .connection import get_pool


async def get_deck_cards_for_export(deck_id: str) -> list[dict]:
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


async def get_deck_card_images(deck_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT dc.quantity, c.name,
                  COALESCE(dc.image_url,
                           cp.image_png,
                           cp.image_large) AS png_url
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           LEFT JOIN card_prints cp ON cp.id = dc.print_id
           WHERE dc.deck_id = $1::uuid
           ORDER BY dc.added_at""",
        deck_id,
    )
    return [dict(r) for r in rows]
