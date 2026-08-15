import { apiFetch } from "../utils/apiFetch.js";

export function searchCards(query, options = {}) {
  const { limit = 60, offset = 0, searchId = null } = options;
  const body = { query, limit, offset };
  if (searchId) body.search_id = searchId;
  return apiFetch("/api/search", {
    method: "POST",
    body,
  });
}
