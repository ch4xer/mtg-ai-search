import { getImageUri } from "./cardImage.js";

const DOUBLE_FACED_LAYOUTS = new Set([
  "transform",
  "modal_dfc",
  "double_faced_token",
  "reversible_card",
]);

const DISPLAY_FIELDS = [
  "mana_cost",
  "type_line",
  "oracle_text",
  "flavor_text",
  "power",
  "toughness",
  "loyalty",
  "set_name",
];

function translatedField(card, field, faceIndex, fallbackToCard) {
  const translation = card?.zh;
  if (!translation) return "";

  const faceValue = translation.card_faces?.[faceIndex]?.[field];
  if (faceValue) return faceValue;
  return fallbackToCard ? (translation[field] || "") : "";
}

function englishField(card, faces, field, faceIndex, doubleFaced) {
  if (doubleFaced) return faces[faceIndex]?.[field] || "";
  return card?.[field] ?? faces[0]?.[field] ?? "";
}

export function hasDoubleFacedLayout(card) {
  return DOUBLE_FACED_LAYOUTS.has(card?.layout);
}

export function isDoubleFacedCard(card, faces = card?.card_faces || []) {
  return faces.length >= 2 && hasDoubleFacedLayout(card);
}

function getLocalizedCardField(card, field, language = "zh", faceIndex = null) {
  if (!card) return "";
  const hasFace = Number.isInteger(faceIndex);
  if (language === "zh") {
    const translated = translatedField(card, field, hasFace ? faceIndex : 0, true);
    if (translated) return translated;
  }
  if (hasFace && card.card_faces?.[faceIndex]?.[field]) return card.card_faces[faceIndex][field];
  return card[field] || "";
}

export function getLocalizedCardName(card, language = "zh", faceIndex = null) {
  return getLocalizedCardField(card, "name", language, faceIndex) || card?.name || "";
}

export function getCardImage(card, options = {}) {
  const {
    mode = "normal",
    faces = card?.card_faces || [],
    imageUris = card?.image_uris,
    faceIndex = 0,
  } = options;
  if (isDoubleFacedCard(card, faces)) return getImageUri(faces[faceIndex]?.image_uris, mode);
  return getImageUri(imageUris, mode) || getImageUri(faces[0]?.image_uris, mode);
}

export function getCardPresentation(card, options = {}) {
  const {
    language = "zh",
    faceIndex = 0,
    faces = card?.card_faces || [],
    imageUris = card?.image_uris,
    imageMode = "normal",
  } = options;
  const doubleFaced = isDoubleFacedCard(card, faces);
  const activeFaceIndex = doubleFaced && faceIndex === 1 ? 1 : 0;
  const readEnglish = (field) => englishField(card, faces, field, activeFaceIndex, doubleFaced);
  const readTranslated = (field) => (
    language === "zh"
      ? translatedField(card, field, activeFaceIndex, !doubleFaced)
      : ""
  );
  const readDisplay = (field) => readTranslated(field) || readEnglish(field);
  const englishName = readEnglish("name") || card?.name || "";
  const translatedName = readTranslated("name");
  const fields = Object.fromEntries(DISPLAY_FIELDS.map((field) => [field, readDisplay(field)]));
  const frontImageUrl = getCardImage(card, {
    mode: imageMode,
    faces,
    imageUris,
    faceIndex: 0,
  });
  const backImageUrl = doubleFaced
    ? getCardImage(card, { mode: imageMode, faces, imageUris, faceIndex: 1 })
    : "";

  return {
    ...fields,
    isDoubleFaced: doubleFaced,
    faceIndex: activeFaceIndex,
    name: translatedName || englishName,
    secondaryName: translatedName && translatedName !== englishName ? englishName : "",
    frontName: (language === "zh" ? translatedField(card, "name", 0, false) : "")
      || faces[0]?.name
      || card?.name
      || "",
    backName: (language === "zh" ? translatedField(card, "name", 1, false) : "")
      || faces[1]?.name
      || card?.name
      || "",
    imageUrl: activeFaceIndex === 1 ? backImageUrl : frontImageUrl,
    frontImageUrl,
    backImageUrl,
  };
}
