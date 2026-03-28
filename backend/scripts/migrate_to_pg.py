"""Migration script: download Scryfall data, populate PostgreSQL + pgvector.

Usage:
    1. Start PostgreSQL: docker compose up db -d
    2. Run: cd backend && python scripts/migrate_to_pg.py
"""

import json
import os
import sys
import time

import psycopg2
from psycopg2.extras import execute_values

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.data_loader import download_scryfall_cards, parse_keyword_abilities
from app.embedding import encode

KEYWORD_ABILITY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "keyword_ability.txt",
)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://mtg:mtg_password@localhost:5432/mtg"
)


def log(msg: str):
    print(msg, flush=True)


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def create_schema(conn):
    """Create pgvector extension and tables."""
    log("Creating schema...")
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id                    TEXT PRIMARY KEY,
                name                  TEXT NOT NULL,
                lang                  TEXT,
                released_at           DATE,
                uri                   TEXT,
                scryfall_uri          TEXT,
                layout                TEXT,
                image_art_crop        TEXT,
                image_border_crop     TEXT,
                mana_cost             TEXT,
                cmc                   REAL,
                type_line             TEXT,
                oracle_text           TEXT,
                power                 TEXT,
                toughness             TEXT,
                colors                TEXT[],
                data                  JSONB NOT NULL,
                name_embedding        vector(1024),
                type_line_embedding   vector(1024),
                oracle_text_embedding vector(1024)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS keyword_abilities (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL,
                embedding   vector(1024)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_released_at ON cards(released_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_cmc ON cards(cmc)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_colors ON cards USING GIN(colors)")
    conn.commit()
    log("Schema created.")


def insert_cards(conn, cards: list[dict]):
    """Insert card rows (without embeddings) in batches."""
    log(f"Inserting {len(cards)} cards...")
    batch_size = 1000

    with conn.cursor() as cur:
        for i in range(0, len(cards), batch_size):
            batch = cards[i:i + batch_size]
            values = []
            for card in batch:
                image_uris = card.get("image_uris") or {}
                colors = card.get("colors") or []
                values.append((
                    card["id"],
                    card.get("name", ""),
                    card.get("lang"),
                    card.get("released_at"),
                    card.get("uri"),
                    card.get("scryfall_uri"),
                    card.get("layout"),
                    image_uris.get("art_crop"),
                    image_uris.get("border_crop"),
                    card.get("mana_cost"),
                    card.get("cmc"),
                    card.get("type_line"),
                    card.get("oracle_text"),
                    card.get("power"),
                    card.get("toughness"),
                    colors,
                    json.dumps(card),
                ))
            execute_values(
                cur,
                """INSERT INTO cards (
                    id, name, lang, released_at, uri, scryfall_uri, layout,
                    image_art_crop, image_border_crop, mana_cost, cmc, type_line,
                    oracle_text, power, toughness, colors, data
                ) VALUES %s ON CONFLICT (id) DO NOTHING""",
                values,
            )
            conn.commit()
            log(f"  Inserted cards {i + 1}-{min(i + batch_size, len(cards))}")


def insert_abilities(conn, abilities: dict[str, str]):
    """Insert keyword abilities (without embeddings)."""
    log(f"Inserting {len(abilities)} keyword abilities...")
    with conn.cursor() as cur:
        values = [
            (name.lower().replace(" ", "_"), name, desc)
            for name, desc in abilities.items()
        ]
        execute_values(
            cur,
            "INSERT INTO keyword_abilities (id, name, description) VALUES %s ON CONFLICT (id) DO NOTHING",
            values,
        )
    conn.commit()
    log("Abilities inserted.")


def generate_card_embeddings(conn, batch_size: int = 200):
    """Generate and store embeddings for cards."""
    log("Generating card embeddings...")
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, type_line, oracle_text FROM cards WHERE name_embedding IS NULL")
        rows = cur.fetchall()

    log(f"  {len(rows)} cards need embeddings")
    total = len(rows)

    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        ids = [r[0] for r in batch]
        names = [r[1] or "" for r in batch]
        type_lines = [r[2] or "" for r in batch]
        oracle_texts = [r[3] or "" for r in batch]

        t0 = time.time()
        name_vecs = encode(names)
        type_vecs = encode(type_lines)
        oracle_vecs = encode(oracle_texts)

        with conn.cursor() as cur:
            for j, card_id in enumerate(ids):
                cur.execute(
                    """UPDATE cards SET
                        name_embedding = %s::vector,
                        type_line_embedding = %s::vector,
                        oracle_text_embedding = %s::vector
                    WHERE id = %s""",
                    (str(name_vecs[j]), str(type_vecs[j]), str(oracle_vecs[j]), card_id),
                )
        conn.commit()

        elapsed = time.time() - t0
        log(f"  [{min(i + batch_size, total)}/{total}] Embedded {len(batch)} cards ({elapsed:.1f}s)")


def generate_ability_embeddings(conn):
    """Generate and store embeddings for keyword abilities."""
    log("Generating ability embeddings...")
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, description FROM keyword_abilities WHERE embedding IS NULL")
        rows = cur.fetchall()

    if not rows:
        log("  No abilities need embeddings.")
        return

    texts = [f"{r[1]}: {r[2]}" for r in rows]
    vecs = encode(texts)

    with conn.cursor() as cur:
        for i, row in enumerate(rows):
            cur.execute(
                "UPDATE keyword_abilities SET embedding = %s::vector WHERE id = %s",
                (str(vecs[i]), row[0]),
            )
    conn.commit()
    log(f"  Embedded {len(rows)} abilities.")


def create_vector_indexes(conn):
    """Create ivfflat indexes after data is loaded."""
    log("Creating vector indexes...")
    with conn.cursor() as cur:
        # ivfflat needs lists parameter; use sqrt(n) as a reasonable default
        cur.execute("SELECT COUNT(*) FROM cards WHERE name_embedding IS NOT NULL")
        card_count = cur.fetchone()[0]
        lists = max(1, int(card_count ** 0.5))
        log(f"  Using {lists} lists for ivfflat (based on {card_count} cards)")

        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_cards_name_vec ON cards USING ivfflat(name_embedding vector_cosine_ops) WITH (lists = {lists})")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_cards_type_vec ON cards USING ivfflat(type_line_embedding vector_cosine_ops) WITH (lists = {lists})")
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_cards_oracle_vec ON cards USING ivfflat(oracle_text_embedding vector_cosine_ops) WITH (lists = {lists})")

        cur.execute("SELECT COUNT(*) FROM keyword_abilities WHERE embedding IS NOT NULL")
        ability_count = cur.fetchone()[0]
        ability_lists = max(1, int(ability_count ** 0.5))
        cur.execute(f"CREATE INDEX IF NOT EXISTS idx_abilities_vec ON keyword_abilities USING ivfflat(embedding vector_cosine_ops) WITH (lists = {ability_lists})")
    conn.commit()
    log("Vector indexes created.")


def main():
    t_start = time.time()

    conn = get_conn()
    try:
        create_schema(conn)

        # Download and insert cards
        raw_cards = download_scryfall_cards()
        valid_cards = [c for c in raw_cards if c.get("layout") not in ("token", "emblem", "art_series")]
        insert_cards(conn, valid_cards)

        # Parse and insert abilities
        abilities = parse_keyword_abilities(KEYWORD_ABILITY_FILE)
        insert_abilities(conn, abilities)

        # Generate embeddings
        generate_card_embeddings(conn)
        generate_ability_embeddings(conn)

        # Create vector indexes
        create_vector_indexes(conn)

    finally:
        conn.close()

    log(f"\nMigration complete! Total time: {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
