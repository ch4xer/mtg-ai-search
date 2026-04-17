"""Idempotent schema migrations.

All statements here must be safe to run on every startup. Prefer
`CREATE TABLE IF NOT EXISTS` and `ADD COLUMN IF NOT EXISTS` forms.

This is the single source of truth for the app's runtime schema. The
`scripts/seed_pg.py` bulk loader creates the same tables from scratch
for fresh databases; any column added here should also be added to
the CREATE TABLE statements there to keep the two in sync.
"""

import logging

import asyncpg

logger = logging.getLogger(__name__)


# Tables that do not reference cards(id) and can be created before seeding.
_PRE_SEED_DDL = """
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'user',
    created_at    TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';
ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_code_expires_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_attempts INT NOT NULL DEFAULT 0;
-- Existing users (no email) are treated as verified
UPDATE users SET email_verified = TRUE WHERE email IS NULL AND email_verified = FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS decks (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    format     TEXT NOT NULL DEFAULT 'undefined',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE decks ADD COLUMN IF NOT EXISTS format TEXT NOT NULL DEFAULT 'undefined';

CREATE TABLE IF NOT EXISTS search_logs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    query         TEXT NOT NULL,
    tokens_prompt INT NOT NULL DEFAULT 0,
    tokens_completion INT NOT NULL DEFAULT 0,
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

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_decks_user_id ON decks(user_id);
ALTER TABLE search_logs ADD COLUMN IF NOT EXISTS ip_address TEXT;
CREATE INDEX IF NOT EXISTS idx_search_logs_user_id ON search_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_search_logs_ip_address ON search_logs(ip_address);
"""

# Migrations for the cards table (added after it has been seeded).
_CARDS_DDL = """
ALTER TABLE cards ADD COLUMN IF NOT EXISTS is_playtest BOOLEAN NOT NULL DEFAULT FALSE;
UPDATE cards SET is_playtest = (data->>'set_type' = 'funny')
WHERE is_playtest = FALSE AND data->>'set_type' = 'funny';
"""

# Tables that depend on cards(id) existing. Run after seeding.
_POST_SEED_DDL = """
CREATE TABLE IF NOT EXISTS deck_cards (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deck_id    UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_id    TEXT NOT NULL REFERENCES cards(id),
    quantity   INT NOT NULL DEFAULT 1,
    image_url  TEXT,
    display_url TEXT,
    added_at   TIMESTAMPTZ DEFAULT now(),
    UNIQUE(deck_id, card_id)
);
ALTER TABLE deck_cards ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE deck_cards ADD COLUMN IF NOT EXISTS display_url TEXT;
ALTER TABLE deck_cards ADD COLUMN IF NOT EXISTS board TEXT NOT NULL DEFAULT 'mainboard';
CREATE INDEX IF NOT EXISTS idx_deck_cards_deck_id ON deck_cards(deck_id);

-- Migrate unique constraint from (deck_id, card_id) to (deck_id, card_id, board)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'deck_cards_deck_id_card_id_key'
    ) THEN
        ALTER TABLE deck_cards DROP CONSTRAINT deck_cards_deck_id_card_id_key;
    END IF;
END $$;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'deck_cards_deck_id_card_id_board_key'
    ) THEN
        ALTER TABLE deck_cards ADD CONSTRAINT deck_cards_deck_id_card_id_board_key
            UNIQUE (deck_id, card_id, board);
    END IF;
END $$;
"""


async def run_pre_seed(pool: asyncpg.Pool) -> None:
    """Run migrations that must exist before card data is loaded."""
    async with pool.acquire() as conn:
        await conn.execute(_PRE_SEED_DDL)
    logger.info("Pre-seed migrations applied.")


async def run_cards_migrations(pool: asyncpg.Pool) -> None:
    """Run idempotent migrations against the cards table."""
    async with pool.acquire() as conn:
        await conn.execute(_CARDS_DDL)
    logger.info("Cards-table migrations applied.")


async def run_post_seed(pool: asyncpg.Pool) -> None:
    """Run migrations that depend on cards(id) existing."""
    async with pool.acquire() as conn:
        await conn.execute(_POST_SEED_DDL)
    logger.info("Post-seed migrations applied.")
