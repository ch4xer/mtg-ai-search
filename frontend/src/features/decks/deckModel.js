import { getImageUri } from "../../utils/cardImage.js";
import { getCardLegality, legalityLabel } from "../../utils/formats.js";

export const TYPE_ORDER = [
  "Planeswalker", "Creature", "Sorcery", "Instant",
  "Artifact", "Enchantment", "Land", "Other",
];

export const TYPE_LABELS_EN = {
  Creature: "Creature",
  Planeswalker: "Planeswalker",
  Instant: "Instant",
  Sorcery: "Sorcery",
  Enchantment: "Enchantment",
  Artifact: "Artifact",
  Land: "Land",
  Other: "Other",
};

export const TYPE_LABELS_ZH = {
  Creature: "生物",
  Planeswalker: "旅法师",
  Instant: "瞬间",
  Sorcery: "法术",
  Enchantment: "结界",
  Artifact: "神器",
  Land: "地",
  Other: "其他",
};

export const TYPE_MANA_CLASSES = {
  Creature: "ms-creature",
  Planeswalker: "ms-planeswalker",
  Instant: "ms-instant",
  Sorcery: "ms-sorcery",
  Enchantment: "ms-enchantment",
  Artifact: "ms-artifact",
  Land: "ms-land",
  Other: null,
};

export const DOUBLE_FACED_LAYOUTS = new Set(["transform", "modal_dfc", "double_faced_token", "reversible_card"]);

const SINGLETON_FORMATS = new Set(["commander", "brawl", "oathbreaker", "paupercommander", "pauper commander"]);
const SPECIAL_COPY_LIMITS = [
  { pattern: /up to seven cards named/i, limit: 7 },
  { pattern: /up to nine cards named/i, limit: 9 },
  { pattern: /any number of cards named/i, limit: Infinity },
];
const COLOR_ORDER = { W: 0, U: 1, B: 2, R: 3, G: 4 };

export function classifyCard(card) {
  const typeLine = card.type_line || "";
  for (const type of TYPE_ORDER) {
    if (type !== "Other" && typeLine.includes(type)) return type;
  }
  return "Other";
}

export function getColorSortIndex(card) {
  const colors = card.color_identity || card.colors || [];
  if (colors.length === 0) return 100;
  if (colors.length === 1) return COLOR_ORDER[colors[0]] ?? 50;
  return 50 + Math.min(...colors.map((color) => COLOR_ORDER[color] ?? 50));
}

export function hasUncertainCmc(card) {
  return /\{[XYZ]\}/i.test(card.mana_cost || "");
}

export function compareDeckCards(a, b) {
  const uncertainA = hasUncertainCmc(a.card);
  const uncertainB = hasUncertainCmc(b.card);
  const cmcA = a.card.cmc ?? 0;
  const cmcB = b.card.cmc ?? 0;

  if (uncertainA !== uncertainB) return uncertainA ? 1 : -1;
  if (cmcA !== cmcB && !uncertainA && !uncertainB) return cmcA - cmcB;

  const colorA = getColorSortIndex(a.card);
  const colorB = getColorSortIndex(b.card);
  if (colorA !== colorB) return colorA - colorB;

  return (a.card.name || "").localeCompare(b.card.name || "");
}

export function buildCardGroups(cards, language) {
  const labels = language === "zh" ? TYPE_LABELS_ZH : TYPE_LABELS_EN;
  const groups = {};

  for (const item of cards) {
    const type = classifyCard(item.card);
    if (!groups[type]) groups[type] = [];
    groups[type].push(item);
  }

  for (const type in groups) {
    groups[type].sort(compareDeckCards);
  }

  return TYPE_ORDER
    .filter((type) => groups[type])
    .map((type) => ({
      type,
      label: labels[type],
      count: groups[type].reduce((sum, card) => sum + card.quantity, 0),
      items: groups[type],
    }));
}

