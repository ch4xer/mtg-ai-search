import { getExactImageUri, getImageUri } from "../../utils/cardImage.js";
import { getCardLegality, legalityLabel } from "../../utils/formats.js";

export const TYPE_LABELS_EN = {
  Creature: "Creature",
  Planeswalker: "Planeswalker",
  Instant: "Instant",
  Sorcery: "Sorcery",
  Enchantment: "Enchantment",
  Artifact: "Artifact",
  Battle: "Battle",
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
  Battle: "战役",
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
  Battle: "ms-battle",
  Land: "ms-land",
  Other: null,
};

export const DOUBLE_FACED_LAYOUTS = new Set(["transform", "modal_dfc", "double_faced_token", "reversible_card"]);

const COLOR_ORDER = { W: 0, U: 1, B: 2, R: 3, G: 4 };

export function getDeckType(card) {
  return card?.deck_type || "Other";
}

function getChineseTranslation(card, field, faceIndex = null, fallbackToCard = true) {
  const zhCard = card?.zh;
  if (!zhCard) return null;

  const zhFaces = Array.isArray(zhCard.card_faces) ? zhCard.card_faces : [];
  if (Number.isInteger(faceIndex)) {
    const faceValue = zhFaces[faceIndex]?.[field];
    if (faceValue) return faceValue;
  }

  return fallbackToCard ? (zhCard[field] || null) : null;
}

export function getLocalizedCardField(card, field, language = "zh", faceIndex = null) {
  if (!card) return "";
  if (language === "zh") {
    const translated = getChineseTranslation(card, field, faceIndex);
    if (translated) return translated;
  }

  if (Number.isInteger(faceIndex)) {
    const faceValue = card.card_faces?.[faceIndex]?.[field];
    if (faceValue) return faceValue;
  }

  return card[field] || "";
}

export function getLocalizedCardName(card, language = "zh", faceIndex = null) {
  return getLocalizedCardField(card, "name", language, faceIndex) || card?.name || "";
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

export function compareDeckCards(a, b, language = "zh") {
  const uncertainA = hasUncertainCmc(a.card);
  const uncertainB = hasUncertainCmc(b.card);
  const cmcA = a.card.cmc ?? 0;
  const cmcB = b.card.cmc ?? 0;

  if (uncertainA !== uncertainB) return uncertainA ? 1 : -1;
  if (cmcA !== cmcB && !uncertainA && !uncertainB) return cmcA - cmcB;

  const colorA = getColorSortIndex(a.card);
  const colorB = getColorSortIndex(b.card);
  if (colorA !== colorB) return colorA - colorB;

  return getLocalizedCardName(a.card, language).localeCompare(getLocalizedCardName(b.card, language));
}

export function buildCardGroups(cards, language) {
  const labels = language === "zh" ? TYPE_LABELS_ZH : TYPE_LABELS_EN;
  const groups = {};

  for (const item of cards) {
    const type = getDeckType(item.card);
    if (!groups[type]) groups[type] = { type, sort: item.card.deck_type_sort ?? 999, items: [] };
    groups[type].items.push(item);
  }

  for (const type in groups) {
    groups[type].items.sort((a, b) => compareDeckCards(a, b, language));
  }

  return Object.values(groups)
    .sort((a, b) => a.sort - b.sort)
    .map((group) => ({
      type: group.type,
      label: labels[group.type] || labels.Other,
      count: group.items.reduce((sum, card) => sum + card.quantity, 0),
      items: group.items,
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
    if (getDeckType(item.card) === "Land") continue;
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
        cardName: getLocalizedCardName(item.card, language),
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

export function getCardDisplayImage(item) {
  return item.display_url
    || getImageUri(item.card.image_uris, "art_crop")
    || getImageUri(item.card.card_faces?.[0]?.image_uris, "art_crop");
}

export function getCardCoverImage(item) {
  return item.card.image_uris?.art_crop
    || item.card.card_faces?.[0]?.image_uris?.art_crop
    || "";
}

export function getCardFullImage(item) {
  return getExactImageUri(item.card.image_uris, "png")
    || getExactImageUri(item.card.card_faces?.[0]?.image_uris, "png")
    || item.image_url;
}

export function getCardFaces(item) {
  return item?.card?.card_faces || [];
}

export function isDoubleFacedCard(item) {
  const faces = getCardFaces(item);
  return faces.length >= 2 && DOUBLE_FACED_LAYOUTS.has(item.card.layout);
}

export function getPreviewData(item, flipped = false, language = "zh") {
  if (!item) return null;

  const faces = getCardFaces(item);
  const isDoubleFaced = isDoubleFacedCard(item);
  const activeFaceIndex = isDoubleFaced ? (flipped ? 1 : 0) : 0;
  const activeFace = isDoubleFaced ? faces[activeFaceIndex] : null;
  const frontFace = faces[0];
  const backFace = faces[1];
  const getEnglishField = (field) => activeFace ? activeFace[field] : (item.card[field] ?? frontFace?.[field]);
  const getTranslatedField = (field) => {
    const translatedFaceValue = getChineseTranslation(item.card, field, activeFaceIndex, !isDoubleFaced);
    if (translatedFaceValue) return translatedFaceValue;
    return isDoubleFaced ? null : getChineseTranslation(item.card, field);
  };
  const getField = (field) => (language === "zh" ? getTranslatedField(field) : null) || getEnglishField(field);
  const englishName = activeFace?.name || item.card.name || frontFace?.name;
  const translatedName = language === "zh"
    ? getTranslatedField("name")
    : null;
  const displayName = translatedName || englishName;
  const frontImage = getCardFullImage(item)
    || getExactImageUri(frontFace?.image_uris, "png");
  const backImage = getExactImageUri(backFace?.image_uris, "png");

  return {
    isDoubleFaced,
    name: displayName,
    secondary_name: translatedName && englishName && translatedName !== englishName ? englishName : "",
    mana_cost: getField("mana_cost"),
    type_line: getField("type_line"),
    oracle_text: getField("oracle_text"),
    power: getField("power"),
    toughness: getField("toughness"),
    loyalty: getField("loyalty"),
    image_url: flipped ? backImage : frontImage,
    front_image_url: frontImage,
    back_image_url: backImage,
    front_name: (language === "zh" ? getChineseTranslation(item.card, "name", 0, false) : null) || frontFace?.name || item.card.name,
    back_name: (language === "zh" ? getChineseTranslation(item.card, "name", 1, false) : null) || backFace?.name || item.card.name,
  };
}
