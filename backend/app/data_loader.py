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
