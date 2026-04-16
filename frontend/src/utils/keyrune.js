const RARITY_CLASS_MAP = {
  common: "ss-common",
  uncommon: "ss-uncommon",
  rare: "ss-rare",
  mythic: "ss-mythic",
};

export function getSetIconClass(card) {
  const setCode = (card?.set || "").toLowerCase().trim();
  if (!setCode) return "";

  const rarity = (card?.rarity || "").toLowerCase().trim();
  const rarityClass = RARITY_CLASS_MAP[rarity] || "";

  return ["ss", `ss-${setCode}`, rarityClass].filter(Boolean).join(" ");
}
