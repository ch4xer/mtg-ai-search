"""Filter construction for card discovery queries."""

import re
from dataclasses import dataclass

_CJK_RE = re.compile(r"[\u3400-\u9fff]")


@dataclass(frozen=True)
class DiscoveryFilter:
    where: str
    params: list
    next_param_index: int
    need_rarity_join: bool


def build_discovery_filter(
    q: str = "",
    colors: list[str] | None = None,
    types: list[str] | None = None,
    rarities: list[str] | None = None,
    keywords: list[str] | None = None,
    cmc_min: float | None = None,
    cmc_max: float | None = None,
    power_min: float | None = None,
    power_max: float | None = None,
    subtypes: list[str] | None = None,
    toughness_min: float | None = None,
    toughness_max: float | None = None,
    include_playtest: bool = False,
) -> DiscoveryFilter:
    clauses: list[str] = []
    params: list = []
    idx = 1

    if not include_playtest:
        clauses.append("NOT COALESCE(c.is_unofficial, FALSE)")

    if q.strip():
        search_chinese = _contains_cjk(q)
        for token in q.strip().split():
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
        clauses.append(f"c.colors @> ${idx}::text[]")
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

    if rarities:
        clauses.append(f"cp.rarity = ANY(${idx}::text[])")
        params.append(rarities)
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

    return DiscoveryFilter(
        where=" AND ".join(clauses) if clauses else "TRUE",
        params=params,
        next_param_index=idx,
        need_rarity_join=rarities is not None,
    )


def _contains_cjk(value: str) -> bool:
    return bool(_CJK_RE.search(value))