export function splitDeckBoards(cards, language) {
  const mainCards = cards.filter((card) => card.board !== "sideboard");
  const sideCards = cards.filter((card) => card.board === "sideboard");

  return {
    mainCards,
    sideCards,
    mainboardGroups: buildCardGroups(mainCards, language),
    sideboardGroups: buildCardGroups(sideCards, language),
  };
}

export function buildDeckAnalysis(analysisCards, language) {
  if (analysisCards.length === 0) return null;

  const colorCounts = { W: 0, U: 0, B: 0, R: 0, G: 0 };
  const colorLabels = language === "zh"
    ? { W: "白", U: "蓝", B: "黑", R: "红", G: "绿" }
    : { W: "White", U: "Blue", B: "Black", R: "Red", G: "Green" };

  for (const item of analysisCards) {
    const colorIdentity = item.card.color_identity || item.card.colors || [];
    for (const color of colorIdentity) {
      if (colorCounts[color] !== undefined) colorCounts[color] += item.quantity;
    }
  }

  const cmcBuckets = [0, 0, 0, 0, 0, 0, 0, 0];
  for (const item of analysisCards) {
    if ((item.card.type_line || "").includes("Land")) continue;
    cmcBuckets[Math.min(Math.floor(item.card.cmc ?? 0), 7)] += item.quantity;
  }

  const rarityOrder = ["common", "uncommon", "rare", "mythic"];
  const rarityLabels = language === "zh"
    ? { common: "普通", uncommon: "非普通", rare: "稀有", mythic: "秘稀" }
    : { common: "Common", uncommon: "Uncommon", rare: "Rare", mythic: "Mythic" };
  const rarityCounts = {};

  for (const item of analysisCards) {
    const rarity = (item.card.rarity || item.rarity || "").toLowerCase();
    if (rarityOrder.includes(rarity)) rarityCounts[rarity] = (rarityCounts[rarity] || 0) + item.quantity;
  }

  return {
    colorCounts,
    colorLabels,
    totalColorCards: Object.values(colorCounts).reduce((sum, value) => sum + value, 0) || 1,
    cmcBuckets,
    cmcMax: Math.max(...cmcBuckets, 1),
    rarityCounts,
    rarityLabels,
    rarityOrder,
    totalRarityCards: rarityOrder.reduce((sum, rarity) => sum + (rarityCounts[rarity] || 0), 0) || 1,
    totalAnalyzedCards: analysisCards.reduce((sum, card) => sum + card.quantity, 0),
  };
}

function formatIssueText(issue, language) {
  const zh = language === "zh";
  switch (issue.type) {
    case "card-legality":
      return zh
        ? `${issue.cardName}：${legalityLabel(issue.status, language)}`
        : `${issue.cardName}: ${legalityLabel(issue.status, language)}`;
    default:
      return issue.message || "";
  }
}

function quantityGuardReason(reason, data, language) {
  const zh = language === "zh";
  switch (reason) {
    case "copy-limit":
      return zh
        ? `${data.cardName} 已达到当前赛制张数上限（最多 ${data.limit} 张）`
        : `${data.cardName} has reached the copy limit (${data.limit})`;
    default:
      return "";
  }
}

function isBasicLand(card) {
  return /\bBasic\b/.test(card?.type_line || "");
}

function getSpecialCopyLimit(card) {
  const text = card?.oracle_text || "";
  for (const rule of SPECIAL_COPY_LIMITS) {
    if (rule.pattern.test(text)) return rule.limit;
  }
  return null;
}

function getCopyLimit(card, formatKey, legality) {
  if (!formatKey || formatKey === "undefined") return Infinity;
  if (isBasicLand(card)) return Infinity;

  const specialLimit = getSpecialCopyLimit(card);
  if (specialLimit !== null) return specialLimit;

  if (legality === "restricted") return 1;
  if (SINGLETON_FORMATS.has(formatKey)) return 1;
  return 4;
}

