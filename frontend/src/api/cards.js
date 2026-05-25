import { apiFetch } from "../utils/apiFetch.js";
import { cacheImages } from "../utils/imageCache.js";

const PRINTS_CACHE_TTL = 30 * 60 * 1000;
const PRINTS_CACHE_LIMIT = 80;
const PRINT_IMAGE_PRELOAD_LIMIT = 16;
const printsCache = new Map();
const pendingPrintRequests = new Map();

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
        thumbnail: print.image_small
          || print.card_faces?.[0]?.image_uris?.small
          || print.image_normal
          || print.card_faces?.[0]?.image_uris?.normal,
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

function getCachedPrints(cardId) {
  const cached = printsCache.get(cardId);
  if (!cached) return null;

  if (Date.now() - cached.cachedAt > PRINTS_CACHE_TTL) {
    printsCache.delete(cardId);
    return null;
  }

  cached.lastUsed = Date.now();
  return cached.prints;
}

function setCachedPrints(cardId, prints) {
  printsCache.set(cardId, {
    prints,
    cachedAt: Date.now(),
    lastUsed: Date.now(),
  });

  if (printsCache.size <= PRINTS_CACHE_LIMIT) return;

  const [oldestKey] = [...printsCache.entries()]
    .sort(([, a], [, b]) => a.lastUsed - b.lastUsed)[0];
  printsCache.delete(oldestKey);
}

function warmPrintImageCache(prints) {
  if (typeof window === "undefined") return;

  const urls = prints.map((print) => print.thumbnail || print.normal);
  window.setTimeout(() => {
    cacheImages(urls, PRINT_IMAGE_PRELOAD_LIMIT);
  }, 0);
}

export async function fetchNormalizedCardPrints(cardId) {
  if (!cardId) return [];

  const cacheKey = String(cardId);
  const cached = getCachedPrints(cacheKey);
  if (cached) return cached;

  const pending = pendingPrintRequests.get(cacheKey);
  if (pending) return pending;

  const request = (async () => {
    const res = await fetchCardPrints(cacheKey);
    if (!res.ok) {
      throw new Error(`Failed to fetch card prints: ${res.status}`);
    }

    const data = await res.json();
    const prints = normalizePrints(data);
    setCachedPrints(cacheKey, prints);
    warmPrintImageCache(prints);
    return prints;
  })().finally(() => {
    pendingPrintRequests.delete(cacheKey);
  });

  pendingPrintRequests.set(cacheKey, request);
  return request;
}
