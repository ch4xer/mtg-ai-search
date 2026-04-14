// Deck formats supported by the app.
// `key` matches backend value + Scryfall's card.legalities key (where applicable).
// `label` is the Chinese display label. `undefined` is the default category.
export const FORMATS = [
  { key: "undefined", label: "未指定", legalityKey: null },
  { key: "standard", label: "标准 (Standard)", legalityKey: "standard" },
  { key: "pioneer", label: "先驱 (Pioneer)", legalityKey: "pioneer" },
  { key: "modern", label: "摩登 (Modern)", legalityKey: "modern" },
  { key: "legacy", label: "薪传 (Legacy)", legalityKey: "legacy" },
  { key: "vintage", label: "特选 (Vintage)", legalityKey: "vintage" },
  { key: "pauper", label: "纯铁 (Pauper)", legalityKey: "pauper" },
  { key: "commander", label: "指挥官 (Commander)", legalityKey: "commander" },
  { key: "brawl", label: "争锋 (Brawl)", legalityKey: "brawl" },
  { key: "historic", label: "史册 (Historic)", legalityKey: "historic" },
  { key: "alchemy", label: "炼金 (Alchemy)", legalityKey: "alchemy" },
  { key: "explorer", label: "探索 (Explorer)", legalityKey: "explorer" },
  { key: "oathbreaker", label: "破誓者 (Oathbreaker)", legalityKey: "oathbreaker" },
  { key: "premodern", label: "前摩登 (Premodern)", legalityKey: "premodern" },
];

const FORMAT_MAP = Object.fromEntries(FORMATS.map((f) => [f.key, f]));

export function getFormat(key) {
  return FORMAT_MAP[key] || FORMATS[0];
}

export function getFormatLabel(key) {
  return getFormat(key).label;
}

/**
 * Check a card's legality in a deck format.
 * Returns one of: "legal" | "not_legal" | "banned" | "restricted" | "unknown"
 * For the "undefined" format, legality is meaningless so returns "unknown".
 */
export function getCardLegality(card, formatKey) {
  const fmt = getFormat(formatKey);
  if (!fmt.legalityKey) return "unknown";
  const legalities = card?.legalities;
  if (!legalities) return "unknown";
  return legalities[fmt.legalityKey] || "unknown";
}

export function isCardLegal(card, formatKey) {
  const status = getCardLegality(card, formatKey);
  return status === "legal" || status === "restricted";
}

export function legalityLabel(status) {
  switch (status) {
    case "legal":
      return "合法";
    case "not_legal":
      return "不合法";
    case "banned":
      return "禁用";
    case "restricted":
      return "限用";
    default:
      return "未知";
  }
}
