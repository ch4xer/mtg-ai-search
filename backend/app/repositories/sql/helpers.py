import json
import re

_MAIN_TYPES = [
    "Creature",
    "Instant",
    "Sorcery",
    "Enchantment",
    "Artifact",
    "Land",
    "Planeswalker",
    "Battle",
]

# Operators allowed in condition expressions like ">5", ">=2020-01-01"
_CONDITION_RE = re.compile(r"^(>=|<=|>|<|=)\s*(.+)$")

def _parse_condition(expr: str) -> tuple[str, str]:
    """Parse a condition expression like '>5' into (operator, value)."""
    m = _CONDITION_RE.match(expr.strip())
    if not m:
        return ("=", expr.strip())
    return (m.group(1), m.group(2).strip())

def _decode_card_data(value):
    return json.loads(value) if isinstance(value, str) else value

def _image_uris_from_row(row) -> dict | None:
    if not row["image_normal"]:
        return None
    return {
        "small": row["image_small"],
        "normal": row["image_normal"],
        "large": row["image_large"],
        "png": row["image_png"],
        "art_crop": row["image_art_crop"],
        "border_crop": row["image_border_crop"],
    }

def _card_faces_from_row(row) -> list[dict] | None:
    if "print_card_faces" in row.keys() and row["print_card_faces"]:
        return _decode_card_data(row["print_card_faces"])
    if "card_faces" in row.keys() and row["card_faces"]:
        return _decode_card_data(row["card_faces"])
    return None

def _serialize_user_row(row) -> dict:
    return {
        "id": str(row["id"]),
        "username": row["username"],
        "role": row["role"],
        "email": row["email"],
        "email_verified": row["email_verified"],
        "last_active_at": row["last_active_at"].isoformat() if row["last_active_at"] else None,
        "created_at": row["created_at"].isoformat(),
    }

def _serialize_deck_row(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "format": row["format"],
        "cover_image_url": row["cover_image_url"] if "cover_image_url" in row.keys() else None,
        "created_at": row["created_at"].isoformat(),
    }

def _serialize_analysis(row) -> dict | None:
    # Nested {"zh": {...}, "en": {...}, "updated_at": "..."} or null.
    if not row["analysis_updated_at"] or not row["analysis_data"]:
        return None
    raw = row["analysis_data"]
    data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    return {
        "zh": data.get("zh"),
        "en": data.get("en"),
        "updated_at": row["analysis_updated_at"].isoformat(),
    }

def _serialize_deck_summary_row(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "format": row["format"],
        "card_count": int(row["card_count"]),
        "mainboard_card_count": int(row["mainboard_card_count"]),
        "colors": row["colors"] or [],
        "cover_image_url": row["cover_image_url"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
        "analysis": _serialize_analysis(row),
    }
