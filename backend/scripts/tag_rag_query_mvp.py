"""Query the no-database Tagger RAG MVP JSON file."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.embedding import encode_query
from app.services.tag_search_service import _analyze_query_with_llm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run query rewrite + vector search over tag_rag_mvp.json.")
    parser.add_argument("query", help="Natural-language user query.")
    parser.add_argument("--input", default="backend/data/tag_rag_mvp.json", help="MVP JSON path.")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to print.")
    parser.add_argument("--print-rewrite", action="store_true", help="Print DeepSeek rewrite details.")
    return parser.parse_args()


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[2] / path


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def build_query_text(analysis) -> str:
    parts = [analysis.intent]
    for target in analysis.targets:
        parts.append(target.intent)
        parts.extend(target.expansions)
    parts.extend(analysis.expansions)
    return ". ".join(dict.fromkeys(part for part in parts if part))


async def main() -> None:
    args = parse_args()
    path = resolve_path(args.input)
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    items = [
        item
        for item in data.get("items", [])
        if isinstance(item.get("embedding"), list) and item.get("tag_type") == "function"
    ]
    if not items:
        raise RuntimeError(f"No embedded functional tag items found in {path}")

    analysis = await asyncio.to_thread(_analyze_query_with_llm, args.query)
    query_text = build_query_text(analysis)
    query_embedding = encode_query([query_text])[0]

    scored = []
    for item in items:
        score = cosine_similarity(query_embedding, item["embedding"])
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    if args.print_rewrite:
        print(
            json.dumps(
                {
                    "original_query": args.query,
                    "type_hint": analysis.type_hint,
                    "intent": analysis.intent,
                    "expansions": list(analysis.expansions),
                    "targets": [
                        {
                            "type": target.type_hint,
                            "intent": target.intent,
                            "expansions": list(target.expansions),
                        }
                        for target in analysis.targets
                    ],
                    "query_text_for_embedding": query_text,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    results = []
    for score, item in scored[: args.top_k]:
        results.append(
            {
                "score": round(score, 6),
                "tag": item["tag"],
                "tag_type": item["tag_type"],
                "description": item.get("description", ""),
                "embedding_text": item.get("embedding_text", ""),
                "sample_cards": item.get("sample_cards", [])[:3],
                "scryfall_query": f'function:"{item["tag"]}"',
            }
        )

    print(
        json.dumps(
            {
                "query": args.query,
                "index_size": len(items),
                "note": "This MVP only searches tags present in the input JSON sample.",
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
