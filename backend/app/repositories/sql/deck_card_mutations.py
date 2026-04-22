from .connection import get_pool


async def add_card_to_deck(
    deck_id: str,
    card_id: str,
    quantity: int = 1,
    image_url: str | None = None,
    display_url: str | None = None,
    update_image: bool = False,
    board: str = "mainboard",
    print_id: str | None = None,
) -> dict:
    pool = await get_pool()
    if update_image:
        row = await pool.fetchrow(
            """INSERT INTO deck_cards (deck_id, card_id, quantity, image_url, display_url, board, print_id)
               VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
               ON CONFLICT (deck_id, card_id, board)
               DO UPDATE SET quantity = deck_cards.quantity + EXCLUDED.quantity,
                             image_url = $4,
                             display_url = $5,
                             print_id = COALESCE($7, deck_cards.print_id)
               RETURNING card_id, quantity, board""",
            deck_id,
            card_id,
            quantity,
            image_url,
            display_url,
            board,
            print_id,
        )
    else:
        row = await pool.fetchrow(
            """INSERT INTO deck_cards (deck_id, card_id, quantity, image_url, display_url, board, print_id)
               VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
               ON CONFLICT (deck_id, card_id, board)
               DO UPDATE SET quantity = deck_cards.quantity + EXCLUDED.quantity,
                             image_url = COALESCE(EXCLUDED.image_url, deck_cards.image_url),
                             display_url = COALESCE(EXCLUDED.display_url, deck_cards.display_url),
                             print_id = COALESCE($7, deck_cards.print_id)
               RETURNING card_id, quantity, board""",
            deck_id,
            card_id,
            quantity,
            image_url,
            display_url,
            board,
            print_id,
        )
    return {"card_id": row["card_id"], "quantity": row["quantity"], "board": row["board"]}


async def remove_card_from_deck(deck_id: str, card_id: str, board: str | None = None):
    pool = await get_pool()
    if board:
        await pool.execute(
            "DELETE FROM deck_cards WHERE deck_id = $1::uuid AND card_id = $2 AND board = $3",
            deck_id,
            card_id,
            board,
        )
    else:
        await pool.execute(
            "DELETE FROM deck_cards WHERE deck_id = $1::uuid AND card_id = $2",
            deck_id,
            card_id,
        )


async def update_deck_card_image(
    deck_id: str,
    card_id: str,
    image_url: str | None,
    display_url: str | None,
    board: str | None = None,
    print_id: str | None = None,
) -> dict | None:
    pool = await get_pool()
    if board:
        row = await pool.fetchrow(
            """UPDATE deck_cards
               SET image_url = $3, display_url = $4, print_id = $6
               WHERE deck_id = $1::uuid AND card_id = $2 AND board = $5
               RETURNING card_id, quantity, image_url, display_url, board, print_id""",
            deck_id,
            card_id,
            image_url,
            display_url,
            board,
            print_id,
        )
    else:
        row = await pool.fetchrow(
            """UPDATE deck_cards
               SET image_url = $3, display_url = $4, print_id = $5
               WHERE deck_id = $1::uuid AND card_id = $2
               RETURNING card_id, quantity, image_url, display_url, board, print_id""",
            deck_id,
            card_id,
            image_url,
            display_url,
            print_id,
        )
    if not row:
        return None
    return {
        "card_id": row["card_id"],
        "quantity": row["quantity"],
        "image_url": row["image_url"],
        "display_url": row["display_url"],
        "print_id": row["print_id"],
        "board": row["board"],
    }
