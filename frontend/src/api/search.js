import { apiFetch } from "../utils/apiFetch.js";

export function searchCards(query) {
  return apiFetch("/api/search", {
    method: "POST",
    body: { query },
  });
}
