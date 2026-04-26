"""Search and discovery HTTP endpoints."""

from fastapi import APIRouter, Depends, Request

from .agent import SEARCH_RESULT_LIMIT
from .dependencies import get_optional_user
from .schemas.search import DiscoverRequest, SearchRequest, SearchResponse
from .services.search_service import (
    discover as discover_service,
    get_client_ip,
    list_card_prints as list_card_prints_service,
    list_keywords as list_keywords_service,
    search_cards as search_cards_service,
)

search_router = APIRouter(tags=["search"])


@search_router.post("/api/search", response_model=SearchResponse)
async def search_cards(
    request: SearchRequest,
    raw_request: Request,
    user_id: str | None = Depends(get_optional_user),
):
    client_ip = get_client_ip(raw_request)
    results = await search_cards_service(
        request.query,
        client_ip,
        user_id,
    )
    return SearchResponse(
        results=results[:SEARCH_RESULT_LIMIT]
    )


@search_router.post("/api/discover")
async def discover(request: DiscoverRequest):
    return await discover_service(request)


@search_router.get("/api/keywords")
async def list_keywords():
    """Return all keyword abilities from the database."""
    return await list_keywords_service()


@search_router.get("/api/cards/{oracle_id}/prints")
async def get_card_prints(oracle_id: str):
    """Return all print versions for a card from the local database."""
    return await list_card_prints_service(oracle_id)
