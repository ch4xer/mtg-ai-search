"""Search and discovery HTTP endpoints."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request

from .dependencies import get_optional_user
from .schemas.search import (
    DiscoverRequest,
    SearchRequest,
    SearchResponse,
    TagSearchRequest,
    TagSearchResponse,
)
from .services.search_service import (
    discover as discover_service,
    get_client_ip,
    list_card_prints as list_card_prints_service,
    list_keywords as list_keywords_service,
    search_cards_result as search_cards_service,
)
from .services.tag_search_service import search_tags as search_tags_service

search_router = APIRouter(tags=["search"])
logger = logging.getLogger(__name__)


@search_router.post("/api/search", response_model=SearchResponse)
async def search_cards(
    request: SearchRequest,
    raw_request: Request,
    user_id: str | None = Depends(get_optional_user),
):
    started = time.perf_counter()
    client_ip = get_client_ip(raw_request)
    logger.debug(
        ">>> /api/search query=%r limit=%d offset=%d search_id=%s user=%s ip=%s",
        request.query,
        request.limit,
        request.offset,
        request.search_id or "-",
        user_id or "anonymous",
        client_ip,
    )
    results = await search_cards_service(
        request.query,
        client_ip,
        user_id,
        card_limit=request.limit,
        card_offset=request.offset,
        search_id=request.search_id,
        include_zh=request.include_zh,
    )
    logger.debug(
        "<<< /api/search returned %d cards in %.2fs",
        len(results["results"]),
        time.perf_counter() - started,
    )
    return SearchResponse(**results)


@search_router.post("/api/tag-search", response_model=TagSearchResponse)
async def tag_search(request: TagSearchRequest):
    try:
        return await search_tags_service(request.query, request.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
