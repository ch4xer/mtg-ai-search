import os
import re
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
BULK_DATA_CACHE = os.path.join(DATA_DIR, "unique_artwork.json")


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


def download_bulk_data_to_file(filepath: str = None) -> str:
    """Download unique_artwork bulk data to local file.

    Returns the path to the downloaded file.
    """
    filepath = filepath or BULK_DATA_CACHE
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    bulk_url = "https://api.scryfall.com/bulk-data"
    resp = requests.get(bulk_url)
    resp.raise_for_status()
    bulk_data = resp.json()

    artwork_entry = None
    for entry in bulk_data["data"]:
        if entry["type"] == "unique_artwork":
            artwork_entry = entry
            break

    if not artwork_entry:
        raise ValueError("Could not find unique_artwork bulk data")

    download_url = artwork_entry["download_uri"]
    updated_at = artwork_entry.get("updated_at", "")

    # Check if existing file is up-to-date
    if os.path.exists(filepath):
        meta_file = filepath + ".meta"
        if os.path.exists(meta_file):
            with open(meta_file, "r") as f:
                cached_updated = f.read().strip()
            if cached_updated == updated_at:
                print(f"Using cached file: {filepath} (updated: {updated_at})")
                return filepath

    print(f"Downloading unique artwork cards from {download_url} ...")
    resp = requests.get(download_url, stream=True)
    resp.raise_for_status()

    # Write to file with progress
    total_size = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total_size > 0 and downloaded % (10 * 1024 * 1024) == 0:
                print(f"  Downloaded {downloaded / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB")

    print(f"Downloaded to {filepath} ({downloaded / 1024 / 1024:.1f}MB)")

    # Save metadata for cache check
    meta_file = filepath + ".meta"
    with open(meta_file, "w") as f:
        f.write(updated_at)

    return filepath


def stream_cards(filepath: str = None, chunk_size: int = 5000):
    """Stream unique artwork cards from local file in chunks.

    Downloads file if not present, then uses ijson to parse incrementally
    without loading entire file into memory.
    """
    import ijson

    filepath = filepath or BULK_DATA_CACHE
    if not os.path.exists(filepath):
        filepath = download_bulk_data_to_file(filepath)

    print(f"Streaming from local file: {filepath}")
    with open(filepath, "rb") as f:
        chunk = []
        total = 0
        for card in ijson.items(f, "item"):
            chunk.append(card)
            if len(chunk) >= chunk_size:
                total += len(chunk)
                print(f"  Yielded chunk: {len(chunk)} cards (total: {total})")
                yield chunk
                chunk = []

        if chunk:
            total += len(chunk)
            print(f"  Yielded final chunk: {len(chunk)} cards (total: {total})")
            yield chunk

    print(f"Streamed {total} cards from local file")