import { apiFetch } from "../utils/apiFetch.js";

export function fetchSharedDeck(id) {
  return fetch(`/api/shared/decks/${id}`);
}

export function fetchSharedDeckCards(id) {
  return fetch(`/api/shared/decks/${id}/cards`);
}

export function updateDeck(id, body) {
  return apiFetch(`/api/decks/${id}`, { method: "PUT", body });
}

export function deleteDeck(id) {
  return apiFetch(`/api/decks/${id}`, { method: "DELETE" });
}

export function addDeckCard(id, body) {
  return apiFetch(`/api/decks/${id}/cards`, { method: "POST", body });
}

export function removeDeckCard(id, cardId, board) {
  const boardParam = board ? `?board=${board}` : "";
  return apiFetch(`/api/decks/${id}/cards/${cardId}${boardParam}`, { method: "DELETE" });
}

export function patchDeckCard(id, cardId, body) {
  return apiFetch(`/api/decks/${id}/cards/${cardId}`, { method: "PATCH", body });
}

export function analyzeDeck(id) {
  return apiFetch(`/api/decks/${id}/analyze`, { method: "POST", body: {} });
}

export function importDecklist(id, text, signal) {
  return apiFetch(`/api/decks/${id}/import`, { method: "POST", body: { text }, signal });
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
