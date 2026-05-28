import logging
import os
import time

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/embeddings"
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-4B"
MAX_BATCH_SIZE = 64
MAX_RETRIES = 3

_RETRIABLE = (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError, httpx.HTTPStatusError)


def _call_api_batch(batch: list[str]) -> list[list[float]] | None:
    """Call API for a single batch. Returns None on persistent failure."""
    if not SILICONFLOW_API_KEY:
        raise RuntimeError("SILICONFLOW_API_KEY is not configured")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = httpx.post(
                SILICONFLOW_API_URL,
                headers={
                    "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={"model": EMBEDDING_MODEL, "input": batch},
                timeout=300,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            data.sort(key=lambda x: x["index"])
            return [item["embedding"] for item in data]
        except _RETRIABLE as e:
            if attempt == MAX_RETRIES:
                logger.error("Embedding API failed after %d attempts: %s", MAX_RETRIES, e)
                return None
            wait = attempt * 5
            logger.warning("Embedding API error (attempt %d/%d), retrying in %ds: %s", attempt, MAX_RETRIES, wait, e)
            time.sleep(wait)
    return None


def encode_queries(texts: list[str]) -> list[list[float]]:
    """Encode queries into embedding vectors."""
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), MAX_BATCH_SIZE):
        batch = texts[i : i + MAX_BATCH_SIZE]
        result = _call_api_batch(batch)
        if result is None:
            raise RuntimeError(f"Failed to embed batch at offset {i}")
        all_embeddings.extend(result)
    return all_embeddings


def encode_batch_or_none(texts: list[str]) -> list[list[float]] | None:
    """Encode a batch, returning None on failure instead of raising."""
    return _call_api_batch(texts)
