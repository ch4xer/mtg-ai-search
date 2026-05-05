"""Generate embeddings for cached functional Tagger tags."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tag_search_service import generate_missing_tag_embeddings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate embeddings for functional Tagger tags.")
    parser.add_argument("--limit", type=int, default=500, help="Maximum tags to process this run.")
    parser.add_argument("--batch-size", type=int, default=64, help="Embedding batch size.")
    parser.add_argument("--force", action="store_true", help="Regenerate embeddings even when already present.")
    parser.add_argument("--print-text", action="store_true", help="Print each embedding_text before embedding it.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await generate_missing_tag_embeddings(
        limit=args.limit,
        batch_size=args.batch_size,
        force=args.force,
        print_embedding_text=args.print_text,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
