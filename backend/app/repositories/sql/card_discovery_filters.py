"""Filter construction for card discovery queries."""

import re
from dataclasses import dataclass

_CJK_RE = re.compile(r"[\u3400-\u9fff]")


@dataclass(frozen=True)
class DiscoveryFilter:
    where: str
    params: list
    next_param_index: int
    need_print_join: bool
    relevance_expr: str = ""
    where_param_count: int = 0


def build_discovery_filter(
    q: str = "",
    colors: list[str] | None = None,
    types: list[str] | None = None,
    rarities: list[str] | None = None,
    set_codes: list[str] | None = None,
    keywords: list[str] | None = None,
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    power_min: float | None = None,
    power_max: float | None = None,
    subtypes: list[str] | None = None,
    function_tags: list[str] | None = None,
    exclude_card_id: str | None = None,
    toughness_min: float | None = None,
    toughness_max: float | None = None,
    include_playtest: bool = False,
) -> DiscoveryFilter:
    clauses: list[str] = []
    params: list = []
    idx = 1
    relevance_expr = "0"
    search_chinese = False
    tokens: list[str] = []

    if not include_playtest:
        clauses.append("NOT COALESCE(c.is_unofficial, FALSE)")

    if q.strip():
        search_chinese = _contains_cjk(q)
        tokens = q.strip().split()
        for token in tokens:
            if search_chinese:
                clauses.append(
                    f"""EXISTS (
                        SELECT 1 FROM card_print_translations zt
                        WHERE zt.card_id = c.id
                          AND zt.lang = 'zhs'
                          AND zt.status = 'ok'
                          AND (
                              zt.name ILIKE ${idx}
                              OR zt.type_line ILIKE ${idx}
                              OR zt.oracle_text ILIKE ${idx}
                              OR zt.set_name ILIKE ${idx}
                              OR EXISTS (
                                  SELECT 1
                                  FROM jsonb_array_elements(COALESCE(zt.card_faces, '[]'::jsonb)) AS face(value)
                                  WHERE face.value ->> 'name' ILIKE ${idx}
                                     OR face.value ->> 'type_line' ILIKE ${idx}
                                     OR face.value ->> 'oracle_text' ILIKE ${idx}
                                     OR face.value ->> 'set_name' ILIKE ${idx}
                              )
                          )
                    )"""
                )
            else:
                clauses.append(f"(c.name ILIKE ${idx} OR c.type_line ILIKE ${idx} OR c.oracle_text ILIKE ${idx})")
            params.append(f"%{token}%")
            idx += 1

    if colors:
        clauses.append(
            f"(COALESCE(c.colors, ARRAY[]::text[]) @> ${idx}::text[] "
            f"AND COALESCE(c.colors, ARRAY[]::text[]) <@ ${idx}::text[])"
        )
        params.append(colors)
        idx += 1

    if types:
        for card_type in types:
            clauses.append(f"c.type_line ILIKE ${idx}")
            params.append(f"%{card_type}%")
            idx += 1

    if subtypes:
        for subtype in subtypes:
            clauses.append(f"split_part(c.type_line, '\u2014', 2) ILIKE ${idx}")
            params.append(f"%{subtype}%")
            idx += 1

    normalized_function_tags = sorted({tag.strip().lower() for tag in function_tags or [] if tag.strip()})
    if normalized_function_tags:
        clauses.append(
            f"""EXISTS (
                SELECT 1
                FROM card_tagger_tags ctt_filter
                JOIN tagger_tags tt_filter
                  ON tt_filter.tag_type = ctt_filter.tag_type
                 AND tt_filter.tag = ctt_filter.tag
                 AND tt_filter.removed_at IS NULL
                WHERE ctt_filter.card_id = c.id
                  AND ctt_filter.tag_type = 'function'
                  AND (
                      LOWER(ctt_filter.tag) = ANY(${idx}::text[])
                      OR LOWER(tt_filter.label) = ANY(${idx}::text[])
                  )
            )"""
        )
        params.append(normalized_function_tags)
        idx += 1

    if exclude_card_id and normalized_function_tags:
        clauses.append(f"c.id <> ${idx}")
        params.append(exclude_card_id)
        idx += 1

    if rarities:
        clauses.append(f"cp.rarity = ANY(${idx}::text[])")
        params.append(rarities)
        idx += 1

    normalized_set_codes = sorted({code.strip().lower() for code in set_codes or [] if code.strip()})
    if normalized_set_codes:
        clauses.append(f"cp.set_code = ANY(${idx}::text[])")
        params.append(normalized_set_codes)
        idx += 1

    if keywords:
        for keyword in keywords:
            clauses.append(f"EXISTS (SELECT 1 FROM unnest(c.keywords) AS k WHERE k ILIKE ${idx})")
            params.append(keyword)
            idx += 1

    if cmc_min is not None:
        clauses.append(f"c.cmc >= ${idx}::real")
        params.append(float(cmc_min))
        idx += 1
    if cmc_max is not None:
        clauses.append(f"c.cmc <= ${idx}::real")
        params.append(float(cmc_max))
        idx += 1

    if power_min is not None:
        clauses.append(f"c.power ~ '^[0-9]+\\.?[0-9]*$' AND CAST(c.power AS real) >= ${idx}::real")
        params.append(float(power_min))
        idx += 1
    if power_max is not None:
        clauses.append(f"c.power ~ '^[0-9]+\\.?[0-9]*$' AND CAST(c.power AS real) <= ${idx}::real")
        params.append(float(power_max))
        idx += 1

    if toughness_min is not None:
        clauses.append(f"c.toughness ~ '^[0-9]+\\.?[0-9]*$' AND CAST(c.toughness AS real) >= ${idx}::real")
        params.append(float(toughness_min))
        idx += 1
    if toughness_max is not None:
        clauses.append(f"c.toughness ~ '^[0-9]+\\.?[0-9]*$' AND CAST(c.toughness AS real) <= ${idx}::real")
        params.append(float(toughness_max))
        idx += 1

    where_param_count = idx - 1

    # Build relevance score for non-CJK queries after all WHERE params
    if not search_chinese and len(tokens) >= 1:
        full_query = q.strip()
        params.append(full_query)
        exact_idx = idx
        idx += 1
        params.append(f"{full_query}%")
        prefix_idx = idx
        idx += 1
        name_clauses_parts = []
        for token in tokens:
            params.append(f"%{token}%")
            name_clauses_parts.append(f"c.name ILIKE ${idx}")
            idx += 1
        name_all_tokens = " AND ".join(name_clauses_parts)
        relevance_expr = (
            f"CASE WHEN c.name ILIKE ${exact_idx} THEN 0"
            f" WHEN c.name ILIKE ${prefix_idx} THEN 1"
            f" WHEN ({name_all_tokens}) THEN 2"
            f" ELSE 3 END"
        )

    return DiscoveryFilter(
        where=" AND ".join(clauses) if clauses else "TRUE",
        params=params,
        next_param_index=idx,
        need_print_join=bool(rarities or normalized_set_codes),
        relevance_expr=relevance_expr,
        where_param_count=where_param_count,
    )


def _contains_cjk(value: str) -> bool:
    return bool(_CJK_RE.search(value))
