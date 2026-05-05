"""Runtime schema bootstrap for fresh databases.

This module intentionally defines the current schema directly. Historical
upgrade/backfill migrations are not kept here because the supported reset path
is to recreate the database and initialize it from the current bulk data.
"""

import logging

import asyncpg

logger = logging.getLogger(__name__)


# Tables that do not reference cards(id) and can be created before seeding.
_PRE_SEED_DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

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
    api_key_hash TEXT,
    api_key_created_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE users ADD COLUMN IF NOT EXISTS api_key_hash TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS api_key_created_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS decks (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    format     TEXT NOT NULL DEFAULT 'undefined',
    analysis_data JSONB,
    analysis_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS search_logs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    query         TEXT NOT NULL,
    tokens_prompt INT NOT NULL DEFAULT 0,
    tokens_completion INT NOT NULL DEFAULT 0,
    ip_address    TEXT,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_logs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status       TEXT NOT NULL DEFAULT 'running',
    new_cards    INT NOT NULL DEFAULT 0,
    updated_cards INT NOT NULL DEFAULT 0,
    message      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sync_logs_started_at ON sync_logs(started_at DESC);

CREATE TABLE IF NOT EXISTS tag_sync_state (
    source_url      TEXT PRIMARY KEY,
    etag            TEXT,
    content_hash    TEXT,
    checked_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ,
    total_tags      INT NOT NULL DEFAULT 0,
    art_tags        INT NOT NULL DEFAULT 0,
    function_tags   INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tagger_tags (
    tag             TEXT NOT NULL,
    tag_type        TEXT NOT NULL CHECK (tag_type IN ('art', 'function')),
    label           TEXT NOT NULL,
    normalized      TEXT NOT NULL,
    aliases         JSONB NOT NULL DEFAULT '[]'::jsonb,
    retrieval_phrases JSONB NOT NULL DEFAULT '[]'::jsonb,
    description     TEXT NOT NULL DEFAULT '',
    embedding_text  TEXT NOT NULL DEFAULT '',
    expansion_generated_at TIMESTAMPTZ,
    expansion_source TEXT,
    expansion_model TEXT,
    expansion_version INT NOT NULL DEFAULT 1,
    embedding        halfvec(2560),
    content_hash    TEXT NOT NULL,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_at      TIMESTAMPTZ,
    PRIMARY KEY (tag_type, tag)
);
CREATE INDEX IF NOT EXISTS idx_tagger_tags_type ON tagger_tags(tag_type) WHERE removed_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_tagger_tags_normalized ON tagger_tags(normalized) WHERE removed_at IS NULL;
ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS embedding halfvec(2560);
ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS expansion_generated_at TIMESTAMPTZ;
ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS expansion_source TEXT;
ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS expansion_model TEXT;
ALTER TABLE tagger_tags ADD COLUMN IF NOT EXISTS expansion_version INT NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_tagger_tags_missing_expansion
ON tagger_tags(tag_type, tag)
WHERE removed_at IS NULL AND tag_type = 'function' AND expansion_generated_at IS NULL;
UPDATE tagger_tags
SET expansion_generated_at = COALESCE(updated_at, now()),
    expansion_source = COALESCE(expansion_source, 'legacy'),
    expansion_version = COALESCE(expansion_version, 1)
WHERE removed_at IS NULL
  AND tag_type = 'function'
  AND expansion_generated_at IS NULL
  AND embedding_text <> ''
  AND (
      jsonb_array_length(COALESCE(aliases, '[]'::jsonb)) > 0
      OR jsonb_array_length(COALESCE(retrieval_phrases, '[]'::jsonb)) > 0
      OR COALESCE(description, '') <> ''
  );
UPDATE tagger_tags
SET embedding = NULL
WHERE removed_at IS NULL
  AND tag_type = 'function'
  AND expansion_generated_at IS NULL
  AND embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_api_key_hash ON users(api_key_hash) WHERE api_key_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_decks_user_id ON decks(user_id);
CREATE INDEX IF NOT EXISTS idx_search_logs_user_id ON search_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_search_logs_ip_address ON search_logs(ip_address);
"""

# Tables that depend on cards(id) existing. Run after seeding.
_POST_SEED_DDL = """
CREATE TABLE IF NOT EXISTS card_effects (
    id           TEXT PRIMARY KEY,
    card_id      TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    face_index   INT NOT NULL DEFAULT 0,
    chunk_index  INT NOT NULL,
    effect_text  TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT 'oracle_text',
    embedding    halfvec(2560),
    UNIQUE(card_id, face_index, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_card_effects_card_id ON card_effects(card_id);
ALTER TABLE card_prints DROP CONSTRAINT IF EXISTS card_prints_card_id_set_code_collector_num_key;
CREATE INDEX IF NOT EXISTS idx_cards_is_unofficial ON cards(is_unofficial);

CREATE TABLE IF NOT EXISTS card_tagger_tags (
    tag_type           TEXT NOT NULL CHECK (tag_type IN ('art', 'function')),
    tag                TEXT NOT NULL,
    card_id            TEXT NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
    source_scryfall_id TEXT,
    synced_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tag_type, tag, card_id),
    FOREIGN KEY (tag_type, tag) REFERENCES tagger_tags(tag_type, tag) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_card_tagger_tags_card_id ON card_tagger_tags(card_id);
CREATE INDEX IF NOT EXISTS idx_card_tagger_tags_tag ON card_tagger_tags(tag_type, tag);

CREATE TABLE IF NOT EXISTS tag_card_sync_state (
    tag_type           TEXT NOT NULL CHECK (tag_type IN ('art', 'function')),
    tag                TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'idle',
    api_card_count     INT NOT NULL DEFAULT 0,
    linked_card_count  INT NOT NULL DEFAULT 0,
    missing_card_count INT NOT NULL DEFAULT 0,
    last_error         TEXT NOT NULL DEFAULT '',
    synced_at          TIMESTAMPTZ,
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tag_type, tag),
    FOREIGN KEY (tag_type, tag) REFERENCES tagger_tags(tag_type, tag) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tag_card_sync_state_status ON tag_card_sync_state(status);

UPDATE cards c
SET is_unofficial = TRUE
WHERE EXISTS (
    SELECT 1 FROM card_prints cp
    WHERE cp.card_id = c.id
      AND cp.set_type = 'minigame'
)
AND NOT EXISTS (
    SELECT 1 FROM card_prints cp
    WHERE cp.card_id = c.id
      AND cp.set_type IS DISTINCT FROM 'minigame'
);

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
);
CREATE INDEX IF NOT EXISTS idx_deck_cards_deck_id ON deck_cards(deck_id);
"""


async def run_pre_seed(pool: asyncpg.Pool) -> None:
    """Run migrations that must exist before card data is loaded."""
    async with pool.acquire() as conn:
        await conn.execute(_PRE_SEED_DDL)
    logger.info("Pre-seed migrations applied.")


async def run_post_seed(pool: asyncpg.Pool) -> None:
    """Run migrations that depend on cards(id) existing."""
    async with pool.acquire() as conn:
        await conn.execute(_POST_SEED_DDL)
    logger.info("Post-seed migrations applied.")
