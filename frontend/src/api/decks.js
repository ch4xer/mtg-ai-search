import { apiFetch, getAccessToken } from "../utils/apiFetch.js";

const USER_DECKS_CACHE_TTL = 60 * 1000;
const SHARED_DECK_CACHE_TTL = 2 * 60 * 1000;
const userDecksCache = new Map();
const sharedDeckCache = new Map();
const sharedDeckCardsCache = new Map();
const pendingUserDecks = new Map();
const pendingSharedDecks = new Map();
const pendingSharedDeckCards = new Map();
let userDecksCacheVersion = 0;
let sharedDeckCacheVersion = 0;

function now() {
  return Date.now();
}

function getUserDecksCacheKey() {
  return getAccessToken() || "anonymous";
}

function getCached(cache, key, ttl) {
  const entry = cache.get(key);
  if (!entry) return null;
  if (now() - entry.cachedAt > ttl) {
    cache.delete(key);
    return null;
  }
  return entry.data;
}

function setCached(cache, key, data) {
  cache.set(key, { data, cachedAt: now() });
}

function invalidateUserDecksCache() {
  userDecksCacheVersion += 1;
  userDecksCache.clear();
  pendingUserDecks.clear();
}

function invalidateSharedDeckCache(id) {
  if (!id) return;
  sharedDeckCacheVersion += 1;
  const key = String(id);
  sharedDeckCache.delete(key);
  sharedDeckCardsCache.delete(key);
  pendingSharedDecks.delete(key);
  pendingSharedDeckCards.delete(key);
}

function invalidateDeckMutationCaches(id) {
  invalidateUserDecksCache();
  invalidateSharedDeckCache(id);
}

async function invalidateOnSuccess(response, deckId) {
  if (response.ok) {
    invalidateDeckMutationCaches(deckId);
  }
  return response;
}

export async function fetchUserDecks({ force = false } = {}) {
  const key = getUserDecksCacheKey();
  if (!force) {
    const cached = getCached(userDecksCache, key, USER_DECKS_CACHE_TTL);
    if (cached) return cached;
    const pending = pendingUserDecks.get(key);
    if (pending) return pending;
  }

  const cacheVersion = userDecksCacheVersion;
  const request = apiFetch("/api/decks")
    .then(async (res) => {
      if (!res.ok) throw new Error("Failed to fetch decks");
      const data = await res.json();
      if (cacheVersion === userDecksCacheVersion) {
        setCached(userDecksCache, key, data);
      }
      return data;
    });

  pendingUserDecks.set(key, request);
  request.then(
    () => {
      if (pendingUserDecks.get(key) === request) pendingUserDecks.delete(key);
    },
    () => {
      if (pendingUserDecks.get(key) === request) pendingUserDecks.delete(key);
    }
  );
  return request;
}

function fetchSharedDeck(id) {
  return fetch(`/api/shared/decks/${id}`);
}

function fetchSharedDeckCards(id) {
  return fetch(`/api/shared/decks/${id}/cards`);
}

export async function fetchSharedDeckData(id, { force = false } = {}) {
  const key = String(id);
  if (!force) {
    const cached = getCached(sharedDeckCache, key, SHARED_DECK_CACHE_TTL);
    if (cached) return cached;
    const pending = pendingSharedDecks.get(key);
    if (pending) return pending;
  }

  const cacheVersion = sharedDeckCacheVersion;
  const request = fetchSharedDeck(id)
    .then(async (res) => {
      if (res.status === 404) {
        const error = new Error("Deck not found");
        error.status = 404;
        throw error;
      }
      if (!res.ok) throw new Error("Failed to fetch deck");
      const data = await res.json();
      if (cacheVersion === sharedDeckCacheVersion) {
        setCached(sharedDeckCache, key, data);
      }
      return data;
    });

  pendingSharedDecks.set(key, request);
  request.then(
    () => {
      if (pendingSharedDecks.get(key) === request) pendingSharedDecks.delete(key);
    },
    () => {
      if (pendingSharedDecks.get(key) === request) pendingSharedDecks.delete(key);
    }
  );
  return request;
}

export async function fetchSharedDeckCardsData(id, { force = false } = {}) {
  const key = String(id);
  if (!force) {
    const cached = getCached(sharedDeckCardsCache, key, SHARED_DECK_CACHE_TTL);
    if (cached) return cached;
    const pending = pendingSharedDeckCards.get(key);
    if (pending) return pending;
  }

  const cacheVersion = sharedDeckCacheVersion;
  const request = fetchSharedDeckCards(id)
    .then(async (res) => {
      if (!res.ok) throw new Error("Failed to fetch deck cards");
      const data = await res.json();
      if (cacheVersion === sharedDeckCacheVersion) {
        setCached(sharedDeckCardsCache, key, data);
      }
      return data;
    });

  pendingSharedDeckCards.set(key, request);
  request.then(
    () => {
      if (pendingSharedDeckCards.get(key) === request) pendingSharedDeckCards.delete(key);
    },
    () => {
      if (pendingSharedDeckCards.get(key) === request) pendingSharedDeckCards.delete(key);
    }
  );
  return request;
}

export async function createDeck(body) {
  const response = await apiFetch("/api/decks", { method: "POST", body });
  if (response.ok) invalidateUserDecksCache();
  return response;
}

export async function updateDeck(id, body) {
  const response = await apiFetch(`/api/decks/${id}`, { method: "PUT", body });
  return invalidateOnSuccess(response, id);
}

export async function patchDeckCover(id, coverImageUrl) {
  const response = await apiFetch(`/api/decks/${id}/cover`, {
    method: "PATCH",
    body: { cover_image_url: coverImageUrl },
  });
  return invalidateOnSuccess(response, id);
}

export async function deleteDeck(id) {
  const response = await apiFetch(`/api/decks/${id}`, { method: "DELETE" });
  return invalidateOnSuccess(response, id);
}

export async function addDeckCard(id, body) {
  const response = await apiFetch(`/api/decks/${id}/cards`, { method: "POST", body });
  return invalidateOnSuccess(response, id);
}

export async function removeDeckCard(id, cardId, board) {
  const boardParam = board ? `?board=${board}` : "";
  const response = await apiFetch(`/api/decks/${id}/cards/${cardId}${boardParam}`, { method: "DELETE" });
  return invalidateOnSuccess(response, id);
}

export async function patchDeckCard(id, cardId, body) {
  const response = await apiFetch(`/api/decks/${id}/cards/${cardId}`, { method: "PATCH", body });
  return invalidateOnSuccess(response, id);
}

export async function analyzeDeck(id) {
  const response = await apiFetch(`/api/decks/${id}/analyze`, { method: "POST", body: {} });
  return invalidateOnSuccess(response, id);
}

export async function importDecklist(id, text, signal) {
  const response = await apiFetch(`/api/decks/${id}/import`, { method: "POST", body: { text }, signal });
  return invalidateOnSuccess(response, id);
}

export function fetchDeckTextExport(id) {
  return fetch(`/api/shared/decks/${id}/export/text`);
}

export function fetchDeckPdfStream(id) {
  return fetch(`/api/shared/decks/${id}/export/stream`);
}

export function getDeckPdfDownloadUrl(id, exportId) {
  return `/api/shared/decks/${id}/export/download/${exportId}`;
}

export function fetchDeckImagesStream(id) {
  return fetch(`/api/shared/decks/${id}/export/images/stream`);
}

export function getDeckImagesDownloadUrl(id, exportId) {
  return `/api/shared/decks/${id}/export/images/download/${exportId}`;
}
