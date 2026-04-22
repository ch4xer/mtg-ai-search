import json

from .connection import get_pool
from .helpers import _card_faces_from_row, _image_uris_from_row


async def get_deck_cards(deck_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT dc.card_id, dc.print_id, dc.quantity, dc.added_at, dc.image_url, dc.display_url, dc.board,
                  c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text,
                  c.power, c.toughness, c.colors, c.color_identity, c.keywords,
                  c.legalities, c.layout, c.card_faces,
                  COALESCE(cp.rarity, dp.rarity) AS rarity,
                  COALESCE(cp.image_small, dp.image_small) AS image_small,
                  COALESCE(cp.image_normal, dp.image_normal) AS image_normal,
                  COALESCE(cp.image_large, dp.image_large) AS image_large,
                  COALESCE(cp.image_png, dp.image_png) AS image_png,
                  COALESCE(cp.image_art_crop, dp.image_art_crop) AS image_art_crop,
                  COALESCE(cp.image_border_crop, dp.image_border_crop) AS image_border_crop,
                  COALESCE(cp.card_faces, dp.card_faces) AS print_card_faces
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           LEFT JOIN card_prints cp ON cp.id = dc.print_id
           LEFT JOIN LATERAL (
               SELECT rarity, image_small, image_normal, image_large, image_png, image_art_crop, image_border_crop, card_faces
               FROM card_prints
               WHERE card_id = dc.card_id
               ORDER BY released_at DESC NULLS LAST
               LIMIT 1
           ) dp ON dc.print_id IS NULL
           WHERE dc.deck_id = $1::uuid
           ORDER BY dc.added_at DESC""",
        deck_id,
    )
    return [_serialize_deck_card_row(r) for r in rows]


def _serialize_deck_card_row(row) -> dict:
    legalities = row["legalities"]
    return {
        "card_id": row["card_id"],
        "print_id": row["print_id"],
        "card": {
            "id": row["card_id"],
            "name": row["name"],
            "mana_cost": row["mana_cost"],
            "cmc": row["cmc"],
            "type_line": row["type_line"],
            "oracle_text": row["oracle_text"],
            "power": row["power"],
            "toughness": row["toughness"],
            "colors": row["colors"] or [],
            "color_identity": row["color_identity"] or [],
            "keywords": row["keywords"] or [],
            "legalities": json.loads(legalities) if isinstance(legalities, str) else legalities,
            "layout": row["layout"],
            "rarity": row["rarity"],
            "card_faces": _card_faces_from_row(row),
            "image_uris": _image_uris_from_row(row),
        },
        "quantity": row["quantity"],
        "image_url": row["image_url"],
        "display_url": row["display_url"],
        "board": row["board"],
        "added_at": row["added_at"].isoformat(),
    }
