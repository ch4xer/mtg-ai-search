from .connection import get_pool
from .helpers import _decode_card_data

async def get_card_print_by_set_cn(card_id: str, set_code: str, collector_num: str) -> dict | None:
    """Query a specific print by set code and collector number."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT id, card_id, set_code, set_name, collector_num, rarity, artist,
                  flavor_name, released_at, finishes,
                  image_small, image_normal, image_large, image_png,
                  image_art_crop, image_border_crop, card_faces,
                  image_set_code, image_set_name, image_collector_number
           FROM card_prints
           WHERE card_id = $1 AND set_code = $2 AND collector_num = $3""",
        card_id, set_code.lower(), collector_num,
    )
    if not row:
        return None
    return {
        "id": row["id"],
        "card_id": row["card_id"],
        "set_code": row["set_code"],
        "set_name": row["set_name"],
        "collector_num": row["collector_num"],
        "image_set_code": row["image_set_code"],
        "image_set_name": row["image_set_name"],
        "image_collector_number": row["image_collector_number"],
        "rarity": row["rarity"],
        "artist": row["artist"],
        "flavor_name": row["flavor_name"],
        "released_at": row["released_at"].isoformat() if row["released_at"] else None,
        "finishes": row["finishes"] or [],
        "image_small": row["image_small"],
        "image_normal": row["image_normal"],
        "image_large": row["image_large"],
        "image_png": row["image_png"],
        "image_art_crop": row["image_art_crop"],
        "image_border_crop": row["image_border_crop"],
        "card_faces": _decode_card_data(row["card_faces"]) if row["card_faces"] else None,
    }

async def get_card_prints_by_oracle_id(oracle_id: str) -> list[dict]:
    """Get all prints for a card by oracle_id."""
    pool = await get_pool()
    rows = await pool.fetch(
        """SELECT id, card_id, set_code, set_name, collector_num, rarity, artist,
                  flavor_name, released_at, finishes,
                  image_small, image_normal, image_large, image_png,
                  image_art_crop, image_border_crop, card_faces,
                  image_set_code, image_set_name, image_collector_number
           FROM card_prints
           WHERE card_id = $1
           ORDER BY released_at DESC""",
        oracle_id,
    )
    return [
        {
            "id": r["id"],
            "card_id": r["card_id"],
            "set_code": r["set_code"],
            "set_name": r["set_name"],
            "collector_num": r["collector_num"],
            "image_set_code": r["image_set_code"],
            "image_set_name": r["image_set_name"],
            "image_collector_number": r["image_collector_number"],
            "rarity": r["rarity"],
            "artist": r["artist"],
            "flavor_name": r["flavor_name"],
            "released_at": r["released_at"].isoformat() if r["released_at"] else None,
            "finishes": r["finishes"] or [],
            "image_small": r["image_small"],
            "image_normal": r["image_normal"],
            "image_large": r["image_large"],
            "image_png": r["image_png"],
            "image_art_crop": r["image_art_crop"],
            "image_border_crop": r["image_border_crop"],
            "card_faces": _decode_card_data(r["card_faces"]) if r["card_faces"] else None,
        }
        for r in rows
    ]

