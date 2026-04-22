from .connection import get_pool

_ALLOWED_EMBEDDING_COLUMNS = {"name_embedding", "type_line_embedding", "oracle_text_embedding"}


async def vector_search_cards(
    column: str,
    query_embedding: list[float],
    n_results: int = 20,
    card_ids: list[str] | None = None,
) -> list[tuple[str, float]]:
    if column not in _ALLOWED_EMBEDDING_COLUMNS:
        raise ValueError(f"Invalid embedding column: {column!r}")

    pool = await get_pool()
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    if card_ids:
        query = f"""
            SELECT id, {column} <=> $1::halfvec AS distance
            FROM cards
            WHERE id = ANY($2) AND {column} IS NOT NULL AND NOT COALESCE(is_unofficial, FALSE)
            ORDER BY distance
            LIMIT $3
        """
        rows = await pool.fetch(query, embedding_str, card_ids, n_results)
    else:
        query = f"""
            SELECT id, {column} <=> $1::halfvec AS distance
            FROM cards
            WHERE {column} IS NOT NULL AND NOT COALESCE(is_unofficial, FALSE)
            ORDER BY distance
            LIMIT $2
        """
        rows = await pool.fetch(query, embedding_str, n_results)

    return [(row["id"], row["distance"]) for row in rows]


async def effect_vector_search_cards(
    query_embedding: list[float],
    n_results: int = 50,
    card_ids: list[str] | None = None,
) -> list[dict]:
    pool = await get_pool()
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    if card_ids:
        rows = await pool.fetch(
            """
            SELECT
                ce.card_id,
                ce.id AS effect_id,
                ce.effect_text,
                ce.face_index,
                ce.chunk_index,
                ce.source,
                ce.embedding <=> $1::halfvec AS distance
            FROM card_effects ce
            JOIN cards c ON c.id = ce.card_id
            WHERE ce.card_id = ANY($2) AND ce.embedding IS NOT NULL AND NOT COALESCE(c.is_unofficial, FALSE)
            ORDER BY distance
            LIMIT $3
            """,
            embedding_str,
            card_ids,
            n_results,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT
                ce.card_id,
                ce.id AS effect_id,
                ce.effect_text,
                ce.face_index,
                ce.chunk_index,
                ce.source,
                ce.embedding <=> $1::halfvec AS distance
            FROM card_effects ce
            JOIN cards c ON c.id = ce.card_id
            WHERE ce.embedding IS NOT NULL AND NOT COALESCE(c.is_unofficial, FALSE)
            ORDER BY distance
            LIMIT $2
            """,
            embedding_str,
            n_results,
        )

    return [dict(row) for row in rows]


async def search_abilities(
    query_embedding: list[float],
    n_results: int = 5,
    distance_threshold: float = 0.2,
) -> list[dict]:
    pool = await get_pool()
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    rows = await pool.fetch(
        """
        SELECT name, description, embedding <=> $1::halfvec AS distance
        FROM keyword_abilities
        WHERE embedding IS NOT NULL AND embedding <=> $1::halfvec < $3
        ORDER BY distance
        LIMIT $2
        """,
        embedding_str,
        n_results,
        distance_threshold,
    )

    return [{"name": row["name"], "description": row["description"], "distance": row["distance"]} for row in rows]
