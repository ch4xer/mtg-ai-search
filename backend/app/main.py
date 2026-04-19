import asyncio

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import run_search
from .config import get_allowed_origins, get_rate_limits
from .db import (
    discover_cards,
    get_all_keywords,
    get_ip_hourly_search_count,
    get_user_by_id,
    get_user_hourly_search_count,
    log_search,
)
from .dependencies import get_optional_user
from .routes_admin import admin_router
from .routes_auth import auth_router
from .routes_decks import deck_router, shared_deck_router
from .startup import lifespan


app = FastAPI(title="MTG AI Card Search", lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(deck_router)
app.include_router(shared_deck_router)
app.include_router(admin_router)


class SearchRequest(BaseModel):
    query: str


class SearchResponse(BaseModel):
    results: list[dict]


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind a reverse proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.post("/api/search", response_model=SearchResponse)
async def search_cards(
    request: SearchRequest,
    raw_request: Request,
    user_id: str | None = Depends(get_optional_user),
):
    client_ip = _get_client_ip(raw_request)

    limits = get_rate_limits()
    anon_limit = limits["anon_hourly"]
    user_limit = limits["user_hourly"]

    if user_id:
        # Registered user (admin exempt)
        user = await get_user_by_id(user_id)
        if not user or user.get("role") != "admin":
            count = await get_user_hourly_search_count(user_id)
            if count >= user_limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"搜索次数已达上限 ({user_limit}次/小时)",
                )
    else:
        # Anonymous user by IP
        count = await get_ip_hourly_search_count(client_ip)
        if count >= anon_limit:
            raise HTTPException(
                status_code=429,
                detail=f"未登录用户搜索次数已达上限 ({anon_limit}次/小时)，请登录后使用",
            )

    search_result = await run_search(request.query)
    # Log search asynchronously — don't block the response
    asyncio.create_task(
        log_search(
            user_id,
            request.query,
            search_result["tokens_prompt"],
            search_result["tokens_completion"],
            ip_address=client_ip,
        )
    )
    return SearchResponse(results=search_result["ranked_results"])


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


@app.get("/api/keywords")
async def list_keywords():
    """Return all keyword abilities from the database."""
    keywords = await get_all_keywords()
    return {"keywords": keywords}


@app.get("/api/health")
async def health():
    return {"status": "ok"}
