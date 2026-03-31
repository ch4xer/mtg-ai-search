import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import run_search
from .db import close_pool, get_pool
from .decks import auth_router, deck_router

logger = logging.getLogger(__name__)


async def _ensure_data(pool):
    """Check if card data exists; if not, run the seed script."""
    try:
        count = await pool.fetchval("SELECT COUNT(*) FROM cards")
    except Exception:
        count = 0

    if count > 0:
        logger.info("Database has %d cards, skipping seed.", count)
        return

    logger.info("No card data found. Running seed script...")
    from scripts.seed_pg import main as seed_main
    await asyncio.to_thread(seed_main)
    logger.info("Seed complete.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await get_pool()
    # Ensure user/deck tables exist (idempotent)
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TIMESTAMPTZ DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS decks (
                id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name       TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS deck_cards (
                id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                deck_id  UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                card_id  TEXT NOT NULL REFERENCES cards(id),
                quantity INT NOT NULL DEFAULT 1,
                added_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE(deck_id, card_id)
            );
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_decks_user_id ON decks(user_id);
            CREATE INDEX IF NOT EXISTS idx_deck_cards_deck_id ON deck_cards(deck_id);
        """)
    await _ensure_data(pool)
    yield
    await close_pool()


app = FastAPI(title="MTG AI Card Search", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(deck_router)


class SearchRequest(BaseModel):
    query: str


class SearchResponse(BaseModel):
    results: list[dict]


@app.post("/api/search", response_model=SearchResponse)
async def search_cards(request: SearchRequest):
    results = await run_search(request.query)
    return SearchResponse(results=results)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
