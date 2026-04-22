import { apiFetch } from "../utils/apiFetch.js";

export function fetchCardPrints(cardId) {
  return apiFetch(`/api/cards/${cardId}/prints`);
}

export function normalizePrints(data) {
  return (data.prints || [])
    .map((print) => {
      const collectorNumber = print.image_collector_number;
      const imageSetName = print.image_set_name;
      return {
        id: print.id,
        normal: print.image_normal || print.card_faces?.[0]?.image_uris?.normal,
        image_uris: {
          small: print.image_small,
          normal: print.image_normal,
          large: print.image_large,
          png: print.image_png,
          art_crop: print.image_art_crop,
          border_crop: print.image_border_crop,
        },
        card_faces: print.card_faces,
        setName: imageSetName,
        set: print.image_set_code,
        collectorNumber,
        label: `${imageSetName}${collectorNumber ? ` #${collectorNumber}` : ""}`,
        rarity: print.rarity,
        artist: print.artist,
      };
    })
    .filter((print) => print.normal);
}
