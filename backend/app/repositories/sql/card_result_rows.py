import json

from .connection import get_pool
from .helpers import _card_faces_from_row, _image_uris_from_row

CARD_RESULT_COLUMNS = """c.id, c.name, c.mana_cost, c.cmc, c.type_line, c.oracle_text,
                  c.power, c.toughness, c.colors, c.color_identity, c.keywords,
                  c.legalities, c.layout, c.card_faces,
                  dp.id AS print_id, dp.image_small, dp.image_normal, dp.image_large, dp.image_png,
                  dp.image_art_crop, dp.image_border_crop, dp.rarity, dp.set_code, dp.set_name,
                  dp.flavor_text, dp.artist, dp.card_faces AS print_card_faces,
                  zt.name AS zh_name, zt.type_line AS zh_type_line,
                  zt.oracle_text AS zh_oracle_text, zt.flavor_text AS zh_flavor_text,
                  zt.set_name AS zh_set_name, zt.card_faces AS zh_card_faces"""

DEFAULT_PRINT_JOIN = """LEFT JOIN LATERAL (
               SELECT id, image_small, image_normal, image_large, image_png,
                      image_art_crop, image_border_crop, rarity, set_code, set_name,
                      flavor_text, artist, card_faces
               FROM card_prints
               WHERE card_id = c.id
               ORDER BY released_at DESC NULLS LAST
               LIMIT 1
           ) dp ON TRUE
           LEFT JOIN LATERAL (
               SELECT name, type_line, oracle_text, flavor_text, set_name, card_faces
               FROM card_print_translations
               WHERE card_id = c.id
                 AND lang = 'zhs'
                 AND status = 'ok'
               ORDER BY synced_at DESC
               LIMIT 1
           ) zt ON TRUE"""

MATCHED_PRINT_JOIN = """JOIN card_prints dp ON dp.id = sub.matched_print_id
           LEFT JOIN card_print_translations zt
             ON zt.print_id = dp.id
            AND zt.lang = 'zhs'
            AND zt.status = 'ok'"""


async def get_cards_by_ids(card_ids: list[str]) -> list[dict]:
    if not card_ids:
        return []

    pool = await get_pool()
    rows = await pool.fetch(
        f"""SELECT {CARD_RESULT_COLUMNS}
           FROM cards c
           {DEFAULT_PRINT_JOIN}
           WHERE c.id = ANY($1)""",
        card_ids,
    )

    card_map = {row["id"]: serialize_card_result(row) for row in rows}
    return [card_map[cid] for cid in card_ids if cid in card_map]


def serialize_card_result(row) -> dict:
    legalities = row["legalities"]
    card = {
        "id": row["id"],
        "print_id": row["print_id"],
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
        "card_faces": _card_faces_from_row(row),
        "image_uris": _image_uris_from_row(row),
        "rarity": row["rarity"],
        "set": row["set_code"],
        "set_name": row["set_name"],
        "flavor_text": row["flavor_text"],
        "artist": row["artist"],
    }
    zh = _translation_from_row(row)
    if zh:
        card["zh"] = zh
    return card


def _translation_from_row(row) -> dict | None:
    if "zh_name" not in row.keys():
        return None
    if not any(row[key] for key in ("zh_name", "zh_type_line", "zh_oracle_text", "zh_flavor_text")):
        return None

    card_faces = _decode_json_field(row["zh_card_faces"])
    return {
        "source": "mtgch",
        "name": row["zh_name"],
        "type_line": row["zh_type_line"],
        "oracle_text": row["zh_oracle_text"],
        "flavor_text": row["zh_flavor_text"],
        "set_name": row["zh_set_name"],
        "card_faces": card_faces or [],
    }


def _decode_json_field(value):
    if isinstance(value, str):
        return json.loads(value)
    return value
