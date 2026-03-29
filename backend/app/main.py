import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import run_search
from .db import close_pool, get_pool

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
