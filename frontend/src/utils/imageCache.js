const imageCache = new Map();
const MAX_CACHED_IMAGES = 160;

function trimImageCache() {
  if (imageCache.size <= MAX_CACHED_IMAGES) return;

  const overflow = imageCache.size - MAX_CACHED_IMAGES;
  const oldest = [...imageCache.entries()]
    .sort(([, a], [, b]) => a.lastUsed - b.lastUsed)
    .slice(0, overflow);

  for (const [src] of oldest) {
    imageCache.delete(src);
  }
}

export function cacheImage(src) {
  if (!src || typeof window === "undefined" || typeof Image === "undefined") return;

  const existing = imageCache.get(src);
  if (existing) {
    existing.lastUsed = Date.now();
    return;
  }

  const image = new Image();
  image.decoding = "async";
  image.src = src;
  imageCache.set(src, { image, lastUsed: Date.now() });
  trimImageCache();
}

export function isImageCached(src) {
  if (!src) return false;
  const existing = imageCache.get(src);
  if (!existing) return false;
  existing.lastUsed = Date.now();
  return true;
}

export function cacheImages(srcs, limit = srcs.length) {
  srcs.slice(0, limit).forEach(cacheImage);
}
