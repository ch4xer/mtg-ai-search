const VALID_COLORS = new Set(["W", "U", "B", "R", "G"]);
const VALID_TYPES = new Set([
  "Creature",
  "Instant",
  "Sorcery",
  "Enchantment",
  "Artifact",
  "Land",
  "Planeswalker",
  "Battle",
]);
const VALID_RARITIES = new Set(["common", "uncommon", "rare", "mythic"]);

const ARRAY_PARAMS = {
  colors: "color",
  types: "type",
  setCodes: "set",
  keywords: "keyword",
  subtypes: "subtype",
};

const NUMBER_PARAMS = {
  cmcMin: "cmc_min",
  cmcMax: "cmc_max",
  powerMin: "power_min",
  powerMax: "power_max",
  toughnessMin: "toughness_min",
  toughnessMax: "toughness_max",
};

export const EMPTY_EXACT_SEARCH = Object.freeze({
  q: "",
  colors: [],
  types: [],
  rarity: "",
  setCodes: [],
  keywords: [],
  subtypes: [],
  functionTags: [],
  sourceCardId: null,
  cmcMin: "",
  cmcMax: "",
  powerMin: "",
  powerMax: "",
  toughnessMin: "",
  toughnessMax: "",
  page: 1,
});

function uniqueSorted(values, transform = (value) => value) {
  return [...new Set(values.map((value) => transform(value.trim())).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right));
}

function validNumber(value) {
  if (value === null || value === "") return "";
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? String(number) : "";
}

function readArray(params, key) {
  return uniqueSorted(params.getAll(key));
}

const FUNCTION_TAG_EXPRESSION = /(^|\s)tag:(?:"((?:\\.|[^"\\])*)"|([^\s]+))/giu;
const SAFE_FUNCTION_TAG = /^[\p{L}\p{N}_-]+$/u;

function parseExactQuery(value) {
  const functionTags = [];
  const text = value.replace(FUNCTION_TAG_EXPRESSION, (match, leadingSpace, quoted, bare) => {
    let tag = bare || "";
    if (quoted !== undefined) {
      try {
        tag = JSON.parse(`"${quoted}"`);
      } catch {
        tag = quoted;
      }
    }
    if (tag.trim()) functionTags.push(tag.trim());
    return leadingSpace ? " " : "";
  });
  return {
    text: text.replace(/\s+/g, " ").trim(),
    functionTags: uniqueSorted(functionTags),
  };
}

function buildExactQuery(text, functionTags) {
  const tagExpressions = uniqueSorted(functionTags).map((tag) => (
    SAFE_FUNCTION_TAG.test(tag) ? `tag:${tag}` : `tag:${JSON.stringify(tag)}`
  ));
  return [text.trim(), ...tagExpressions].filter(Boolean).join(" ");
}

export function parseSearchLocation(pathname, search = "") {
  const params = new URLSearchParams(search);
  if (pathname === "/exact-match") {
    const parsedQuery = parseExactQuery(params.get("q") || "");
    const colors = readArray(params, "color").filter((value) => VALID_COLORS.has(value));
    const types = readArray(params, "type").filter((value) => VALID_TYPES.has(value)).slice(0, 1);
    const rarityValue = params.get("rarity") || "";
    const pageValue = Number.parseInt(params.get("page") || "1", 10);
    const state = {
      ...EMPTY_EXACT_SEARCH,
      q: parsedQuery.text,
      colors,
      types,
      rarity: VALID_RARITIES.has(rarityValue) ? rarityValue : "",
      setCodes: uniqueSorted(params.getAll("set"), (value) => value.toLowerCase()),
      keywords: readArray(params, "keyword"),
      subtypes: readArray(params, "subtype"),
      functionTags: parsedQuery.functionTags,
      sourceCardId: (params.get("source") || "").trim() || null,
      page: Number.isInteger(pageValue) && pageValue > 0 ? pageValue : 1,
    };
    for (const [property, param] of Object.entries(NUMBER_PARAMS)) {
      state[property] = validNumber(params.get(param));
    }
    return { mode: "exact", exact: state };
  }

  return { mode: "ai", query: (params.get("q") || "").trim() };
}

export function buildAiSearchUrl(query) {
  const params = new URLSearchParams();
  const trimmed = query.trim();
  if (trimmed) params.set("q", trimmed);
  const suffix = params.toString();
  return suffix ? `/?${suffix}` : "/";
}

export function buildExactSearchUrl(input) {
  const state = { ...EMPTY_EXACT_SEARCH, ...input };
  const params = new URLSearchParams();
  const functionTagValues = uniqueSorted(Array.from(state.functionTags || []));
  const q = buildExactQuery(state.q, functionTagValues);
  if (q) params.set("q", q);

  for (const [property, param] of Object.entries(ARRAY_PARAMS)) {
    const transform = property === "setCodes" ? (value) => value.toLowerCase() : undefined;
    const values = uniqueSorted(Array.from(state[property] || []), transform);
    values.forEach((value) => params.append(param, value));
  }
  if (functionTagValues.length && state.sourceCardId) params.set("source", state.sourceCardId);
  if (VALID_RARITIES.has(state.rarity)) params.set("rarity", state.rarity);
  for (const [property, param] of Object.entries(NUMBER_PARAMS)) {
    const value = validNumber(state[property]);
    if (value !== "") params.set(param, value);
  }
  const page = Number.parseInt(state.page, 10);
  if (Number.isInteger(page) && page > 1) params.set("page", String(page));

  const suffix = params.toString();
  return suffix ? `/exact-match?${suffix}` : "/exact-match";
}

export function exactSearchToRequest(state, page = state.page) {
  const body = { page, page_size: 60 };
  if (state.q.trim()) body.q = state.q.trim();
  if (state.colors.length) body.colors = state.colors;
  if (state.types.length) body.types = state.types;
  if (state.rarity) body.rarities = [state.rarity];
  if (state.setCodes.length) body.set_codes = state.setCodes;
  if (state.keywords.length) body.keywords = state.keywords;
  if (state.subtypes.length) body.subtypes = state.subtypes;
  if (state.functionTags.length) {
    body.function_tags = state.functionTags;
    if (state.sourceCardId) body.exclude_card_id = state.sourceCardId;
  }
  for (const [property, param] of Object.entries(NUMBER_PARAMS)) {
    const value = validNumber(state[property]);
    if (value !== "") body[param] = Number(value);
  }
  return body;
}

export function hasExactSearch(state) {
  return Boolean(
    state.q.trim()
    || state.colors.length
    || state.types.length
    || state.rarity
    || state.setCodes.length
    || state.keywords.length
    || state.subtypes.length
    || state.functionTags.length
    || Object.keys(NUMBER_PARAMS).some((property) => state[property] !== "")
  );
}
