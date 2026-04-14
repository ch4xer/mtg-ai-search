import { useCallback, useEffect, useRef, useState } from "react";

const PAGE_SIZE = 60;

export function useDiscoverCards({ enabled = true } = {}) {
  const [q, setQ] = useState("");
  const [colors, setColors] = useState(new Set());
  const [types, setTypes] = useState(new Set());
  const [rarities, setRarities] = useState(new Set());
  const [selectedKeywords, setSelectedKeywords] = useState(new Set());
  const [selectedSubtypes, setSelectedSubtypes] = useState(new Set());
  const [includePlaytest, setIncludePlaytest] = useState(false);
  const [cmcMin, setCmcMin] = useState("");
  const [cmcMax, setCmcMax] = useState("");
  const [powerMin, setPowerMin] = useState("");
  const [powerMax, setPowerMax] = useState("");
  const [toughnessMin, setToughnessMin] = useState("");
  const [toughnessMax, setToughnessMax] = useState("");
  const [page, setPage] = useState(1);
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({});
  const [loading, setLoading] = useState(false);
  const [keywordSearch, setKeywordSearch] = useState("");
  const [subtypeSearch, setSubtypeSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const abortRef = useRef(null);
  const debounceRef = useRef(null);

  const buildBody = useCallback((pageNum) => {
    const body = { page: pageNum, page_size: PAGE_SIZE };
    if (q.trim()) body.q = q.trim();
    if (colors.size > 0) body.colors = [...colors];
    if (types.size > 0) body.types = [...types];
    if (rarities.size > 0) body.rarities = [...rarities];
    if (selectedKeywords.size > 0) body.keywords = [...selectedKeywords];
    if (selectedSubtypes.size > 0) body.subtypes = [...selectedSubtypes];
    if (includePlaytest) body.include_playtest = true;
    if (cmcMin !== "") body.cmc_min = parseFloat(cmcMin);
    if (cmcMax !== "") body.cmc_max = parseFloat(cmcMax);
    if (powerMin !== "") body.power_min = parseFloat(powerMin);
    if (powerMax !== "") body.power_max = parseFloat(powerMax);
    if (toughnessMin !== "") body.toughness_min = parseFloat(toughnessMin);
    if (toughnessMax !== "") body.toughness_max = parseFloat(toughnessMax);
    return body;
  }, [q, colors, types, rarities, selectedKeywords, selectedSubtypes, includePlaytest, cmcMin, cmcMax, powerMin, powerMax, toughnessMin, toughnessMax]);

  const fetchResults = useCallback(async (pageNum) => {
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    try {
      const res = await fetch("/api/discover", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildBody(pageNum)),
        signal: controller.signal,
      });
      const data = await res.json();
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
      setLoading(false);
    }
  }, [buildBody]);

  useEffect(() => {
    if (!enabled) return undefined;
    setPage(1);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchResults(1), 300);
    return () => clearTimeout(debounceRef.current);
  }, [enabled, q, colors, types, rarities, selectedKeywords, selectedSubtypes, includePlaytest, cmcMin, cmcMax, powerMin, powerMax, toughnessMin, toughnessMax, fetchResults]);

  useEffect(() => {
    if (!enabled && abortRef.current) {
      abortRef.current.abort();
      setLoading(false);
    }
  }, [enabled]);

  const toggleSet = useCallback((setter, value) => {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    setQ("");
    setColors(new Set());
    setTypes(new Set());
    setRarities(new Set());
    setSelectedKeywords(new Set());
    setSelectedSubtypes(new Set());
    setSubtypeSearch("");
    setIncludePlaytest(false);
    setCmcMin("");
    setCmcMax("");
    setPowerMin("");
    setPowerMax("");
    setToughnessMin("");
    setToughnessMax("");
    setKeywordSearch("");
  }, []);

  const handlePageChange = useCallback((newPage) => {
    setPage(newPage);
    fetchResults(newPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [fetchResults]);

  const showSubtypes = types.has("Creature");
  const subtypeFacets = (facets.subtypes || []).filter(
    (st) => st.name.toLowerCase().includes(subtypeSearch.toLowerCase())
  );
  const keywordFacets = (facets.keywords || []).filter(
    (kw) => kw.name.toLowerCase().includes(keywordSearch.toLowerCase())
  );
  const hasFilters = q || colors.size || types.size || rarities.size || selectedKeywords.size || selectedSubtypes.size
    || cmcMin !== "" || cmcMax !== "" || powerMin !== "" || powerMax !== ""
    || toughnessMin !== "" || toughnessMax !== "";

  return {
    q, setQ,
    colors, setColors,
    types, setTypes,
    rarities, setRarities,
    selectedKeywords, setSelectedKeywords,
    selectedSubtypes, setSelectedSubtypes,
    includePlaytest, setIncludePlaytest,
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
    keywordSearch, setKeywordSearch,
    subtypeSearch, setSubtypeSearch,
    filtersOpen, setFiltersOpen,
    toggleSet,
    clearAll,
    handlePageChange,
    showSubtypes,
    subtypeFacets,
    keywordFacets,
    hasFilters,
    totalPages: Math.ceil(total / PAGE_SIZE),
  };
}
