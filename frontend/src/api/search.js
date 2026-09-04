import { apiJson } from "../utils/apiFetch.js";

export function searchCards(query, options = {}) {
  const { limit = 60, offset = 0, searchId = null } = options;
  const body = { query, limit, offset };
  if (searchId) body.search_id = searchId;
  return apiJson("/api/search", {
    method: "POST",
    body,
  }, "Search failed");
}
