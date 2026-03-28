"""One-time setup script to download and index MTG data into ChromaDB + SQLite."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data_loader import download_scryfall_cards, parse_keyword_abilities, process_card
from app.database import init_db, insert_cards_batch
from app.vectorstore import get_abilities_collection, get_cards_collection

KEYWORD_ABILITY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "keyword_ability.txt",
)


def log(msg):
    print(msg, flush=True)


def setup_abilities():
    log("=== Setting up keyword abilities ===")
    abilities = parse_keyword_abilities(KEYWORD_ABILITY_FILE)
    log(f"Parsed {len(abilities)} keyword abilities")

    collection = get_abilities_collection()

    ids = []
    documents = []
    metadatas = []

    for name, description in abilities.items():
        doc = f"{name}: {description}"
        ids.append(name.lower().replace(" ", "_"))
        documents.append(doc)
        metadatas.append({"name": name})

    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        t0 = time.time()
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
        )
        log(f"  Indexed abilities {i + 1}-{end} ({time.time() - t0:.1f}s)")

    log(f"Done: {len(ids)} abilities indexed\n")


def setup_cards():
    log("=== Setting up card data ===")
    raw_cards = download_scryfall_cards()

    # Step 1: Store all raw card data into SQLite
    log("Storing all card data into SQLite...")
    init_db()
    db_batch_size = 1000
    valid_cards = [c for c in raw_cards if c.get("layout") not in ("token", "emblem", "art_series")]
    for i in range(0, len(valid_cards), db_batch_size):
        end = min(i + db_batch_size, len(valid_cards))
        insert_cards_batch(valid_cards[i:end])
    log(f"Stored {len(valid_cards)} cards in SQLite\n")

    # Step 2: Build embedding documents and index into ChromaDB
    log("Building embedding documents...")
    collection = get_cards_collection()

    ids = []
    documents = []

    for card in raw_cards:
        processed = process_card(card)
        if processed:
            ids.append(processed["id"])
            documents.append(processed["document"])

    total = len(ids)
    log(f"Indexing {total} cards into ChromaDB...")

    batch_size = 200
    total_batches = (total + batch_size - 1) // batch_size
    for batch_num, i in enumerate(range(0, total, batch_size), 1):
        end = min(i + batch_size, total)
        t0 = time.time()
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
        )
        elapsed = time.time() - t0
        log(f"  [{batch_num}/{total_batches}] Indexed cards {i + 1}-{end} ({elapsed:.1f}s)")

    log(f"Done: {total} cards indexed into ChromaDB\n")


if __name__ == "__main__":
    t_start = time.time()
    setup_abilities()
    setup_cards()
    log(f"Setup complete! Total time: {time.time() - t_start:.0f}s")
