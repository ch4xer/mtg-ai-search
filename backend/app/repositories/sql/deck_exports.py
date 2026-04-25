import json

from .connection import get_pool

DOUBLE_FACED_LAYOUTS = frozenset({"transform", "modal_dfc", "double_faced_token", "reversible_card"})

DECK_FRONTEND_ORDER_SQL = """
           ORDER BY
                  CASE WHEN dc.board = 'sideboard' THEN 1 ELSE 0 END,
                  CASE
                    WHEN POSITION('Planeswalker' IN COALESCE(c.type_line, '')) > 0 THEN 0
                    WHEN POSITION('Creature' IN COALESCE(c.type_line, '')) > 0 THEN 1
                    WHEN POSITION('Sorcery' IN COALESCE(c.type_line, '')) > 0 THEN 2
                    WHEN POSITION('Instant' IN COALESCE(c.type_line, '')) > 0 THEN 3
                    WHEN POSITION('Artifact' IN COALESCE(c.type_line, '')) > 0 THEN 4
                    WHEN POSITION('Enchantment' IN COALESCE(c.type_line, '')) > 0 THEN 5
                    WHEN POSITION('Land' IN COALESCE(c.type_line, '')) > 0 THEN 6
                    ELSE 7
                  END,
                  (COALESCE(c.mana_cost, '') ~* '\\{[XYZ]\\}') ASC,
                  CASE
                    WHEN COALESCE(c.mana_cost, '') ~* '\\{[XYZ]\\}' THEN 0
                    ELSE COALESCE(c.cmc, 0)
                  END,
                  CASE
                    WHEN COALESCE(cardinality(c.color_identity), 0) = 0 THEN 100
                    WHEN cardinality(c.color_identity) = 1 THEN
                      CASE c.color_identity[1]
                        WHEN 'W' THEN 0
                        WHEN 'U' THEN 1
                        WHEN 'B' THEN 2
                        WHEN 'R' THEN 3
                        WHEN 'G' THEN 4
                        ELSE 50
                      END
                    ELSE 50 + COALESCE((
                      SELECT MIN(CASE color_symbol
                        WHEN 'W' THEN 0
                        WHEN 'U' THEN 1
                        WHEN 'B' THEN 2
                        WHEN 'R' THEN 3
                        WHEN 'G' THEN 4
                        ELSE 50
                      END)
                      FROM unnest(c.color_identity) AS colors(color_symbol)
                    ), 50)
                  END,
                  c.name,
                  dc.added_at DESC
"""


async def get_deck_cards_for_export(deck_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        f"""SELECT split_part(c.name, ' // ', 1) AS name, dc.quantity, dc.board
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           WHERE dc.deck_id = $1::uuid
           {DECK_FRONTEND_ORDER_SQL}""",
        deck_id,
    )
    return [{"name": r["name"], "quantity": r["quantity"], "board": r["board"]} for r in rows]


async def get_deck_card_images(deck_id: str) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        f"""SELECT dc.quantity, c.name,
                  c.layout,
                  CASE
                    WHEN dc.print_id IS NOT NULL THEN COALESCE(
                        cp.image_png,
                        cp.image_normal,
                        cp.image_large,
                        dc.image_url
                    )
                    ELSE COALESCE(
                        dp.image_png,
                        dp.image_normal,
                        dp.image_large,
                        dc.image_url
                    )
                  END AS png_url,
                  COALESCE(cp.card_faces, dp.card_faces, c.card_faces) AS card_faces
           FROM deck_cards dc
           JOIN cards c ON c.id = dc.card_id
           LEFT JOIN card_prints cp ON cp.id = dc.print_id
           LEFT JOIN LATERAL (
               SELECT image_normal, image_large, image_png, card_faces
               FROM card_prints
               WHERE card_id = dc.card_id
               ORDER BY released_at DESC NULLS LAST
               LIMIT 1
           ) dp ON dc.print_id IS NULL
           WHERE dc.deck_id = $1::uuid
           {DECK_FRONTEND_ORDER_SQL}""",
        deck_id,
    )
    return [_serialize_deck_card_image_row(r) for r in rows]


def _decode_faces(raw_value) -> list[dict]:
    if not raw_value:
        return []
    return json.loads(raw_value) if isinstance(raw_value, str) else raw_value


def _pick_face_image(face: dict) -> str | None:
    image_uris = face.get("image_uris") or {}
    return (
        image_uris.get("png")
        or image_uris.get("normal")
        or image_uris.get("large")
        or image_uris.get("small")
    )


def _serialize_deck_card_image_row(row) -> dict:
    card = dict(row)
    faces = _decode_faces(card.get("card_faces"))
    front_face = faces[0] if faces else None
    back_face = faces[1] if len(faces) >= 2 and card.get("layout") in DOUBLE_FACED_LAYOUTS else None
    front_name = (front_face or {}).get("name") or card["name"].split(" // ", 1)[0]
    front_url = card.get("png_url") or _pick_face_image(front_face or {})

    return {
        "quantity": card["quantity"],
        "name": front_name,
        "png_url": front_url,
        "back_name": (back_face or {}).get("name"),
        "back_png_url": _pick_face_image(back_face or {}),
    }
