import CardGrid from "./CardGrid.jsx";
import { useDiscoverCards } from "../hooks/useDiscoverCards.js";
import { useUserDecks } from "../hooks/useUserDecks.js";

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

function DiscoverBrowser({ imageMode, onToggleImageMode, enabled = true }) {
  const decks = useUserDecks();
  const {
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
    handleSearch,
    handlePageChange,
    showSubtypes,
    subtypeFacets,
    keywordFacets,
    hasFilters,
    totalPages,
  } = useDiscoverCards({ enabled });

  return (
    <>
      <div className="discover-search-bar">
        <div className="discover-search-row">
          <input
            type="text"
            className="discover-search-input"
            placeholder="Search name, type, text..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
          />
          <button className="discover-search-go" onClick={handleSearch} disabled={loading}>
            {loading ? "..." : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            )}
          </button>
        </div>
      </div>

      <div className="discover-page">
      <button className="discover-filter-toggle" onClick={() => setFiltersOpen(!filtersOpen)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="4" y1="6" x2="20" y2="6" />
          <line x1="8" y1="12" x2="20" y2="12" />
          <line x1="12" y1="18" x2="20" y2="18" />
        </svg>
        {filtersOpen ? "Hide Filters" : "Show Filters"}
      </button>

      <aside className={`discover-sidebar ${filtersOpen ? "open" : ""}`}>
        <div className="discover-sidebar-header">
          <h3>Filters</h3>
          {hasFilters && (
            <button className="discover-clear-all" onClick={clearAll}>Clear All</button>
          )}
        </div>

        <FilterSection title="Colors" onClear={colors.size ? () => setColors(new Set()) : null}>
          <div className="filter-color-grid">
            {COLOR_OPTIONS.map((c) => {
              const count = facets.colors?.[c.value] || 0;
              return (
                <label key={c.value} className={`filter-color-item ${colors.has(c.value) ? "active" : ""}`}>
                  <input type="checkbox" checked={colors.has(c.value)} onChange={() => toggleSet(setColors, c.value)} />
                  <span className={`mana-dot ${c.className}`} />
                  <span className="filter-color-label">{c.label}</span>
                  <span className="facet-count">{count}</span>
                </label>
              );
            })}
          </div>
        </FilterSection>

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

        {showSubtypes && (
          <FilterSection title="Creature Type" onClear={selectedSubtypes.size ? () => { setSelectedSubtypes(new Set()); setSubtypeSearch(""); } : null}>
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
                  <input type="checkbox" checked={selectedSubtypes.has(st.name)} onChange={() => toggleSet(setSelectedSubtypes, st.name)} />
                  <span className="filter-checkbox-label">{st.name}</span>
                  <span className="facet-count">{st.count}</span>
                </label>
              ))}
              {subtypeFacets.length === 0 && <p className="filter-empty">No matching subtypes</p>}
            </div>
          </FilterSection>
        )}

        <FilterSection title="Rarity" onClear={rarities.size ? () => setRarities(new Set()) : null}>
          <div className="filter-checkbox-list">
            {RARITY_OPTIONS.map((r) => {
              const count = facets.rarities?.[r.value] || 0;
              return (
                <label key={r.value} className={`filter-checkbox-item ${rarities.has(r.value) ? "active" : ""}`}>
                  <input type="checkbox" checked={rarities.has(r.value)} onChange={() => toggleSet(setRarities, r.value)} />
                  <span className="filter-checkbox-label">{r.label}</span>
                  <span className="facet-count">{count}</span>
                </label>
              );
            })}
          </div>
        </FilterSection>

        <FilterSection title="Mana Value (CMC)" onClear={cmcMin !== "" || cmcMax !== "" ? () => { setCmcMin(""); setCmcMax(""); } : null}>
          <div className="filter-range">
            <input type="number" className="filter-range-input" placeholder={`Min${facets.cmc_range ? ` (${facets.cmc_range.min})` : ""}`} value={cmcMin} onChange={(e) => setCmcMin(e.target.value)} min="0" step="1" />
            <span className="filter-range-sep">&mdash;</span>
            <input type="number" className="filter-range-input" placeholder={`Max${facets.cmc_range ? ` (${facets.cmc_range.max})` : ""}`} value={cmcMax} onChange={(e) => setCmcMax(e.target.value)} min="0" step="1" />
          </div>
        </FilterSection>

        <FilterSection title="Power" onClear={powerMin !== "" || powerMax !== "" ? () => { setPowerMin(""); setPowerMax(""); } : null}>
          <div className="filter-range">
            <input type="number" className="filter-range-input" placeholder={`Min${facets.power_range ? ` (${facets.power_range.min})` : ""}`} value={powerMin} onChange={(e) => setPowerMin(e.target.value)} min="0" />
            <span className="filter-range-sep">&mdash;</span>
            <input type="number" className="filter-range-input" placeholder={`Max${facets.power_range ? ` (${facets.power_range.max})` : ""}`} value={powerMax} onChange={(e) => setPowerMax(e.target.value)} min="0" />
          </div>
        </FilterSection>

        <FilterSection title="Toughness" onClear={toughnessMin !== "" || toughnessMax !== "" ? () => { setToughnessMin(""); setToughnessMax(""); } : null}>
          <div className="filter-range">
            <input type="number" className="filter-range-input" placeholder={`Min${facets.toughness_range ? ` (${facets.toughness_range.min})` : ""}`} value={toughnessMin} onChange={(e) => setToughnessMin(e.target.value)} min="0" />
            <span className="filter-range-sep">&mdash;</span>
            <input type="number" className="filter-range-input" placeholder={`Max${facets.toughness_range ? ` (${facets.toughness_range.max})` : ""}`} value={toughnessMax} onChange={(e) => setToughnessMax(e.target.value)} min="0" />
          </div>
        </FilterSection>

        <FilterSection title="Abilities" onClear={selectedKeywords.size ? () => setSelectedKeywords(new Set()) : null}>
          <input type="text" className="filter-keyword-search" placeholder="Search abilities..." value={keywordSearch} onChange={(e) => setKeywordSearch(e.target.value)} />
          <div className="filter-checkbox-list filter-keyword-list">
            {keywordFacets.map((kw) => (
              <label key={kw.name} className={`filter-checkbox-item ${selectedKeywords.has(kw.name) ? "active" : ""}`}>
                <input type="checkbox" checked={selectedKeywords.has(kw.name)} onChange={() => toggleSet(setSelectedKeywords, kw.name)} />
                <span className="filter-checkbox-label">{kw.name}</span>
                <span className="facet-count">{kw.count}</span>
              </label>
            ))}
            {keywordFacets.length === 0 && <p className="filter-empty">No matching abilities</p>}
          </div>
        </FilterSection>

        <div className="filter-section">
          <label className="filter-checkbox-item">
            <input type="checkbox" checked={includePlaytest} onChange={(e) => setIncludePlaytest(e.target.checked)} />
            <span className="filter-checkbox-label">Include Playtest Cards</span>
          </label>
        </div>

        <button className="btn-accent discover-search-btn" onClick={handleSearch} disabled={loading}>
          {loading ? "Searching..." : "Search"}
        </button>
      </aside>

      <div className="discover-results">
        <div className="discover-results-header">
          <span className="discover-results-count">
            {loading ? "Searching..." : `${total.toLocaleString()} cards found`}
          </span>
        </div>

        {loading && <div className="loading"><div className="loading-spinner" /></div>}
        {!loading && results.length === 0 && <div className="no-results"><p>No cards found matching your filters</p></div>}
        {!loading && results.length > 0 && (
          <>
            <CardGrid cards={results} imageMode={imageMode} decks={decks} />
            {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onChange={handlePageChange} />}
          </>
        )}
      </div>
    </div>
    </>
  );
}

function FilterSection({ title, onClear, children }) {
  return (
    <div className="filter-section">
      <div className="filter-section-header">
        <span className="filter-section-title">{title}</span>
        {onClear && <button className="filter-clear-btn" onClick={onClear}>Clear</button>}
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
      <button className="pagination-btn" onClick={() => onChange(page - 1)} disabled={page === 1}>Previous</button>
      {getPages().map((p, idx) => (
        <button
          key={`${p}-${idx}`}
          className={`pagination-btn ${p === page ? "active" : ""} ${p === "..." ? "ellipsis" : ""}`}
          onClick={() => p !== "..." && onChange(p)}
          disabled={p === "..."}
        >
          {p}
        </button>
      ))}
      <button className="pagination-btn" onClick={() => onChange(page + 1)} disabled={page === totalPages}>Next</button>
    </div>
  );
}

export default DiscoverBrowser;
