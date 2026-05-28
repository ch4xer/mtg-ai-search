import { apiFetch } from "../utils/apiFetch.js";

export function searchCards(query, options = {}) {
  const { limit = 60, offset = 0, searchId = null, includeZh = false } = options;
  const body = { query, limit, offset };
  if (searchId) body.search_id = searchId;
  if (includeZh) body.include_zh = true;
  return apiFetch("/api/search", {
    method: "POST",
    body,
  });
}
