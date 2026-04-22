import os
import re
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
BULK_DATA_TYPE = "all_cards"
BULK_DATA_CACHE = os.path.join(DATA_DIR, "all-cards.json")
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def _env_bulk_data_file() -> str | None:
    path = os.getenv("SCRYFALL_BULK_DATA_FILE", "").strip()
    return path or None


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
    """Download all_cards bulk data to local file, resuming partial downloads.

    Returns the path to the downloaded file.
    """
    filepath = filepath or BULK_DATA_CACHE
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    bulk_url = "https://api.scryfall.com/bulk-data"
    resp = requests.get(bulk_url)
    resp.raise_for_status()
    bulk_data = resp.json()

    bulk_entry = None
    for entry in bulk_data["data"]:
        if entry["type"] == BULK_DATA_TYPE:
            bulk_entry = entry
            break

    if not bulk_entry:
        raise ValueError(f"Could not find {BULK_DATA_TYPE} bulk data")

    download_url = bulk_entry["download_uri"]
    updated_at = bulk_entry.get("updated_at", "")

    # Check if existing file is up-to-date
    meta_file = filepath + ".meta"
    if os.path.exists(filepath):
        if os.path.exists(meta_file):
            with open(meta_file, "r") as f:
                cached_updated = f.read().strip()
            if cached_updated == updated_at:
                print(f"Using cached file: {filepath} (updated: {updated_at})")
                return filepath

    part_file = filepath + ".part"
    part_meta_file = part_file + ".meta"
    if os.path.exists(part_meta_file):
        with open(part_meta_file, "r") as f:
            part_updated = f.read().strip()
        if part_updated != updated_at:
            if os.path.exists(part_file):
                os.remove(part_file)
            os.remove(part_meta_file)
    elif os.path.exists(part_file):
        os.remove(part_file)

    with open(part_meta_file, "w") as f:
        f.write(updated_at)

    resume_from = os.path.getsize(part_file) if os.path.exists(part_file) else 0
    headers = {"Range": f"bytes={resume_from}-"} if resume_from else {}
    mode = "ab" if resume_from else "wb"

    print(f"Downloading {BULK_DATA_TYPE} cards from {download_url} ...")
    if resume_from:
        print(f"  Resuming from {resume_from / 1024 / 1024:.1f}MB")
    resp = requests.get(download_url, headers=headers, stream=True, timeout=60)
    if resume_from and resp.status_code != 206:
        print("  Server did not resume; restarting download.")
        resume_from = 0
        mode = "wb"
        resp.close()
        resp = requests.get(download_url, stream=True, timeout=60)
    resp.raise_for_status()

    # Write to file with progress
    total_size = int(resp.headers.get("content-length", 0))
    expected_size = resume_from + total_size if total_size else 0
    downloaded = resume_from
    with open(part_file, mode) as f:
        for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)
            if downloaded % (50 * 1024 * 1024) < DOWNLOAD_CHUNK_SIZE:
                if expected_size:
                    print(f"  Downloaded {downloaded / 1024 / 1024:.1f}MB / {expected_size / 1024 / 1024:.1f}MB")
                else:
                    print(f"  Downloaded {downloaded / 1024 / 1024:.1f}MB")

    os.replace(part_file, filepath)
    if os.path.exists(part_meta_file):
        os.remove(part_meta_file)
    print(f"Downloaded to {filepath} ({downloaded / 1024 / 1024:.1f}MB)")

    # Save metadata for cache check
    with open(meta_file, "w") as f:
        f.write(updated_at)

    return filepath


def stream_cards(filepath: str = None, chunk_size: int = 5000):
    """Stream all_cards from local file in chunks.

    Downloads file if not present, then uses ijson to parse incrementally
    without loading entire file into memory.
    """
    import ijson

    if filepath is None:
        env_file = _env_bulk_data_file()
        if env_file:
            if not os.path.exists(env_file):
                raise FileNotFoundError(f"SCRYFALL_BULK_DATA_FILE does not exist: {env_file}")
            filepath = env_file
        else:
            filepath = download_bulk_data_to_file(BULK_DATA_CACHE)
    elif not os.path.exists(filepath):
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
