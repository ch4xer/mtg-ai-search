"""API-key based external search endpoints."""

from fastapi import APIRouter, Request

from .schemas.search import ApiAiSearchRequest, ApiExactMatchRequest, SearchResponse
from .services.api_key_service import authenticate_api_key
from .services.search_service import discover_exact_match, get_client_ip, search_cards

api_router = APIRouter(prefix="/api/external", tags=["external-api"])


@api_router.post("/ai-search", response_model=SearchResponse)
async def external_ai_search(req: ApiAiSearchRequest, raw_request: Request):
    user = await authenticate_api_key(req.api_key)
    results = await search_cards(
        req.query,
        get_client_ip(raw_request),
        user["id"],
        card_limit=req.limit,
    )
    return SearchResponse(results=results)


@api_router.post("/exact-match", response_model=SearchResponse)
async def external_exact_match(req: ApiExactMatchRequest):
    await authenticate_api_key(req.api_key)
    filters = req.model_dump(exclude={"api_key", "query", "limit"})
    result = await discover_exact_match(req.query, req.limit, **filters)
    return SearchResponse(results=result["results"])
