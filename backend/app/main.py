from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import run_search
from .db import close_pool, get_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
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
