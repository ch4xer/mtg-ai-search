import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { apiJson } from "../utils/apiFetch.js";
import {
  buildExactSearchUrl,
  EMPTY_EXACT_SEARCH,
  exactSearchToRequest,
  hasExactSearch,
  parseSearchLocation,
} from "../utils/searchUrlState.js";

const PAGE_SIZE = 60;

export function useDiscoverCards({ enabled = true } = {}) {
  const location = useLocation();
  const navigate = useNavigate();
  const parsedLocation = useMemo(
    () => parseSearchLocation(location.pathname, location.search),
    [location.pathname, location.search],
  );
  const initial = parsedLocation.mode === "exact" ? parsedLocation.exact : EMPTY_EXACT_SEARCH;

  const [q, setQ] = useState(initial.q);
  const [colors, setColors] = useState(new Set(initial.colors));
  const [types, setTypes] = useState(new Set(initial.types));
  const [rarity, setRarity] = useState(initial.rarity);
  const [selectedSetCodes, setSelectedSetCodes] = useState(new Set(initial.setCodes));
  const [selectedKeywords, setSelectedKeywords] = useState(new Set(initial.keywords));
  const [selectedSubtypes, setSelectedSubtypes] = useState(new Set(initial.subtypes));
  const [functionTags, setFunctionTags] = useState(new Set(initial.functionTags));
  const [sourceCardId, setSourceCardId] = useState(initial.sourceCardId);
  const [cmcMin, setCmcMin] = useState(initial.cmcMin);
  const [cmcMax, setCmcMax] = useState(initial.cmcMax);
  const [powerMin, setPowerMin] = useState(initial.powerMin);
  const [powerMax, setPowerMax] = useState(initial.powerMax);
  const [toughnessMin, setToughnessMin] = useState(initial.toughnessMin);
  const [toughnessMax, setToughnessMax] = useState(initial.toughnessMax);
  const [page, setPage] = useState(initial.page);
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({});
  const [loading, setLoading] = useState(false);
  const [subtypeSearch, setSubtypeSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [allKeywords, setAllKeywords] = useState([]);
  const [allSets, setAllSets] = useState([]);
  const abortRef = useRef(null);

  useEffect(() => {
    if (!enabled) return;
    apiJson("/api/keywords", {}, "Failed to fetch keywords")
      .then((data) => setAllKeywords(data.keywords || []))
      .catch((err) => console.error("Failed to fetch keywords:", err));
    apiJson("/api/card-sets", {}, "Failed to fetch card sets")
      .then((data) => setAllSets(data.sets || []))
      .catch((err) => console.error("Failed to fetch card sets:", err));
  }, [enabled]);

  const fetchResults = useCallback(async (searchState) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const data = await apiJson("/api/discover", {
        method: "POST",
        body: exactSearchToRequest(searchState),
        signal: controller.signal,
      }, "Discover failed");
      setResults(data.results || []);
      setTotal(data.total || 0);
      setFacets(data.facets || {});
    } catch (err) {
      if (err.name !== "AbortError") {
        setResults([]);
        setTotal(0);
        setFacets({});
      }
    } finally {
      if (abortRef.current === controller) setLoading(false);
    }
  }, []);

  const applyUrlState = useCallback((state) => {
    setQ(state.q);
    setColors(new Set(state.colors));
    setTypes(new Set(state.types));
    setRarity(state.rarity);
    setSelectedSetCodes(new Set(state.setCodes));
    setSelectedKeywords(new Set(state.keywords));
    setSelectedSubtypes(new Set(state.subtypes));
    setFunctionTags(new Set(state.functionTags));
    setSourceCardId(state.sourceCardId);
    setCmcMin(state.cmcMin);
    setCmcMax(state.cmcMax);
    setPowerMin(state.powerMin);
    setPowerMax(state.powerMax);
    setToughnessMin(state.toughnessMin);
    setToughnessMax(state.toughnessMax);
    setSubtypeSearch("");
    setPage(state.page);
  }, []);

  useEffect(() => {
    if (!enabled || parsedLocation.mode !== "exact") {
      abortRef.current?.abort();
      setLoading(false);
      return;
    }
    const state = parsedLocation.exact;
    applyUrlState(state);
    if (hasExactSearch(state)) {
      fetchResults(state);
    } else {
      setResults([]);
      setTotal(0);
      setFacets({});
    }
  }, [enabled, parsedLocation, applyUrlState, fetchResults]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const currentDraft = useCallback((pageNumber = page) => ({
    q,
    colors: [...colors],
    types: [...types],
    rarity,
    setCodes: [...selectedSetCodes],
    keywords: [...selectedKeywords],
    subtypes: [...selectedSubtypes],
    functionTags: [...functionTags],
    sourceCardId,
    cmcMin,
    cmcMax,
    powerMin,
    powerMax,
    toughnessMin,
    toughnessMax,
    page: pageNumber,
  }), [q, colors, types, rarity, selectedSetCodes, selectedKeywords, selectedSubtypes, functionTags, sourceCardId, cmcMin, cmcMax, powerMin, powerMax, toughnessMin, toughnessMax, page]);

  const commitState = useCallback((state) => {
    const nextUrl = buildExactSearchUrl(state);
    const currentUrl = `${location.pathname}${location.search}`;
    if (nextUrl === currentUrl) fetchResults(state);
    else navigate(nextUrl);
  }, [fetchResults, location.pathname, location.search, navigate]);

  const handleSearch = useCallback(() => {
    const state = currentDraft(1);
    setPage(1);
    commitState(state);
  }, [commitState, currentDraft]);

  const handlePageChange = useCallback((newPage) => {
    const state = currentDraft(newPage);
    setPage(newPage);
    commitState(state);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [commitState, currentDraft]);

  const toggleSet = useCallback((setter, value) => {
    setter((previous) => {
      const next = new Set(previous);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    setQ("");
    setColors(new Set());
    setTypes(new Set());
    setRarity("");
    setSelectedSetCodes(new Set());
    setSelectedKeywords(new Set());
    setSelectedSubtypes(new Set());
    setFunctionTags(new Set());
    setSourceCardId(null);
    setSubtypeSearch("");
    setCmcMin("");
    setCmcMax("");
    setPowerMin("");
    setPowerMax("");
    setToughnessMin("");
    setToughnessMax("");
  }, []);

  const showSubtypes = types.has("Creature");
  const subtypeFacets = (facets.subtypes || []).filter(
    (subtype) => subtype.name.toLowerCase().includes(subtypeSearch.toLowerCase()),
  );
  const activeFilterCount = [
    colors.size > 0,
    types.size > 0,
    selectedSubtypes.size > 0,
    functionTags.size > 0,
    Boolean(rarity),
    selectedSetCodes.size > 0,
    cmcMin !== "" || cmcMax !== "",
    powerMin !== "" || powerMax !== "",
    toughnessMin !== "" || toughnessMax !== "",
    selectedKeywords.size > 0,
  ].filter(Boolean).length;
  const hasFilters = Boolean(q.trim() || activeFilterCount > 0);

  return {
    q, setQ,
    colors, setColors,
    types, setTypes,
    rarity, setRarity,
    selectedSetCodes, setSelectedSetCodes,
    selectedKeywords, setSelectedKeywords,
    selectedSubtypes, setSelectedSubtypes,
    functionTags, setFunctionTags,
    cmcMin, setCmcMin,
    cmcMax, setCmcMax,
    powerMin, setPowerMin,
    powerMax, setPowerMax,
    toughnessMin, setToughnessMin,
    toughnessMax, setToughnessMax,
    page,
    results,
    total,
    facets,
    loading,
    subtypeSearch, setSubtypeSearch,
    filtersOpen, setFiltersOpen,
    toggleSet,
    clearAll,
    handleSearch,
    handlePageChange,
    showSubtypes,
    subtypeFacets,
    keywordFacets: facets.keywords || [],
    allKeywords,
    allSets,
    hasFilters,
    activeFilterCount,
    totalPages: Math.ceil(total / PAGE_SIZE),
  };
}
