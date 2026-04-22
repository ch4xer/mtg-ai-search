import json

from .connection import get_pool
from .helpers import _decode_card_data

async def get_cards_by_oracle_ids(oracle_ids: list[str]) -> dict[str, str]:
    """Look up multiple cards by oracle_ids. Returns {oracle_id: card_id}."""
    if not oracle_ids:
        return {}
    pool = await get_pool()
    rows = await pool.fetch("SELECT id FROM cards WHERE id = ANY($1)", oracle_ids)
    return {row["id"]: row["id"] for row in rows}

async def get_cards_by_names(names: list[str]) -> dict[str, str]:
    """Look up card IDs by exact name (case-insensitive). Returns {name_lower: card_id}.

    Also matches double-faced cards by front face name (before ' // ').
    Also matches flavor_name from card_prints table.
    """
    if not names:
        return {}
    pool = await get_pool()
    lowered = [n.lower() for n in names]

    # Query cards table for name matches
    rows = await pool.fetch(
        """SELECT id, name FROM cards
           WHERE LOWER(name) = ANY($1)
              OR LOWER(split_part(name, ' // ', 1)) = ANY($1)""",
        lowered,
    )
    result: dict[str, str] = {}
    for row in rows:
        full = row["name"].lower()
        front = full.split(" // ")[0]
        if full not in result:
            result[full] = row["id"]
        if front not in result:
            result[front] = row["id"]

    # Query card_prints for flavor_name matches
    flavor_rows = await pool.fetch(
        """SELECT DISTINCT card_id, flavor_name FROM card_prints
           WHERE flavor_name IS NOT NULL
             AND LOWER(flavor_name) = ANY($1)""",
        lowered,
    )
    for row in flavor_rows:
        flavor = row["flavor_name"].lower()
        if flavor not in result:
            result[flavor] = row["card_id"]

    return result

async def get_card_by_oracle_id(oracle_id: str) -> dict | None:
    """Get full card data by oracle_id."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """SELECT id, name, mana_cost, cmc, type_line, oracle_text,
                  power, toughness, colors, color_identity, keywords,
                  legalities, layout, card_faces
           FROM cards WHERE id = $1""",
        oracle_id,
    )
    if not row:
        return None
    return {
        "id": row["id"],
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
        "legalities": json.loads(row["legalities"]) if isinstance(row["legalities"], str) else row["legalities"],
        "layout": row["layout"],
        "card_faces": _decode_card_data(row["card_faces"]) if row["card_faces"] else None,
    }

