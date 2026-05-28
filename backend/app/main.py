import logging
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_allowed_origins, get_log_level
from .routes_api import api_router
from .routes_admin import admin_router
from .routes_auth import auth_router
from .routes_decks import deck_router, shared_deck_router
from .routes_search import search_router
from .startup import get_startup_state, lifespan


class HealthCheckAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not self._is_suppressible_health_check(record)

    @staticmethod
    def _is_suppressible_health_check(record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 5:
            method = str(args[1]).upper()
            path = str(args[2]).split("?", 1)[0]
            try:
                status_code = int(str(args[4]).split()[0])
            except (TypeError, ValueError):
                status_code = None
            if method == "GET" and path == "/api/health" and status_code == 200:
                return True

        return bool(re.search(r'"GET\s+/api/health(?:\?[^ ]*)?\s+HTTP/[^"]+"\s+200\b', record.getMessage()))


def configure_logging() -> None:
    level_name = get_log_level()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger().setLevel(level)
    logging.getLogger("app").setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)


configure_logging()
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
app.include_router(api_router)
app.include_router(deck_router)
app.include_router(shared_deck_router)
app.include_router(admin_router)
app.include_router(search_router)


@app.middleware("http")
async def require_initialized_backend(request: Request, call_next):
    startup_state = get_startup_state()
    if request.url.path != "/api/health" and request.url.path.startswith("/api/"):
        if startup_state["status"] == "initializing":
            return JSONResponse(status_code=503, content=startup_state)
        if startup_state["status"] == "error":
            return JSONResponse(status_code=503, content=startup_state)
    return await call_next(request)


@app.get("/api/health")
async def health():
    startup_state = get_startup_state()
    if startup_state["status"] != "ok":
        return JSONResponse(status_code=503, content=startup_state)
    return {"status": "ok"}
