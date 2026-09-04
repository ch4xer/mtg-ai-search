from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=60, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    search_id: str | None = None


class SearchResponse(BaseModel):
    search_id: str | None = None
    results: list[dict]
    total: int | None = None
    limit: int | None = None
    offset: int = 0
    has_more: bool = False


class RandomCardResponse(BaseModel):
    card: dict


class FunctionTagInfo(BaseModel):
    tag: str
    label: str


class CardFunctionTagsResponse(BaseModel):
    card_id: str
    card_name: str
    tags: list[FunctionTagInfo]


class ApiAiSearchRequest(BaseModel):
    api_key: str
    query: str
    limit: int = Field(default=10, ge=1, le=50)


class CardFilterRequest(BaseModel):
    colors: list[str] | None = None
    types: list[str] | None = None
    rarities: list[str] | None = None
    set_codes: list[str] | None = None
    keywords: list[str] | None = None
    subtypes: list[str] | None = None
    function_tags: list[str] | None = None
    exclude_card_id: str | None = None
    include_playtest: bool = False
    cmc_min: float | None = None
    cmc_max: float | None = None
    power_min: float | None = None
    power_max: float | None = None
    toughness_min: float | None = None
    toughness_max: float | None = None


class ApiExactMatchRequest(CardFilterRequest):
    api_key: str
    query: str = ""
    limit: int = Field(default=10, ge=1, le=100)


class DiscoverRequest(CardFilterRequest):
    q: str = ""
    page: int = 1
    page_size: int = 60
