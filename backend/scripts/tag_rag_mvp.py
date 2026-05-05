"""Minimal no-database Tagger RAG proof of concept.

Fetches a small number of functional Scryfall Tagger tags, asks DeepSeek to
generate English retrieval text using sample cards, embeds that text, and writes
everything to a local JSON file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.embedding import encode_batch_safe
from app.services.tag_search_service import (
    _fetch_sample_cards_for_tag,
    _generate_expansion_batch,
    _TaggerTagHTMLParser,
    TAGGER_TAGS_URL,
    SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS,
)

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a tiny no-DB functional-tag RAG sample.")
    parser.add_argument("--limit", type=int, default=20, help="Number of functional tags to process.")
    parser.add_argument("--batch-size", type=int, default=5, help="Tags per DeepSeek request.")
    parser.add_argument("--sample-size", type=int, default=3, help="Sample cards fetched per tag.")
    parser.add_argument("--scryfall-delay", type=float, default=SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS)
    parser.add_argument(
        "--output",
        default="backend/data/tag_rag_mvp.json",
        help="Output JSON path, relative to repo root unless absolute.",
    )
    parser.add_argument("--print-text", action="store_true", help="Print generated embedding_text lines.")
    return parser.parse_args()


async def fetch_functional_tags(limit: int):
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(
            TAGGER_TAGS_URL,
            headers={
                "User-Agent": "MTG-AI-Search/1.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
    response.raise_for_status()
    entries, content_hash = _TaggerTagHTMLParser.parse(response.text)
    return list(entries[:limit]), content_hash


def output_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


async def main() -> None:
    args = parse_args()
    entries, content_hash = await fetch_functional_tags(args.limit)
    items = []

    for offset in range(0, len(entries), args.batch_size):
        batch = entries[offset : offset + args.batch_size]
        generated = await asyncio.to_thread(
            _generate_expansion_batch,
            batch,
            args.sample_size,
            args.scryfall_delay,
        )
        for entry in batch:
            key = f"{entry.tag_type}:{entry.tag}"
            item = generated.get(key)
            if not item:
                continue
            if args.print_text:
                print(f"[embedding_text] {key} -> {item['embedding_text']}", flush=True)
            items.append(item)

    texts = [item["embedding_text"] for item in items]
    vectors = encode_batch_safe(texts) if texts else []
    if vectors is None:
        raise RuntimeError("Embedding API failed")

    for item, vector in zip(items, vectors):
        item["embedding"] = vector
        item["embedding_dim"] = len(vector)

    payload = {
        "source_url": TAGGER_TAGS_URL,
        "source_content_hash": content_hash,
        "requested_limit": args.limit,
        "generated": len(items),
        "items": items,
    }

    path = output_path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(path),
                "requested_limit": args.limit,
                "generated": len(items),
                "embedded": len(vectors),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
