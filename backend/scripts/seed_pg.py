"""Seed script: download Scryfall data, populate PostgreSQL + pgvector.

Usage:
    1. Start PostgreSQL: docker compose up db -d
    2. Run: cd backend && python scripts/seed_pg.py
"""

import json
import os
import sys
import time

import psycopg
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.data_loader import download_scryfall_cards, parse_keyword_abilities

KEYWORD_ABILITY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "keyword_ability.txt",
)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://mtg:mtg_password@localhost:5433/mtg"
)


def log(msg: str):
    print(msg, flush=True)


def get_conn():
    return psycopg.connect(DATABASE_URL)


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
                image_png             TEXT,
                image_art_crop        TEXT,
                image_border_crop     TEXT,
                mana_cost             TEXT,
                cmc                   REAL,
                type_line             TEXT,
                oracle_text           TEXT,
                power                 TEXT,
                toughness             TEXT,
                colors                TEXT[],
                keywords              TEXT[] DEFAULT '{}',
                is_playtest           BOOLEAN NOT NULL DEFAULT FALSE,
                data                  JSONB NOT NULL,
                name_embedding        halfvec(2560),
                type_line_embedding   halfvec(2560),
                oracle_text_embedding halfvec(2560)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS keyword_abilities (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL,
                embedding   halfvec(2560)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMPTZ DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS decks (
                id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name       TEXT NOT NULL,
                format     TEXT NOT NULL DEFAULT 'undefined',
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        # Migration for existing deployments
        cur.execute(
            "ALTER TABLE decks ADD COLUMN IF NOT EXISTS format TEXT NOT NULL DEFAULT 'undefined'"
        )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS deck_cards (
                id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                deck_id  UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                card_id  TEXT NOT NULL REFERENCES cards(id),
                quantity INT NOT NULL DEFAULT 1,
                added_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE(deck_id, card_id)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_decks_user_id ON decks(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deck_cards_deck_id ON deck_cards(deck_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_released_at ON cards(released_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_cmc ON cards(cmc)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_colors ON cards USING GIN(colors)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_keywords ON cards USING GIN(keywords)")
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
                raw_colors = card.get("colors")
                colors = raw_colors if raw_colors is not None else (card.get("color_identity") or [])
                keywords = card.get("keywords") or []
                values.append((
                    card["id"],
                    card.get("name", ""),
                    card.get("lang"),
                    card.get("released_at"),
                    card.get("uri"),
                    card.get("scryfall_uri"),
                    card.get("layout"),
                    image_uris.get("png"),
                    image_uris.get("art_crop"),
                    image_uris.get("border_crop"),
                    card.get("mana_cost"),
                    card.get("cmc"),
                    card.get("type_line"),
                    card.get("oracle_text"),
                    card.get("power"),
                    card.get("toughness"),
                    colors,
                    keywords,
                    card.get("set_type") == "funny",
                    json.dumps(card),
                ))
            cur.executemany(
                """INSERT INTO cards (
                    id, name, lang, released_at, uri, scryfall_uri, layout,
                    image_png, image_art_crop, image_border_crop, mana_cost, cmc, type_line,
                    oracle_text, power, toughness, colors, keywords, is_playtest, data
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT (id) DO UPDATE SET
                    image_png = EXCLUDED.image_png,
                    image_art_crop = EXCLUDED.image_art_crop,
                    image_border_crop = EXCLUDED.image_border_crop,
                    mana_cost = EXCLUDED.mana_cost,
                    cmc = EXCLUDED.cmc,
                    power = EXCLUDED.power,
                    toughness = EXCLUDED.toughness,
                    colors = EXCLUDED.colors,
                    keywords = EXCLUDED.keywords,
                    is_playtest = EXCLUDED.is_playtest,
                    data = EXCLUDED.data,
                    name = EXCLUDED.name,
                    type_line = EXCLUDED.type_line,
                    oracle_text = EXCLUDED.oracle_text,
                    name_embedding = CASE WHEN cards.name IS NOT DISTINCT FROM EXCLUDED.name THEN cards.name_embedding ELSE NULL END,
                    type_line_embedding = CASE WHEN cards.type_line IS NOT DISTINCT FROM EXCLUDED.type_line THEN cards.type_line_embedding ELSE NULL END,
                    oracle_text_embedding = CASE WHEN cards.oracle_text IS NOT DISTINCT FROM EXCLUDED.oracle_text THEN cards.oracle_text_embedding ELSE NULL END
                """,
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
        cur.executemany(
            "INSERT INTO keyword_abilities (id, name, description) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
            values,
        )
    conn.commit()
    log("Abilities inserted.")


def generate_card_embeddings(conn, batch_size: int = 200, max_rounds: int = 10, on_progress=None):
    """Generate and store embeddings for cards. Skips failed batches and retries in later rounds.

    on_progress: optional callback(done, total) called after each batch.
    """
    from app.embedding import encode_batch_safe

    for round_num in range(1, max_rounds + 1):
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, type_line, oracle_text FROM cards WHERE name_embedding IS NULL")
            rows = cur.fetchall()

        if not rows:
            log("All card embeddings complete.")
            return

        log(f"Generating card embeddings (round {round_num}/{max_rounds}): {len(rows)} cards remaining...")
        total = len(rows)
        failed = 0

        for i in range(0, total, batch_size):
            batch = rows[i:i + batch_size]
            ids = [r[0] for r in batch]
            names = [r[1] or "" for r in batch]
            type_lines = [r[2] or "" for r in batch]
            oracle_texts = [r[3] or "" for r in batch]

            t0 = time.time()
            name_vecs = encode_batch_safe(names)
            type_vecs = encode_batch_safe(type_lines)
            oracle_vecs = encode_batch_safe(oracle_texts)

            if name_vecs is None or type_vecs is None or oracle_vecs is None:
                failed += len(batch)
                log(f"  [{min(i + batch_size, total)}/{total}] SKIPPED {len(batch)} cards (API error)")
                continue

            with conn.cursor() as cur:
                for j, card_id in enumerate(ids):
                    cur.execute(
                        """UPDATE cards SET
                            name_embedding = %s::halfvec,
                            type_line_embedding = %s::halfvec,
                            oracle_text_embedding = %s::halfvec
                        WHERE id = %s""",
                        (str(name_vecs[j]), str(type_vecs[j]), str(oracle_vecs[j]), card_id),
                    )
            conn.commit()

            done = min(i + batch_size, total)
            elapsed = time.time() - t0
            log(f"  [{done}/{total}] Embedded {len(batch)} cards ({elapsed:.1f}s)")
            if on_progress:
                on_progress(done, total)

        if failed == 0:
            return
        log(f"Round {round_num} done. {failed} cards failed, will retry...")
        time.sleep(10)

    # Check remaining after all rounds
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM cards WHERE name_embedding IS NULL")
        remaining = cur.fetchone()[0]
    if remaining > 0:
        log(f"WARNING: {remaining} cards still missing embeddings after {max_rounds} rounds.")
    else:
        log("All card embeddings complete.")


def generate_ability_embeddings(conn, max_rounds: int = 10, on_progress=None):
    """Generate and store embeddings for keyword abilities with retry.

    on_progress: optional callback(done, total) called on completion.
    """
    from app.embedding import encode_batch_safe

    for round_num in range(1, max_rounds + 1):
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, description FROM keyword_abilities WHERE embedding IS NULL")
            rows = cur.fetchall()

        if not rows:
            log("All ability embeddings complete.")
            return

        total = len(rows)
        log(f"Generating ability embeddings (round {round_num}/{max_rounds}): {total} remaining...")
        texts = [f"{r[1]}: {r[2]}" for r in rows]
        vecs = encode_batch_safe(texts)

        if vecs is None:
            log(f"  Round {round_num} failed, retrying in 10s...")
            time.sleep(10)
            continue

        with conn.cursor() as cur:
            for i, row in enumerate(rows):
                cur.execute(
                    "UPDATE keyword_abilities SET embedding = %s::halfvec WHERE id = %s",
                    (str(vecs[i]), row[0]),
                )
        conn.commit()
        log(f"  Embedded {total} abilities.")
        if on_progress:
            on_progress(total, total)
        return

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM keyword_abilities WHERE embedding IS NULL")
        remaining = cur.fetchone()[0]
    if remaining > 0:
        log(f"WARNING: {remaining} abilities still missing embeddings after {max_rounds} rounds.")


def create_vector_indexes(conn):
    """Skipped – halfvec columns are searched via sequential scan."""
    log("Skipping vector index creation (halfvec sequential scan).")


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
