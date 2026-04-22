"""Filter construction for card discovery queries."""

from dataclasses import dataclass


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
) -> DiscoveryFilter:
    clauses: list[str] = []
    params: list = []
    idx = 1

    if q.strip():
        for token in q.strip().split():
            clauses.append(f"(name ILIKE ${idx} OR type_line ILIKE ${idx} OR oracle_text ILIKE ${idx})")
            params.append(f"%{token}%")
            idx += 1

    if colors:
        clauses.append(f"colors @> ${idx}::text[]")
        params.append(colors)
        idx += 1

    if types:
        for card_type in types:
            clauses.append(f"type_line ILIKE ${idx}")
            params.append(f"%{card_type}%")
            idx += 1

    if subtypes:
        for subtype in subtypes:
            clauses.append(f"split_part(type_line, '\u2014', 2) ILIKE ${idx}")
            params.append(f"%{subtype}%")
            idx += 1

    if rarities:
        clauses.append(f"cp.rarity = ANY(${idx}::text[])")
        params.append(rarities)
        idx += 1

    if keywords:
        for keyword in keywords:
            clauses.append(f"EXISTS (SELECT 1 FROM unnest(keywords) AS k WHERE k ILIKE ${idx})")
            params.append(keyword)
            idx += 1

    if cmc_min is not None:
        clauses.append(f"cmc >= ${idx}::real")
        params.append(float(cmc_min))
        idx += 1
    if cmc_max is not None:
        clauses.append(f"cmc <= ${idx}::real")
        params.append(float(cmc_max))
        idx += 1

    if power_min is not None:
        clauses.append(f"power ~ '^[0-9]+\\.?[0-9]*$' AND CAST(power AS real) >= ${idx}::real")
        params.append(float(power_min))
        idx += 1
    if power_max is not None:
        clauses.append(f"power ~ '^[0-9]+\\.?[0-9]*$' AND CAST(power AS real) <= ${idx}::real")
        params.append(float(power_max))
        idx += 1

    if toughness_min is not None:
        clauses.append(f"toughness ~ '^[0-9]+\\.?[0-9]*$' AND CAST(toughness AS real) >= ${idx}::real")
        params.append(float(toughness_min))
        idx += 1
    if toughness_max is not None:
        clauses.append(f"toughness ~ '^[0-9]+\\.?[0-9]*$' AND CAST(toughness AS real) <= ${idx}::real")
        params.append(float(toughness_max))
        idx += 1

    return DiscoveryFilter(
        where=" AND ".join(clauses) if clauses else "TRUE",
        params=params,
        next_param_index=idx,
        need_rarity_join=rarities is not None,
    )

