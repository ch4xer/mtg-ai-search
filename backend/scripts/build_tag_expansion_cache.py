"""Build the offline English semantic-expansion cache for Scryfall Tagger tags."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.tag_search_service import SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS, build_tag_expansion_cache


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate cached retrieval text for Tagger tags.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum missing tags to generate this run.")
    parser.add_argument("--batch-size", type=int, default=10, help="Tags per DeepSeek request.")
    parser.add_argument("--sample-size", type=int, default=3, help="Scryfall sample cards to fetch per tag.")
    parser.add_argument(
        "--scryfall-delay",
        type=float,
        default=None,
        help="Delay in seconds between Scryfall sample-card requests.",
    )
    parser.add_argument("--print-text", action="store_true", help="Print generated embedding_text lines.")
    parser.add_argument("--force", action="store_true", help="Regenerate existing cache entries.")
    parser.add_argument(
        "--type",
        choices=("function",),
        action="append",
        dest="tag_types",
        help="Restrict generation to functional tags. Kept for CLI compatibility.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await build_tag_expansion_cache(
        limit=args.limit,
        batch_size=args.batch_size,
        force=args.force,
        tag_types=set(args.tag_types) if args.tag_types else None,
        sample_size=args.sample_size,
        scryfall_delay_seconds=(
            args.scryfall_delay if args.scryfall_delay is not None else SCRYFALL_SAMPLE_REQUEST_DELAY_SECONDS
        ),
        print_embedding_text=args.print_text,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
