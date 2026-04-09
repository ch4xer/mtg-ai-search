import { useState, useEffect, useRef, useCallback } from "react";
import CardGrid from "../components/CardGrid.jsx";
import { useAuth } from "../contexts/AuthContext.jsx";
import { apiFetch } from "../utils/apiFetch.js";

const COLOR_OPTIONS = [
  { value: "W", label: "White", className: "mana-white" },
  { value: "U", label: "Blue", className: "mana-blue" },
  { value: "B", label: "Black", className: "mana-black" },
  { value: "R", label: "Red", className: "mana-red" },
  { value: "G", label: "Green", className: "mana-green" },
];

const TYPE_OPTIONS = [
  "Creature", "Instant", "Sorcery", "Enchantment",
  "Artifact", "Land", "Planeswalker", "Battle", "Kindred",
];

const RARITY_OPTIONS = [
  { value: "common", label: "Common" },
  { value: "uncommon", label: "Uncommon" },
  { value: "rare", label: "Rare" },
  { value: "mythic", label: "Mythic" },
];

const PAGE_SIZE = 60;

function DiscoverPage({ imageMode, onToggleImageMode }) {
  // Filter state
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

  // Results state
  const [page, setPage] = useState(1);
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({});
  const [loading, setLoading] = useState(false);
  const [decks, setDecks] = useState([]);
  const [keywordSearch, setKeywordSearch] = useState("");
  const [subtypeSearch, setSubtypeSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);

  const { user } = useAuth();
  const abortRef = useRef(null);
  const debounceRef = useRef(null);

  // Load user decks
  useEffect(() => {
    if (user) {
      apiFetch("/api/decks")
        .then((res) => (res.ok ? res.json() : []))
        .then(setDecks)
        .catch(() => {});
    } else {
      setDecks([]);
    }
  }, [user]);

  // Build request body from current filters
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

  // Fetch results
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
        console.error("Discover failed:", err);
        setResults([]);
        setTotal(0);
      }
    } finally {
      setLoading(false);
    }
  }, [buildBody]);

  // Debounced search on any filter change — reset to page 1
  useEffect(() => {
    setPage(1);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchResults(1), 300);
    return () => clearTimeout(debounceRef.current);
  }, [q, colors, types, rarities, selectedKeywords, selectedSubtypes, includePlaytest, cmcMin, cmcMax, powerMin, powerMax, toughnessMin, toughnessMax]);

  // Page change — fetch immediately
  const handlePageChange = (newPage) => {
    setPage(newPage);
    fetchResults(newPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Toggle helpers
  const toggleSet = (setter, value) => {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  };

  const clearAll = () => {
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
  };

  const hasFilters = q || colors.size || types.size || rarities.size || selectedKeywords.size || selectedSubtypes.size
    || cmcMin !== "" || cmcMax !== "" || powerMin !== "" || powerMax !== ""
    || toughnessMin !== "" || toughnessMax !== "";

  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Clear subtypes when Creature is deselected
  const showSubtypes = types.has("Creature");

  // Filter subtype facets by search text
  const subtypeFacets = (facets.subtypes || []).filter(
    (st) => st.name.toLowerCase().includes(subtypeSearch.toLowerCase())
  );

  // Filter keyword facets by search text
  const keywordFacets = (facets.keywords || []).filter(
    (kw) => kw.name.toLowerCase().includes(keywordSearch.toLowerCase())
  );

  return (
    <div className="discover-page">
      {/* Mobile filter toggle */}
      <button className="discover-filter-toggle" onClick={() => setFiltersOpen(!filtersOpen)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="4" y1="6" x2="20" y2="6" />
          <line x1="8" y1="12" x2="20" y2="12" />
          <line x1="12" y1="18" x2="20" y2="18" />
        </svg>
        {filtersOpen ? "Hide Filters" : "Show Filters"}
      </button>

      {/* Sidebar */}
      <aside className={`discover-sidebar ${filtersOpen ? "open" : ""}`}>
        <div className="discover-sidebar-header">
          <h3>Filters</h3>
          {hasFilters && (
            <button className="discover-clear-all" onClick={clearAll}>Clear All</button>
          )}
        </div>

        {/* Keyword Search */}
        <div className="filter-section">
          <div className="filter-section-title">Keyword Search</div>
          <input
            type="text"
            className="discover-search-input"
            placeholder="Search name, type, text..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>

        {/* Colors */}
        <FilterSection title="Colors" onClear={colors.size ? () => setColors(new Set()) : null}>
          <div className="filter-color-grid">
            {COLOR_OPTIONS.map((c) => {
              const count = facets.colors?.[c.value] || 0;
              return (
                <label key={c.value} className={`filter-color-item ${colors.has(c.value) ? "active" : ""}`}>
                  <input
                    type="checkbox"
                    checked={colors.has(c.value)}
                    onChange={() => toggleSet(setColors, c.value)}
                  />
                  <span className={`mana-dot ${c.className}`} />
                  <span className="filter-color-label">{c.label}</span>
                  <span className="facet-count">{count}</span>
                </label>
              );
            })}
          </div>
        </FilterSection>

        {/* Card Type */}
        <FilterSection title="Card Type" onClear={types.size ? () => { setTypes(new Set()); setSelectedSubtypes(new Set()); setSubtypeSearch(""); } : null}>
          <div className="filter-checkbox-list">
            {TYPE_OPTIONS.map((t) => {
              const count = facets.types?.[t] || 0;
              return (
                <label key={t} className={`filter-checkbox-item ${types.has(t) ? "active" : ""}`}>
                  <input
                    type="checkbox"
                    checked={types.has(t)}
                    onChange={() => {
                      toggleSet(setTypes, t);
                      if (t === "Creature" && types.has("Creature")) {
                        setSelectedSubtypes(new Set());
                        setSubtypeSearch("");
                      }
                    }}
                  />
                  <span className="filter-checkbox-label">{t}</span>
                  <span className="facet-count">{count}</span>
                </label>
              );
            })}
          </div>
        </FilterSection>

        {/* Subtypes — shown when Creature is selected */}
        {showSubtypes && (
          <FilterSection
            title="Creature Type"
            onClear={selectedSubtypes.size ? () => { setSelectedSubtypes(new Set()); setSubtypeSearch(""); } : null}
          >
            <input
              type="text"
              className="filter-keyword-search"
              placeholder="Search subtypes..."
              value={subtypeSearch}
              onChange={(e) => setSubtypeSearch(e.target.value)}
            />
            <div className="filter-checkbox-list filter-keyword-list">
              {subtypeFacets.map((st) => (
                <label key={st.name} className={`filter-checkbox-item ${selectedSubtypes.has(st.name) ? "active" : ""}`}>
                  <input
                    type="checkbox"
                    checked={selectedSubtypes.has(st.name)}
                    onChange={() => toggleSet(setSelectedSubtypes, st.name)}
                  />
                  <span className="filter-checkbox-label">{st.name}</span>
                  <span className="facet-count">{st.count}</span>
                </label>
              ))}
              {subtypeFacets.length === 0 && (
                <p className="filter-empty">No matching subtypes</p>
              )}
            </div>
          </FilterSection>
        )}

        {/* Rarity */}
        <FilterSection title="Rarity" onClear={rarities.size ? () => setRarities(new Set()) : null}>
          <div className="filter-checkbox-list">
            {RARITY_OPTIONS.map((r) => {
              const count = facets.rarities?.[r.value] || 0;
              return (
                <label key={r.value} className={`filter-checkbox-item ${rarities.has(r.value) ? "active" : ""}`}>
                  <input
                    type="checkbox"
                    checked={rarities.has(r.value)}
                    onChange={() => toggleSet(setRarities, r.value)}
                  />
                  <span className="filter-checkbox-label">{r.label}</span>
                  <span className="facet-count">{count}</span>
                </label>
              );
            })}
          </div>
        </FilterSection>

        {/* CMC Range */}
        <FilterSection
          title="Mana Value (CMC)"
          onClear={cmcMin !== "" || cmcMax !== "" ? () => { setCmcMin(""); setCmcMax(""); } : null}
        >
          <div className="filter-range">
            <input
              type="number"
              className="filter-range-input"
              placeholder={`Min${facets.cmc_range ? ` (${facets.cmc_range.min})` : ""}`}
              value={cmcMin}
              onChange={(e) => setCmcMin(e.target.value)}
              min="0"
              step="1"
            />
            <span className="filter-range-sep">&mdash;</span>
            <input
              type="number"
              className="filter-range-input"
              placeholder={`Max${facets.cmc_range ? ` (${facets.cmc_range.max})` : ""}`}
              value={cmcMax}
              onChange={(e) => setCmcMax(e.target.value)}
              min="0"
              step="1"
            />
          </div>
        </FilterSection>

        {/* Power Range */}
        <FilterSection
          title="Power"
          onClear={powerMin !== "" || powerMax !== "" ? () => { setPowerMin(""); setPowerMax(""); } : null}
        >
          <div className="filter-range">
            <input
              type="number"
              className="filter-range-input"
              placeholder={`Min${facets.power_range ? ` (${facets.power_range.min})` : ""}`}
              value={powerMin}
              onChange={(e) => setPowerMin(e.target.value)}
              min="0"
            />
            <span className="filter-range-sep">&mdash;</span>
            <input
              type="number"
              className="filter-range-input"
              placeholder={`Max${facets.power_range ? ` (${facets.power_range.max})` : ""}`}
              value={powerMax}
              onChange={(e) => setPowerMax(e.target.value)}
              min="0"
            />
          </div>
        </FilterSection>

        {/* Toughness Range */}
        <FilterSection
          title="Toughness"
          onClear={toughnessMin !== "" || toughnessMax !== "" ? () => { setToughnessMin(""); setToughnessMax(""); } : null}
        >
          <div className="filter-range">
            <input
              type="number"
              className="filter-range-input"
              placeholder={`Min${facets.toughness_range ? ` (${facets.toughness_range.min})` : ""}`}
              value={toughnessMin}
              onChange={(e) => setToughnessMin(e.target.value)}
              min="0"
            />
            <span className="filter-range-sep">&mdash;</span>
            <input
              type="number"
              className="filter-range-input"
              placeholder={`Max${facets.toughness_range ? ` (${facets.toughness_range.max})` : ""}`}
              value={toughnessMax}
              onChange={(e) => setToughnessMax(e.target.value)}
              min="0"
            />
          </div>
        </FilterSection>

        {/* Keyword Abilities */}
        <FilterSection
          title="Abilities"
          onClear={selectedKeywords.size ? () => setSelectedKeywords(new Set()) : null}
        >
          <input
            type="text"
            className="filter-keyword-search"
            placeholder="Search abilities..."
            value={keywordSearch}
            onChange={(e) => setKeywordSearch(e.target.value)}
          />
          <div className="filter-checkbox-list filter-keyword-list">
            {keywordFacets.map((kw) => (
              <label key={kw.name} className={`filter-checkbox-item ${selectedKeywords.has(kw.name) ? "active" : ""}`}>
                <input
                  type="checkbox"
                  checked={selectedKeywords.has(kw.name)}
                  onChange={() => toggleSet(setSelectedKeywords, kw.name)}
                />
                <span className="filter-checkbox-label">{kw.name}</span>
                <span className="facet-count">{kw.count}</span>
              </label>
            ))}
            {keywordFacets.length === 0 && (
              <p className="filter-empty">No matching abilities</p>
            )}
          </div>
        </FilterSection>

        {/* Include playtest toggle */}
        <div className="filter-section">
          <label className="filter-checkbox-item">
            <input
              type="checkbox"
              checked={includePlaytest}
              onChange={(e) => setIncludePlaytest(e.target.checked)}
            />
            <span className="filter-checkbox-label">Include Playtest Cards</span>
          </label>
        </div>
      </aside>

      {/* Results */}
      <div className="discover-results">
        <div className="discover-results-header">
          <span className="discover-results-count">
            {loading ? "Searching..." : `${total.toLocaleString()} cards found`}
          </span>
          <button
            type="button"
            className="image-mode-btn"
            onClick={onToggleImageMode}
            title={imageMode === "border_crop" ? "Art Mode" : "Card Mode"}
          >
            {imageMode === "border_crop" ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <polyline points="21 15 16 10 5 21" />
              </svg>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="3" width="20" height="18" rx="2" ry="2" />
                <line x1="2" y1="7" x2="22" y2="7" />
                <line x1="2" y1="17" x2="22" y2="17" />
              </svg>
            )}
          </button>
        </div>

        {loading && (
          <div className="loading">
            <div className="loading-spinner" />
          </div>
        )}

        {!loading && results.length === 0 && (
          <div className="no-results">
            <p>No cards found matching your filters</p>
          </div>
        )}

        {!loading && results.length > 0 && (
          <>
            <CardGrid cards={results} imageMode={imageMode} decks={decks} />
            {totalPages > 1 && (
              <Pagination page={page} totalPages={totalPages} onChange={handlePageChange} />
            )}
          </>
        )}
      </div>
    </div>
  );
}

function FilterSection({ title, onClear, children }) {
  return (
    <div className="filter-section">
      <div className="filter-section-header">
        <span className="filter-section-title">{title}</span>
        {onClear && (
          <button className="filter-clear-btn" onClick={onClear}>Clear</button>
        )}
      </div>
      {children}
    </div>
  );
}

function Pagination({ page, totalPages, onChange }) {
  const getPages = () => {
    const pages = [];
    const delta = 2;
    const start = Math.max(2, page - delta);
    const end = Math.min(totalPages - 1, page + delta);

    pages.push(1);
    if (start > 2) pages.push("...");
    for (let i = start; i <= end; i++) pages.push(i);
    if (end < totalPages - 1) pages.push("...");
    if (totalPages > 1) pages.push(totalPages);
    return pages;
  };

  return (
    <div className="discover-pagination">
      <button
        className="pagination-btn"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        Prev
      </button>
      {getPages().map((p, i) =>
        p === "..." ? (
          <span key={`ellipsis-${i}`} className="pagination-ellipsis">&hellip;</span>
        ) : (
          <button
            key={p}
            className={`pagination-btn ${p === page ? "active" : ""}`}
            onClick={() => onChange(p)}
          >
            {p}
          </button>
        )
      )}
      <button
        className="pagination-btn"
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
      >
        Next
      </button>
    </div>
  );
}

export default DiscoverPage;
