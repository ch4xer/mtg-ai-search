import re
import requests


def parse_keyword_abilities(filepath: str) -> dict[str, str]:
    """Parse keyword_ability.txt into {name: description} dict."""
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    text = text.replace("\u2019", "'")
    result = {}
    current_name = None
    current_lines = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        header_match = re.match(r"702\.(\d+)\.\s+(.+)", line)
        if header_match:
            # Skip 702.1 which is just an introduction paragraph, not a keyword ability
            if header_match.group(1) == "1":
                current_name = None
                current_lines = []
                continue
            if current_name:
                result[current_name] = " ".join(current_lines)
            current_name = header_match.group(2).strip()
            current_lines = []
            continue

        sub_match = re.match(r"702\.\d+[a-z]\s+(.+)", line)
        if sub_match and current_name:
            current_lines.append(sub_match.group(1).strip())

    if current_name:
        result[current_name] = " ".join(current_lines)

    return result


def download_scryfall_cards() -> list[dict]:
    """Download oracle cards from Scryfall bulk data API."""
    bulk_url = "https://api.scryfall.com/bulk-data"
    resp = requests.get(bulk_url)
    resp.raise_for_status()
    bulk_data = resp.json()

    oracle_entry = None
    for entry in bulk_data["data"]:
        if entry["type"] == "oracle_cards":
            oracle_entry = entry
            break

    if not oracle_entry:
        raise ValueError("Could not find oracle_cards bulk data")

    download_url = oracle_entry["download_uri"]
    print(f"Downloading oracle cards from {download_url} ...")
    resp = requests.get(download_url, stream=True)
    resp.raise_for_status()

    cards = resp.json()
    print(f"Downloaded {len(cards)} cards")
    return cards


COLOR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}


def build_card_document(card: dict) -> str:
    """Build a comprehensive text document from ALL card fields for embedding."""
    parts = []

    # ---- Core identity ----
    parts.append(f"Name: {card.get('name', '')}")

    if card.get("mana_cost"):
        parts.append(f"Mana Cost: {card['mana_cost']}")
    if card.get("cmc") is not None:
        parts.append(f"Mana Value: {card['cmc']}")

    parts.append(f"Type: {card.get('type_line', '')}")

    if card.get("oracle_text"):
        parts.append(f"Oracle Text: {card['oracle_text']}")

    # ---- Colors ----
    if card.get("colors"):
        colors = [COLOR_NAMES.get(c, c) for c in card["colors"]]
        parts.append(f"Colors: {', '.join(colors)}")
    else:
        parts.append("Colors: Colorless")

    if card.get("color_identity"):
        ci = [COLOR_NAMES.get(c, c) for c in card["color_identity"]]
        parts.append(f"Color Identity: {', '.join(ci)}")

    # ---- Keywords ----
    if card.get("keywords"):
        parts.append(f"Keywords: {', '.join(card['keywords'])}")

    # ---- Stats ----
    if card.get("power") and card.get("toughness"):
        parts.append(f"Power/Toughness: {card['power']}/{card['toughness']}")
    if card.get("loyalty"):
        parts.append(f"Loyalty: {card['loyalty']}")
    if card.get("defense"):
        parts.append(f"Defense: {card['defense']}")

    # ---- Mana production ----
    if card.get("produced_mana"):
        pm = [COLOR_NAMES.get(c, c) for c in card["produced_mana"]]
        parts.append(f"Produces Mana: {', '.join(pm)}")

    # ---- Set & rarity ----
    if card.get("set_name"):
        parts.append(f"Set: {card['set_name']}")
    if card.get("rarity"):
        parts.append(f"Rarity: {card['rarity'].capitalize()}")

    # ---- Flavor & artist ----
    if card.get("flavor_text"):
        parts.append(f"Flavor: {card['flavor_text']}")
    if card.get("artist"):
        parts.append(f"Artist: {card['artist']}")

    # ---- Layout & card faces ----
    if card.get("layout"):
        parts.append(f"Layout: {card['layout']}")

    if card.get("card_faces"):
        for i, face in enumerate(card["card_faces"]):
            parts.append(f"--- Face {i + 1} ---")
            if face.get("name"):
                parts.append(f"Face Name: {face['name']}")
            if face.get("mana_cost"):
                parts.append(f"Face Mana Cost: {face['mana_cost']}")
            if face.get("type_line"):
                parts.append(f"Face Type: {face['type_line']}")
            if face.get("oracle_text"):
                parts.append(f"Face Oracle Text: {face['oracle_text']}")
            if face.get("power") and face.get("toughness"):
                parts.append(f"Face P/T: {face['power']}/{face['toughness']}")
            if face.get("loyalty"):
                parts.append(f"Face Loyalty: {face['loyalty']}")
            if face.get("colors"):
                fc = [COLOR_NAMES.get(c, c) for c in face["colors"]]
                parts.append(f"Face Colors: {', '.join(fc)}")
            if face.get("keywords"):
                parts.append(f"Face Keywords: {', '.join(face['keywords'])}")
            if face.get("flavor_text"):
                parts.append(f"Face Flavor: {face['flavor_text']}")

    # ---- Legalities ----
    if card.get("legalities"):
        legal_formats = [fmt for fmt, status in card["legalities"].items() if status == "legal"]
        if legal_formats:
            parts.append(f"Legal in: {', '.join(legal_formats)}")

    # ---- Game availability ----
    if card.get("games"):
        parts.append(f"Games: {', '.join(card['games'])}")

    # ---- Boolean properties ----
    props = []
    if card.get("reserved"):
        props.append("Reserved List")
    if card.get("reprint"):
        props.append("Reprint")
    if card.get("promo"):
        props.append("Promo")
    if card.get("full_art"):
        props.append("Full Art")
    if card.get("digital"):
        props.append("Digital Only")
    if card.get("oversized"):
        props.append("Oversized")
    if props:
        parts.append(f"Properties: {', '.join(props)}")

    # ---- Rankings ----
    if card.get("edhrec_rank"):
        parts.append(f"EDHREC Rank: {card['edhrec_rank']}")

    return "\n".join(parts)


def process_card(card: dict) -> dict | None:
    """Process a Scryfall card: build embedding document, return id + document."""
    if card.get("layout") in ("token", "emblem", "art_series"):
        return None

    document = build_card_document(card)

    return {
        "id": card["id"],
        "document": document,
    }
