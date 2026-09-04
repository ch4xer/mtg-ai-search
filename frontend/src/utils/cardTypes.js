const CARD_TYPES = [
  ["Creature", "Creature", "生物"],
  ["Instant", "Instant", "瞬间"],
  ["Sorcery", "Sorcery", "法术"],
  ["Enchantment", "Enchantment", "结界"],
  ["Artifact", "Artifact", "神器"],
  ["Land", "Land", "地"],
  ["Planeswalker", "Planeswalker", "鹏洛客"],
  ["Battle", "Battle", "战役"],
];

const LABELS = Object.fromEntries(
  [...CARD_TYPES, ["Other", "Other", "其他"]]
    .map(([value, en, zh]) => [value, { en, zh }]),
);

export function getSearchableCardTypes(language) {
  const labelIndex = language === "zh" ? 2 : 1;
  return CARD_TYPES.map((type) => ({ value: type[0], label: type[labelIndex] }));
}

export function getCardTypeLabel(type, language) {
  return LABELS[type]?.[language === "zh" ? "zh" : "en"]
    || LABELS.Other[language === "zh" ? "zh" : "en"];
}
