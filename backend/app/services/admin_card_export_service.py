"""Admin export helpers for card-search data."""

from __future__ import annotations

import json
import os
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from ..repositories.database import get_pool


EXPORT_FORMAT_VERSION = 1


@dataclass(frozen=True)
class ExportTable:
    name: str
    order_by: str
    columns: tuple[str, ...]
    embedding_columns: tuple[str, ...] = ()


CARD_EXPORT_TABLES = (
    ExportTable(
        name="cards",
        order_by="name, id",
        columns=(
            "id",
            "name",
            "mana_cost",
            "cmc",
            "type_line",
            "oracle_text",
            "power",
            "toughness",
            "colors",
            "color_identity",
            "keywords",
            "legalities",
            "layout",
            "card_faces",
            "image_set_code",
            "image_set_name",
            "image_collector_number",
            "is_unofficial",
            "is_playtest",
        ),
        embedding_columns=("name_embedding", "type_line_embedding", "oracle_text_embedding"),
    ),
    ExportTable(
        name="card_prints",
        order_by="card_id, released_at NULLS LAST, set_code, collector_num, id",
        columns=(
            "id",
            "card_id",
            "set_code",
            "set_name",
            "collector_num",
            "rarity",
            "artist",
            "flavor_name",
            "flavor_text",
            "released_at",
            "finishes",
            "image_small",
            "image_normal",
            "image_large",
            "image_png",
            "image_art_crop",
            "image_border_crop",
            "card_faces",
            "image_set_code",
            "image_set_name",
            "image_collector_number",
            "set_type",
            "security_stamp",
            "border_color",
            "games",
        ),
    ),
    ExportTable(
        name="card_effects",
        order_by="card_id, face_index, chunk_index, id",
        columns=("id", "card_id", "face_index", "chunk_index", "effect_text", "source"),
        embedding_columns=("embedding",),
    ),
    ExportTable(
        name="keyword_abilities",
        order_by="name, id",
        columns=("id", "name", "description"),
        embedding_columns=("embedding",),
    ),
)


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _select_list(table: ExportTable, include_embeddings: bool) -> str:
    columns = [f'"{column}"' for column in table.columns]
    if include_embeddings:
        columns.extend(f'"{column}"::text AS "{column}"' for column in table.embedding_columns)
    return ", ".join(columns)


async def export_card_database(*, include_embeddings: bool = False) -> tuple[str, str]:
    """Export card-search tables to a ZIP file and return (path, filename)."""
    pool = await get_pool()
    exported_at = datetime.now(timezone.utc)
    fd, path = tempfile.mkstemp(prefix="mtg-card-export-", suffix=".zip")
    os.close(fd)

    manifest = {
        "format": "mtg-ai-search-card-export",
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": exported_at.isoformat(),
        "include_embeddings": include_embeddings,
        "tables": [],
    }

    try:
        async with pool.acquire() as conn:
            table_counts = {
                table.name: await conn.fetchval(f'SELECT COUNT(*) FROM "{table.name}"')
                for table in CARD_EXPORT_TABLES
            }

            with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
                for table in CARD_EXPORT_TABLES:
                    file_name = f"{table.name}.jsonl"
                    selected_columns = (*table.columns, *(table.embedding_columns if include_embeddings else ()))
                    manifest["tables"].append(
                        {
                            "name": table.name,
                            "file": file_name,
                            "row_count": table_counts[table.name],
                            "columns": list(selected_columns),
                        }
                    )

                    query = f'SELECT {_select_list(table, include_embeddings)} FROM "{table.name}" ORDER BY {table.order_by}'
                    async with conn.transaction():
                        with archive.open(file_name, "w") as handle:
                            async for row in conn.cursor(query, prefetch=1000):
                                line = json.dumps(dict(row), ensure_ascii=False, default=_json_default, separators=(",", ":"))
                                handle.write(line.encode("utf-8"))
                                handle.write(b"\n")

                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2, default=_json_default) + "\n",
                )
    except Exception:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise

    stamp = exported_at.strftime("%Y%m%d-%H%M%S")
    suffix = "with-embeddings" if include_embeddings else "no-embeddings"
    return path, f"mtg-card-data-{suffix}-{stamp}.zip"
