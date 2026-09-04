// Deck formats supported by the app.
// `key` matches backend value + Scryfall's card.legalities key (where applicable).
// `labelZh` and `labelEn` are the display labels for each language. `undefined` is the default category.
export const FORMATS = [
  { key: "undefined", labelZh: "未指定", labelEn: "Undefined", legalityKey: null },
  { key: "standard", labelZh: "标准", labelEn: "Standard", legalityKey: "standard" },
  { key: "pioneer", labelZh: "先驱", labelEn: "Pioneer", legalityKey: "pioneer" },
  { key: "modern", labelZh: "摩登", labelEn: "Modern", legalityKey: "modern" },
  { key: "legacy", labelZh: "薪传", labelEn: "Legacy", legalityKey: "legacy" },
  { key: "vintage", labelZh: "特选", labelEn: "Vintage", legalityKey: "vintage" },
  { key: "pauper", labelZh: "纯铁", labelEn: "Pauper", legalityKey: "pauper" },
  { key: "commander", labelZh: "指挥官", labelEn: "Commander", legalityKey: "commander" },
  { key: "brawl", labelZh: "争锋", labelEn: "Brawl", legalityKey: "brawl" },
  { key: "historic", labelZh: "史册", labelEn: "Historic", legalityKey: "historic" },
  { key: "alchemy", labelZh: "炼金", labelEn: "Alchemy", legalityKey: "alchemy" },
  { key: "explorer", labelZh: "探索", labelEn: "Explorer", legalityKey: "explorer" },
  { key: "oathbreaker", labelZh: "破誓者", labelEn: "Oathbreaker", legalityKey: "oathbreaker" },
  { key: "premodern", labelZh: "前摩登", labelEn: "Premodern", legalityKey: "premodern" },
];

const FORMAT_MAP = Object.fromEntries(FORMATS.map((f) => [f.key, f]));

function getFormat(key) {
  return FORMAT_MAP[key] || FORMATS[0];
}

export function getFormatLabel(key, language = 'zh') {
  const format = getFormat(key);
  return language === 'zh' ? format.labelZh : format.labelEn;
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

export function legalityLabel(status, language = 'zh') {
  if (language === 'zh') {
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
  } else {
    switch (status) {
      case "legal":
        return "Legal";
      case "not_legal":
        return "Not Legal";
      case "banned":
        return "Banned";
      case "restricted":
        return "Restricted";
      default:
        return "Unknown";
    }
  }
}
