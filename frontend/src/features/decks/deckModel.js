import {
  getCardImage,
  getCardPresentation,
  getLocalizedCardName,
} from "../../utils/cardPresentation.js";
import { getCardTypeLabel } from "../../utils/cardTypes.js";
import { getCardLegality, legalityLabel } from "../../utils/formats.js";

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

const COLOR_ORDER = { W: 0, U: 1, B: 2, R: 3, G: 4 };

function getDeckType(card) {
  return card?.deck_type || "Other";
}

function getColorSortIndex(card) {
  const colors = card.color_identity || card.colors || [];
  if (colors.length === 0) return 100;
  if (colors.length === 1) return COLOR_ORDER[colors[0]] ?? 50;
  return 50 + Math.min(...colors.map((color) => COLOR_ORDER[color] ?? 50));
}

function hasUncertainCmc(card) {
  return /\{[XYZ]\}/i.test(card.mana_cost || "");
}

function compareDeckCards(a, b, language = "zh") {
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
      label: getCardTypeLabel(group.type, language),
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

export function getDeckCardImage(item, mode = "normal") {
  return getCardImage(item.card, { mode });
}

export function getCardCoverImage(item) {
  return getDeckCardImage(item, "art_crop");
}

export function getPreviewData(item, flipped = false, language = "zh") {
  if (!item) return null;

  const presentation = getCardPresentation(item.card, {
    language,
    faceIndex: flipped ? 1 : 0,
  });

  return {
    isDoubleFaced: presentation.isDoubleFaced,
    name: presentation.name,
    secondary_name: presentation.secondaryName,
    mana_cost: presentation.mana_cost,
    type_line: presentation.type_line,
    oracle_text: presentation.oracle_text,
    power: presentation.power,
    toughness: presentation.toughness,
    loyalty: presentation.loyalty,
    image_url: presentation.imageUrl,
    front_image_url: presentation.frontImageUrl,
    back_image_url: presentation.backImageUrl,
    front_name: presentation.frontName,
    back_name: presentation.backName,
  };
}
