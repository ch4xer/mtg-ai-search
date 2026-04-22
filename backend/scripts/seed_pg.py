"""Seed script: download Scryfall all_cards data, populate PostgreSQL + pgvector.

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

from app.data_loader import (
    parse_keyword_abilities,
    stream_cards,
)
from app.effect_chunks import build_card_effect_chunks

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
    """Create pgvector extension and tables with multi-print support."""
    log("Creating schema...")
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # cards 表：存储卡牌基本信息（以 oracle_id 为主键）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id                    TEXT PRIMARY KEY,
                name                  TEXT NOT NULL,
                mana_cost             TEXT,
                cmc                   REAL,
                type_line             TEXT,
                oracle_text           TEXT,
                power                 TEXT,
                toughness             TEXT,
                colors                TEXT[],
                color_identity        TEXT[],
                keywords              TEXT[] DEFAULT '{}',
                legalities            JSONB,
                layout                TEXT,
                card_faces            JSONB,
                image_set_code        TEXT,
                image_set_name        TEXT,
                image_collector_number TEXT,
                name_embedding        halfvec(2560),
                type_line_embedding   halfvec(2560),
                oracle_text_embedding halfvec(2560)
            )
        """)

        # card_prints 表：存储印刷版本信息（一个 oracle_id 对应多个版本）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS card_prints (
                id              TEXT PRIMARY KEY,
                card_id         TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                set_code        TEXT NOT NULL,
                set_name        TEXT NOT NULL,
                collector_num   TEXT NOT NULL,
                rarity          TEXT,
                artist          TEXT,
                flavor_name     TEXT,
                flavor_text     TEXT,
                released_at     DATE,
                finishes        TEXT[],
                image_small     TEXT,
                image_normal    TEXT,
                image_large     TEXT,
                image_png       TEXT,
                image_art_crop  TEXT,
                image_border_crop TEXT,
                card_faces      JSONB,
                image_set_code  TEXT,
                image_set_name  TEXT,
                image_collector_number TEXT,
                UNIQUE(card_id, set_code, collector_num)
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
            CREATE TABLE IF NOT EXISTS card_effects (
                id           TEXT PRIMARY KEY,
                card_id      TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                face_index   INT NOT NULL DEFAULT 0,
                chunk_index  INT NOT NULL,
                effect_text  TEXT NOT NULL,
                source       TEXT NOT NULL DEFAULT 'oracle_text',
                embedding    halfvec(2560),
                UNIQUE(card_id, face_index, chunk_index)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'user',
                email         TEXT,
                email_verified BOOLEAN NOT NULL DEFAULT FALSE,
                verification_code TEXT,
                verification_code_expires_at TIMESTAMPTZ,
                verification_attempts INT NOT NULL DEFAULT 0,
                last_active_at TIMESTAMPTZ,
                created_at    TIMESTAMPTZ DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS decks (
                id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name                 TEXT NOT NULL,
                format               TEXT NOT NULL DEFAULT 'undefined',
                analysis_data        JSONB,
                analysis_updated_at  TIMESTAMPTZ,
                created_at           TIMESTAMPTZ DEFAULT now(),
                updated_at           TIMESTAMPTZ DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS deck_cards (
                id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                deck_id    UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                card_id    TEXT NOT NULL REFERENCES cards(id),
                print_id   TEXT REFERENCES card_prints(id) ON DELETE SET NULL,
                quantity   INT NOT NULL DEFAULT 1,
                image_url  TEXT,
                display_url TEXT,
                board      TEXT NOT NULL DEFAULT 'mainboard',
                added_at   TIMESTAMPTZ DEFAULT now(),
                UNIQUE(deck_id, card_id, board)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS search_logs (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
                query         TEXT NOT NULL,
                tokens_prompt INT NOT NULL DEFAULT 0,
                tokens_completion INT NOT NULL DEFAULT 0,
                ip_address    TEXT,
                created_at    TIMESTAMPTZ DEFAULT now()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sync_logs (
                id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                completed_at TIMESTAMPTZ,
                status       TEXT NOT NULL DEFAULT 'running',
                new_cards    INT NOT NULL DEFAULT 0,
                updated_cards INT NOT NULL DEFAULT 0,
                message      TEXT NOT NULL DEFAULT ''
            )
        """)

        # 索引
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_decks_user_id ON decks(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_deck_cards_deck_id ON deck_cards(deck_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_user_id ON search_logs(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_ip_address ON search_logs(ip_address)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_cmc ON cards(cmc)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_colors ON cards USING GIN(colors)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_cards_keywords ON cards USING GIN(keywords)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_card_effects_card_id ON card_effects(card_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_card_prints_card_id ON card_prints(card_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_card_prints_set_code ON card_prints(set_code)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_card_prints_lookup ON card_prints(card_id, set_code, collector_num)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_card_prints_flavor_name ON card_prints(flavor_name)")
    conn.commit()
    log("Schema created.")


def insert_cards_and_prints(conn, chunk_size: int = 5000, batch_size: int = 1000):
    """Stream and insert cards/prints in chunks to reduce memory usage.

    Downloads bulk data to local file once, then streams from it.
    Ensures cards are inserted before their prints to satisfy foreign key constraints.
    """
    oracle_groups: dict[str, list[dict]] = {}
    total_prints = 0
    total_oracles = 0

    # First pass: collect and insert cards
    log("Processing cards...")
    for chunk in stream_cards(chunk_size=chunk_size):
        valid_prints = [
            p for p in chunk
            if p.get("layout") not in ("token", "emblem", "art_series")
            and p.get("lang") == "en"
            and p.get("oracle_id")
        ]
        total_prints += len(valid_prints)

        # Group by oracle_id
        for p in valid_prints:
            oracle_id = p.get("oracle_id")
            if oracle_id:
                oracle_groups.setdefault(oracle_id, []).append(p)

        # Periodically flush cards to reduce memory
        if len(oracle_groups) >= chunk_size * 2:
            _insert_cards_batch(conn, oracle_groups, batch_size)
            total_oracles += len(oracle_groups)
            oracle_groups.clear()
            log(f"  Inserted {total_oracles} cards so far")

    # Final flush for remaining cards
    if oracle_groups:
        _insert_cards_batch(conn, oracle_groups, batch_size)
        total_oracles += len(oracle_groups)
        log(f"  Final: {total_oracles} cards total")

    log(f"Cards complete: {total_oracles} unique oracle_ids")

    # Second pass: insert prints (cards now exist for all foreign keys)
    log("Inserting card prints...")
    prints_inserted = 0
    for chunk in stream_cards(chunk_size=chunk_size):
        valid_prints = [
            p for p in chunk
            if p.get("layout") not in ("token", "emblem", "art_series")
            and p.get("lang") == "en"
            and p.get("oracle_id")
        ]
        _insert_prints_batch(conn, valid_prints, batch_size)
        prints_inserted += len(valid_prints)
        if prints_inserted % 10000 == 0:
            log(f"  Inserted {prints_inserted} prints so far")

    log(f"Prints complete: {prints_inserted} total")
    log(f"Summary: {total_oracles} cards, {prints_inserted} prints")
    sync_card_effect_chunks(conn)


def _insert_cards_batch(conn, oracle_groups: dict[str, list[dict]], batch_size: int):
    """Insert cards from oracle_groups dictionary."""
    cards_values = []
    for oracle_id, card_prints in oracle_groups.items():
        first_print = card_prints[0]
        card_faces = first_print.get("card_faces") or []
        face_mana_cost = " // ".join(f.get("mana_cost", "") for f in card_faces if f.get("mana_cost"))
        face_type_line = " // ".join(f.get("type_line", "") for f in card_faces if f.get("type_line"))
        face_oracle_text = "\n//\n".join(f.get("oracle_text", "") for f in card_faces if f.get("oracle_text"))
        first_power = next((f.get("power") for f in card_faces if f.get("power")), None)
        first_toughness = next((f.get("toughness") for f in card_faces if f.get("toughness")), None)
        legalities = first_print.get("legalities") or {}
        raw_colors = first_print.get("colors")
        colors = raw_colors if raw_colors is not None else (first_print.get("color_identity") or [])
        color_identity = first_print.get("color_identity") or []
        keywords = first_print.get("keywords") or []

        cards_values.append((
            oracle_id,
            first_print.get("name", ""),
            first_print.get("mana_cost") or face_mana_cost or None,
            first_print.get("cmc"),
            first_print.get("type_line") or face_type_line or None,
            first_print.get("oracle_text") or face_oracle_text or None,
            first_print.get("power") or first_power,
            first_print.get("toughness") or first_toughness,
            colors,
            color_identity,
            keywords,
            json.dumps(legalities),
            first_print.get("layout"),
            json.dumps(card_faces) if card_faces else None,
            first_print.get("set"),
            first_print.get("set_name"),
            first_print.get("collector_number"),
        ))

    with conn.cursor() as cur:
        for i in range(0, len(cards_values), batch_size):
            batch = cards_values[i:i + batch_size]
            cur.executemany(
                """INSERT INTO cards (
                    id, name, mana_cost, cmc, type_line, oracle_text,
                    power, toughness, colors, color_identity, keywords,
                    legalities, layout, card_faces,
                    image_set_code, image_set_name, image_collector_number
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    mana_cost = EXCLUDED.mana_cost,
                    cmc = EXCLUDED.cmc,
                    type_line = EXCLUDED.type_line,
                    oracle_text = EXCLUDED.oracle_text,
                    power = EXCLUDED.power,
                    toughness = EXCLUDED.toughness,
                    colors = EXCLUDED.colors,
                    color_identity = EXCLUDED.color_identity,
                    keywords = EXCLUDED.keywords,
                    legalities = EXCLUDED.legalities,
                    layout = EXCLUDED.layout,
                    card_faces = EXCLUDED.card_faces,
                    image_set_code = EXCLUDED.image_set_code,
                    image_set_name = EXCLUDED.image_set_name,
                    image_collector_number = EXCLUDED.image_collector_number,
                    name_embedding = CASE WHEN cards.name IS NOT DISTINCT FROM EXCLUDED.name THEN cards.name_embedding ELSE NULL END,
                    type_line_embedding = CASE WHEN cards.type_line IS NOT DISTINCT FROM EXCLUDED.type_line THEN cards.type_line_embedding ELSE NULL END,
                    oracle_text_embedding = CASE WHEN cards.oracle_text IS NOT DISTINCT FROM EXCLUDED.oracle_text THEN cards.oracle_text_embedding ELSE NULL END
                """,
                batch,
            )
            conn.commit()


def sync_card_effect_chunks(conn, card_ids: list[str] | None = None, batch_size: int = 500):
    """Create/update effect-level oracle text chunks for cards."""
    log("Syncing card effect chunks...")
    where = "WHERE id = ANY(%s)" if card_ids else ""
    params = (card_ids,) if card_ids else ()

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT id, oracle_text, card_faces, keywords FROM cards {where}",
            params,
        )
        rows = cur.fetchall()

    total = len(rows)
    for i in range(0, total, batch_size):
        batch = rows[i:i + batch_size]
        with conn.cursor() as cur:
            for card_id, oracle_text, card_faces, keywords in batch:
                card = {
                    "id": card_id,
                    "oracle_text": oracle_text,
                    "card_faces": card_faces,
                    "keywords": keywords or [],
                }
                chunks = build_card_effect_chunks(card)
                expected_ids = []
                for chunk in chunks:
                    chunk_id = f"{card_id}:{chunk['face_index']}:{chunk['chunk_index']}"
                    expected_ids.append(chunk_id)
                    cur.execute(
                        """INSERT INTO card_effects (
                               id, card_id, face_index, chunk_index, effect_text, source
                           ) VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (id) DO UPDATE SET
                               face_index = EXCLUDED.face_index,
                               chunk_index = EXCLUDED.chunk_index,
                               effect_text = EXCLUDED.effect_text,
                               source = EXCLUDED.source,
                               embedding = CASE
                                   WHEN card_effects.effect_text IS NOT DISTINCT FROM EXCLUDED.effect_text
                                   THEN card_effects.embedding
                                   ELSE NULL
                               END""",
                        (
                            chunk_id,
                            card_id,
                            chunk["face_index"],
                            chunk["chunk_index"],
                            chunk["effect_text"],
                            chunk["source"],
                        ),
                    )

                if expected_ids:
                    cur.execute(
                        "DELETE FROM card_effects WHERE card_id = %s AND NOT (id = ANY(%s))",
                        (card_id, expected_ids),
                    )
                else:
                    cur.execute("DELETE FROM card_effects WHERE card_id = %s", (card_id,))
        conn.commit()
        log(f"  [{min(i + batch_size, total)}/{total}] Synced effect chunks")


def _insert_prints_batch(conn, prints: list[dict], batch_size: int):
    """Insert card prints from a list."""
    prints_values = []
    for p in prints:
        oracle_id = p.get("oracle_id")
        if not oracle_id:
            continue
        image_uris = p.get("image_uris") or {}
        finishes = p.get("finishes") or []

        prints_values.append((
            p.get("id"),
            oracle_id,
            p.get("set"),
            p.get("set_name"),
            p.get("collector_number"),
            p.get("rarity"),
            p.get("artist"),
            p.get("flavor_name"),
            p.get("flavor_text"),
            p.get("released_at"),
            finishes,
            image_uris.get("small"),
            image_uris.get("normal"),
            image_uris.get("large"),
            image_uris.get("png"),
            image_uris.get("art_crop"),
            image_uris.get("border_crop"),
            json.dumps(p.get("card_faces")) if p.get("card_faces") else None,
            p.get("set"),
            p.get("set_name"),
            p.get("collector_number"),
        ))

    with conn.cursor() as cur:
        for i in range(0, len(prints_values), batch_size):
            batch = prints_values[i:i + batch_size]
            cur.executemany(
                """INSERT INTO card_prints (
                    id, card_id, set_code, set_name, collector_num,
                    rarity, artist, flavor_name, flavor_text, released_at, finishes,
                    image_small, image_normal, image_large, image_png,
                    image_art_crop, image_border_crop, card_faces,
                    image_set_code, image_set_name, image_collector_number
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (card_id, set_code, collector_num) DO UPDATE SET
                    rarity = EXCLUDED.rarity,
                    artist = EXCLUDED.artist,
                    flavor_name = COALESCE(EXCLUDED.flavor_name, card_prints.flavor_name),
                    flavor_text = COALESCE(EXCLUDED.flavor_text, card_prints.flavor_text),
                    finishes = EXCLUDED.finishes,
                    image_small = EXCLUDED.image_small,
                    image_normal = EXCLUDED.image_normal,
                    image_large = EXCLUDED.image_large,
                    image_png = EXCLUDED.image_png,
                    image_art_crop = EXCLUDED.image_art_crop,
                    image_border_crop = EXCLUDED.image_border_crop,
                    card_faces = EXCLUDED.card_faces,
                    image_set_code = EXCLUDED.image_set_code,
                    image_set_name = EXCLUDED.image_set_name,
                    image_collector_number = EXCLUDED.image_collector_number
                """,
                batch,
            )
            conn.commit()


def insert_abilities(conn, abilities: dict[str, str], skip_summary: bool = False, on_progress=None):
    """Insert keyword abilities with DeepSeek-generated summaries.

    Uses incremental checkpointing: each ability is summarized and inserted
    immediately, so progress is preserved if the process crashes.

    Args:
        abilities: {name: raw_description} from rules file
        skip_summary: if True, use raw descriptions directly (for testing)
        on_progress: callback(done, total) for summarization progress
    """
    log(f"Processing {len(abilities)} keyword abilities...")
    total = len(abilities)

    if skip_summary:
        # Fast path: insert all at once without summarization
        log(f"Inserting {total} keyword abilities (no summarization)...")
        with conn.cursor() as cur:
            values = [
                (name.lower().replace(" ", "_"), name, desc)
                for name, desc in abilities.items()
            ]
            cur.executemany(
                """INSERT INTO keyword_abilities (id, name, description) VALUES (%s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET
                       description = EXCLUDED.description,
                       embedding = CASE WHEN keyword_abilities.description IS NOT DISTINCT FROM EXCLUDED.description
                                        THEN keyword_abilities.embedding ELSE NULL END""",
                values,
            )
        conn.commit()
        log("Abilities inserted.")
        return

    from app.ability_summarizer import summarize_ability

    log("Generating concise summaries with DeepSeek (checkpointed)...")
    processed = 0
    for name, desc in abilities.items():
        ability_id = name.lower().replace(" ", "_")

        # Check existing state to decide whether to skip summarization
        with conn.cursor() as cur:
            cur.execute(
                "SELECT description, embedding FROM keyword_abilities WHERE id = %s",
                (ability_id,),
            )
            row = cur.fetchone()
            if row:
                existing_desc, existing_emb = row
                # Skip summarization if:
                # 1. Has non-NULL embedding (fully processed)
                # 2. Has description that differs from raw (already summarized)
                if existing_emb is not None:
                    processed += 1
                    if on_progress:
                        on_progress(processed, total)
                    continue
                # If description is already different from raw, it's a summary - skip API call
                if existing_desc != desc:
                    processed += 1
                    if on_progress:
                        on_progress(processed, total)
                    continue

        # Generate summary for new or not-yet-summarized ability
        summary = summarize_ability(name, desc)
        if summary is None:
            summary = desc[:200] if len(desc) > 200 else desc
            log(f"  [{processed + 1}/{total}] {name}: using fallback")

        # Insert immediately (checkpoint)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO keyword_abilities (id, name, description) VALUES (%s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET
                       description = EXCLUDED.description,
                       embedding = CASE WHEN keyword_abilities.description IS NOT DISTINCT FROM EXCLUDED.description
                                        THEN keyword_abilities.embedding ELSE NULL END""",
                (ability_id, name, summary),
            )
        conn.commit()
        processed += 1
        log(f"  [{processed}/{total}] {name}: {summary[:50]}...")
        if on_progress:
            on_progress(processed, total)

    log(f"Abilities processed: {processed}/{total}")


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


def generate_ability_embeddings(conn, batch_size: int = 50, max_rounds: int = 10, on_progress=None):
    """Generate and store embeddings for keyword abilities with checkpointing.

    Processes in batches and commits after each batch, so progress is preserved
    if the process crashes.

    on_progress: optional callback(done, total) called after each batch.
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
        processed_this_round = 0

        for i in range(0, total, batch_size):
            batch = rows[i:i + batch_size]
            texts = [f"{r[1]}: {r[2]}" for r in batch]
            vecs = encode_batch_safe(texts)

            if vecs is None:
                log(f"  Batch {i//batch_size + 1} failed, skipping...")
                continue

            with conn.cursor() as cur:
                for j, row in enumerate(batch):
                    cur.execute(
                        "UPDATE keyword_abilities SET embedding = %s::halfvec WHERE id = %s",
                        (str(vecs[j]), row[0]),
                    )
            conn.commit()
            processed_this_round += len(batch)
            done = i + len(batch)
            log(f"  [{done}/{total}] Embedded {len(batch)} abilities")
            if on_progress:
                on_progress(done, total)

        if processed_this_round == total:
            log("All ability embeddings complete.")
            return

        log(f"Round {round_num} done. {total - processed_this_round} abilities failed, retrying...")
        time.sleep(10)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM keyword_abilities WHERE embedding IS NULL")
        remaining = cur.fetchone()[0]
    if remaining > 0:
        log(f"WARNING: {remaining} abilities still missing embeddings after {max_rounds} rounds.")
    else:
        log("All ability embeddings complete.")


def generate_effect_embeddings(conn, batch_size: int = 200, max_rounds: int = 10, on_progress=None):
    """Generate embeddings for effect-level card text chunks."""
    from app.embedding import encode_batch_safe

    for round_num in range(1, max_rounds + 1):
        with conn.cursor() as cur:
            cur.execute("SELECT id, effect_text FROM card_effects WHERE embedding IS NULL")
            rows = cur.fetchall()

        if not rows:
            log("All effect chunk embeddings complete.")
            return

        total = len(rows)
        failed = 0
        log(f"Generating effect chunk embeddings (round {round_num}/{max_rounds}): {total} remaining...")

        for i in range(0, total, batch_size):
            batch = rows[i:i + batch_size]
            texts = [r[1] or "" for r in batch]
            t0 = time.time()
            vecs = encode_batch_safe(texts)

            if vecs is None:
                failed += len(batch)
                log(f"  [{min(i + batch_size, total)}/{total}] SKIPPED {len(batch)} chunks (API error)")
                continue

            with conn.cursor() as cur:
                for j, row in enumerate(batch):
                    cur.execute(
                        "UPDATE card_effects SET embedding = %s::halfvec WHERE id = %s",
                        (str(vecs[j]), row[0]),
                    )
            conn.commit()

            done = min(i + batch_size, total)
            elapsed = time.time() - t0
            log(f"  [{done}/{total}] Embedded {len(batch)} effect chunks ({elapsed:.1f}s)")
            if on_progress:
                on_progress(done, total)

        if failed == 0:
            return
        log(f"Round {round_num} done. {failed} chunks failed, will retry...")
        time.sleep(10)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM card_effects WHERE embedding IS NULL")
        remaining = cur.fetchone()[0]
    if remaining > 0:
        log(f"WARNING: {remaining} effect chunks still missing embeddings after {max_rounds} rounds.")
    else:
        log("All effect chunk embeddings complete.")


def create_vector_indexes(conn):
    """Skipped – halfvec columns are searched via sequential scan."""
    log("Skipping vector index creation (halfvec sequential scan).")


def main():
    """Run seed process.

    Downloads bulk data to local file once, then streams and processes in chunks.
    """
    t_start = time.time()

    conn = get_conn()
    try:
        create_schema(conn)

        # Download and insert all_cards prints
        insert_cards_and_prints(conn)

        # Parse and insert abilities (with DeepSeek summarization)
        abilities = parse_keyword_abilities(KEYWORD_ABILITY_FILE)
        insert_abilities(conn, abilities, on_progress=lambda done, total: log(f"  Summarized {done}/{total} abilities"))

        # Generate embeddings
        generate_card_embeddings(conn)
        generate_effect_embeddings(conn)
        generate_ability_embeddings(conn)

        # Create vector indexes
        create_vector_indexes(conn)

    finally:
        conn.close()

    log(f"\nSeed complete! Total time: {time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
