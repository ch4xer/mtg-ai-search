import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cards.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Ensure table exists even if setup hasn't been run
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            data TEXT NOT NULL
        )
    """)
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            data TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)")
    conn.commit()
    conn.close()


def insert_cards_batch(cards: list[dict]):
    conn = get_connection()
    conn.executemany(
        "INSERT OR REPLACE INTO cards (id, name, data) VALUES (?, ?, ?)",
        [(card["id"], card.get("name", ""), json.dumps(card, ensure_ascii=False)) for card in cards],
    )
    conn.commit()
    conn.close()


def get_card_by_id(card_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT data FROM cards WHERE id = ?", (card_id,)).fetchone()
    conn.close()
    if row:
        return json.loads(row["data"])
    return None


def get_cards_by_ids(card_ids: list[str]) -> list[dict]:
    if not card_ids:
        return []
    conn = get_connection()
    placeholders = ",".join("?" * len(card_ids))
    rows = conn.execute(
        f"SELECT id, data FROM cards WHERE id IN ({placeholders})", card_ids
    ).fetchall()
    conn.close()
    # Preserve the order of card_ids
    id_to_data = {row["id"]: json.loads(row["data"]) for row in rows}
    return [id_to_data[cid] for cid in card_ids if cid in id_to_data]
