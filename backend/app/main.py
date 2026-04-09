import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import run_search
from .db import close_pool, discover_cards, get_pool
from .decks import admin_router, auth_router, deck_router

logger = logging.getLogger(__name__)


async def _ensure_admin(pool):
    """Create the built-in admin account from env vars if it doesn't exist."""
    import os
    admin_user = os.getenv("ADMIN_USERNAME")
    admin_pass = os.getenv("ADMIN_PASSWORD")
    if not admin_user or not admin_pass:
        return
    from .auth import hash_password
    row = await pool.fetchrow("SELECT id FROM users WHERE username = $1", admin_user)
    if row:
        await pool.execute("UPDATE users SET role = 'admin' WHERE username = $1", admin_user)
        return
    pw_hash = hash_password(admin_pass)
    await pool.execute(
        "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, 'admin')",
        admin_user, pw_hash,
    )
    logger.info("Built-in admin account '%s' created.", admin_user)


async def _ensure_data(pool):
    """Check if card data exists; if not, run the seed script."""
    try:
        count = await pool.fetchval("SELECT COUNT(*) FROM cards")
    except Exception:
        count = 0

    if count > 0:
        logger.info("Database has %d cards, skipping seed.", count)
    else:
        logger.info("No card data found. Running seed script...")
        from scripts.seed_pg import main as seed_main
        await asyncio.to_thread(seed_main)
        logger.info("Seed complete.")

    # Backfill any missing embeddings
    await _backfill_embeddings(pool)


async def _backfill_embeddings(pool):
    """Check for cards/abilities with missing embeddings and fill them."""
    card_count = await pool.fetchval(
        "SELECT COUNT(*) FROM cards WHERE name_embedding IS NULL"
    )
    ability_count = await pool.fetchval(
        "SELECT COUNT(*) FROM keyword_abilities WHERE embedding IS NULL"
    )

    if card_count == 0 and ability_count == 0:
        logger.info("All embeddings present, nothing to backfill.")
        return

    logger.info("Backfilling embeddings: %d cards, %d abilities missing.", card_count, ability_count)

    def _do_backfill():
        from scripts.seed_pg import generate_card_embeddings, generate_ability_embeddings, get_conn
        conn = get_conn()
        try:
            if card_count > 0:
                generate_card_embeddings(conn)
            if ability_count > 0:
                generate_ability_embeddings(conn)
        finally:
            conn.close()

    await asyncio.to_thread(_do_backfill)
    logger.info("Embedding backfill complete.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await get_pool()
    # Ensure user/deck tables exist (idempotent)
    # Create user/deck tables that don't depend on cards
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'user',
                created_at    TIMESTAMPTZ DEFAULT now()
            );
            ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'user';
            CREATE TABLE IF NOT EXISTS decks (
                id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name       TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_decks_user_id ON decks(user_id);
        """)
    # Ensure built-in admin exists
    await _ensure_admin(pool)
    # Add is_playtest column to existing cards table (idempotent migration)
    async with pool.acquire() as conn:
        await conn.execute("""
            ALTER TABLE cards ADD COLUMN IF NOT EXISTS is_playtest BOOLEAN NOT NULL DEFAULT FALSE;
        """)
        # Backfill from JSONB for existing rows
        await conn.execute("""
            UPDATE cards SET is_playtest = (data->>'set_type' = 'funny')
            WHERE is_playtest = FALSE AND data->>'set_type' = 'funny'
        """)
    # Seed cards first so the FK reference works
    await _ensure_data(pool)
    # Now create deck_cards which references cards(id)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS deck_cards (
                id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                deck_id  UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                card_id  TEXT NOT NULL REFERENCES cards(id),
                quantity INT NOT NULL DEFAULT 1,
                image_url TEXT,
                added_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE(deck_id, card_id)
            );
            ALTER TABLE deck_cards ADD COLUMN IF NOT EXISTS image_url TEXT;
            ALTER TABLE deck_cards ADD COLUMN IF NOT EXISTS display_url TEXT;
            CREATE INDEX IF NOT EXISTS idx_deck_cards_deck_id ON deck_cards(deck_id);
        """)
    yield
    await close_pool()


app = FastAPI(title="MTG AI Card Search", lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(deck_router)
app.include_router(admin_router)


class SearchRequest(BaseModel):
    query: str


class SearchResponse(BaseModel):
    results: list[dict]


@app.post("/api/search", response_model=SearchResponse)
async def search_cards(request: SearchRequest):
    results = await run_search(request.query)
    return SearchResponse(results=results)


class DiscoverRequest(BaseModel):
    q: str = ""
    colors: list[str] | None = None
    types: list[str] | None = None
    rarities: list[str] | None = None
    keywords: list[str] | None = None
    subtypes: list[str] | None = None
    include_playtest: bool = False
    cmc_min: float | None = None
    cmc_max: float | None = None
    power_min: float | None = None
    power_max: float | None = None
    toughness_min: float | None = None
    toughness_max: float | None = None
    page: int = 1
    page_size: int = 60


@app.post("/api/discover")
async def discover(request: DiscoverRequest):
    result = await discover_cards(
        q=request.q,
        colors=request.colors,
        types=request.types,
        rarities=request.rarities,
        keywords=request.keywords,
        subtypes=request.subtypes,
        include_playtest=request.include_playtest,
        cmc_min=request.cmc_min,
        cmc_max=request.cmc_max,
        power_min=request.power_min,
        power_max=request.power_max,
        toughness_min=request.toughness_min,
        toughness_max=request.toughness_max,
        page=request.page,
        page_size=request.page_size,
    )
    return result


@app.get("/api/health")
async def health():
    return {"status": "ok"}
