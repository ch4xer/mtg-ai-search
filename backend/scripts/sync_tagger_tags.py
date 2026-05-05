"""Synchronize Scryfall Tagger tags into the local database."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.migrations import run_pre_seed
from app.repositories.database import close_pool, get_pool
from app.services.tag_search_service import update_tagger_tags_if_changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Scryfall Tagger tags into Postgres.")
    parser.add_argument("--force", action="store_true", help="Ignore the stored ETag and refresh from Scryfall.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    try:
        pool = await get_pool()
        await run_pre_seed(pool)
        result = await update_tagger_tags_if_changed(force=args.force)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
