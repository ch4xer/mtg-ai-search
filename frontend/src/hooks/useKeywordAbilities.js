import { useEffect, useState } from "react";
import { apiJson } from "../utils/apiFetch.js";

let cachedCatalog = null;
let catalogRequest = null;

function indexKeywordAbilities(abilities) {
  return Object.fromEntries(
    (abilities || [])
      .filter((ability) => ability?.name && ability?.description_en)
      .map((ability) => [ability.name.trim().toLowerCase(), ability])
  );
}

async function loadKeywordAbilities() {
  if (cachedCatalog) return cachedCatalog;
  if (!catalogRequest) {
    catalogRequest = apiJson("/api/keyword-abilities", {}, "Keyword catalog request failed")
      .then((data) => {
        cachedCatalog = indexKeywordAbilities(data.abilities);
        return cachedCatalog;
      })
      .catch((error) => {
        catalogRequest = null;
        throw error;
      });
  }
  return catalogRequest;
}

export function useKeywordAbilities(enabled = true) {
  const [catalog, setCatalog] = useState(cachedCatalog || {});

  useEffect(() => {
    if (!enabled || cachedCatalog) {
      if (cachedCatalog) setCatalog(cachedCatalog);
      return undefined;
    }
    let active = true;
    loadKeywordAbilities()
      .then((result) => {
        if (active) setCatalog(result);
      })
      .catch((error) => console.error("Failed to fetch keyword explanations:", error));
    return () => {
      active = false;
    };
  }, [enabled]);

  return catalog;
}
