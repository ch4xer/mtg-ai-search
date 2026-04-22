import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_allowed_origins
from .dependencies import get_optional_user
from .routes_admin import admin_router
from .routes_auth import auth_router
from .routes_decks import deck_router, shared_deck_router
from .schemas.search import DiscoverRequest, SearchRequest, SearchResponse
from .services.search_service import (
    discover as discover_service,
    get_client_ip,
    list_card_prints as list_card_prints_service,
    list_keywords as list_keywords_service,
    search_cards as search_cards_service,
)
from .startup import get_startup_state, lifespan


class HealthCheckAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:
            method = args[1]
            path = args[2]
            status_code = args[4]
            return not (method == "GET" and path == "/api/health" and status_code in (200, 503))
        return "/api/health" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(HealthCheckAccessFilter())

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


@app.middleware("http")
async def require_initialized_backend(request: Request, call_next):
    startup_state = get_startup_state()
    if request.url.path != "/api/health" and request.url.path.startswith("/api/"):
        if startup_state["status"] == "initializing":
            return JSONResponse(status_code=503, content=startup_state)
        if startup_state["status"] == "error":
            return JSONResponse(status_code=503, content=startup_state)
    return await call_next(request)


@app.post("/api/search", response_model=SearchResponse)
async def search_cards(
    request: SearchRequest,
    raw_request: Request,
    user_id: str | None = Depends(get_optional_user),
):
    client_ip = get_client_ip(raw_request)
    return SearchResponse(
        results=await search_cards_service(
            request.query,
            client_ip,
            user_id,
            rerank_enabled=request.rerank_enabled,
            rerank_top_n=request.rerank_top_n,
        )
    )


@app.post("/api/discover")
async def discover(request: DiscoverRequest):
    return await discover_service(request)


@app.get("/api/keywords")
async def list_keywords():
    """Return all keyword abilities from the database."""
    return await list_keywords_service()


@app.get("/api/cards/{oracle_id}/prints")
async def get_card_prints(oracle_id: str):
    """Return all print versions for a card from the local database."""
    return await list_card_prints_service(oracle_id)


@app.get("/api/health")
async def health():
    startup_state = get_startup_state()
    if startup_state["status"] != "ok":
        return JSONResponse(status_code=503, content=startup_state)
    return {"status": "ok"}