function getCardTotalMap(cards) {
  const cardTotals = new Map();

  for (const item of cards) {
    const existing = cardTotals.get(item.card_id);
    if (existing) {
      existing.quantity += item.quantity;
    } else {
      cardTotals.set(item.card_id, {
        card: item.card,
        quantity: item.quantity,
      });
    }
  }

  return cardTotals;
}

export function validateDeck(cards, formatKey = "undefined", language = "zh") {
  if (!formatKey || formatKey === "undefined") {
    return { isLegal: true, issues: [], cardIssuesById: {}, summary: "" };
  }

  const issues = [];
  const cardIssuesById = {};

  for (const item of cards) {
    const status = getCardLegality(item.card, formatKey);
    if (status !== "legal" && status !== "restricted") {
      const issue = {
        type: "card-legality",
        cardId: item.card_id,
        cardName: item.card.name,
        status,
      };
      issues.push(issue);
      cardIssuesById[item.card_id] = [...(cardIssuesById[item.card_id] || []), formatIssueText(issue, language)];
    }
  }

  return {
    isLegal: issues.length === 0,
    issues,
    cardIssuesById,
    summary: issues.length === 0
      ? (language === "zh" ? "当前卡组符合所选赛制规则" : "This deck is legal in the selected format")
      : (language === "zh" ? `发现 ${issues.length} 个赛制问题` : `${issues.length} format issues found`),
  };
}

export function getQuantityIncreaseGuards(cards, formatKey = "undefined", language = "zh") {
  const guards = {};
  if (!formatKey || formatKey === "undefined") return guards;

  const cardTotals = getCardTotalMap(cards);

  for (const item of cards) {
    const status = getCardLegality(item.card, formatKey);
    const limit = getCopyLimit(item.card, formatKey, status);
    const total = cardTotals.get(item.card_id)?.quantity || item.quantity;

    if (total >= limit) {
      guards[`${item.card_id}:${item.board}`] = {
        canIncrease: false,
        reason: quantityGuardReason("copy-limit", { cardName: item.card.name, limit }, language),
      };
    }
  }

  return guards;
}

export function getCardDisplayImage(item) {
  return item.display_url
    || getImageUri(item.card.image_uris, "art_crop")
    || getImageUri(item.card.card_faces?.[0]?.image_uris, "art_crop");
}

export function getCardFullImage(item) {
  return item.image_url
    || getImageUri(item.card.image_uris, "png")
    || getImageUri(item.card.card_faces?.[0]?.image_uris, "png");
}

export function getCardFaces(item) {
  return item?.card?.card_faces || [];
}

export function isDoubleFacedCard(item) {
  const faces = getCardFaces(item);
  return faces.length >= 2 && DOUBLE_FACED_LAYOUTS.has(item.card.layout);
}

export function getPreviewData(item, flipped = false) {
  if (!item) return null;

  const faces = getCardFaces(item);
  const isDoubleFaced = isDoubleFacedCard(item);
  const activeFace = isDoubleFaced ? faces[flipped ? 1 : 0] : null;
  const frontFace = faces[0];
  const backFace = faces[1];
  const getField = (field) => activeFace ? activeFace[field] : (item.card[field] ?? frontFace?.[field]);
  const frontImage = getCardFullImage(item)
    || getImageUri(frontFace?.image_uris, "png")
    || getImageUri(frontFace?.image_uris, "normal");
  const backImage = getImageUri(backFace?.image_uris, "png")
    || getImageUri(backFace?.image_uris, "normal");

  return {
    isDoubleFaced,
    name: activeFace?.name || item.card.name || frontFace?.name,
    mana_cost: getField("mana_cost"),
    type_line: getField("type_line"),
    oracle_text: getField("oracle_text"),
    power: getField("power"),
    toughness: getField("toughness"),
    loyalty: getField("loyalty"),
    image_url: flipped ? backImage : frontImage,
    front_image_url: frontImage,
    back_image_url: backImage,
    front_name: frontFace?.name || item.card.name,
    back_name: backFace?.name || item.card.name,
  };
}
