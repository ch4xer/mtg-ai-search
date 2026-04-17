import CardGrid from "./CardGrid.jsx";
import { useDiscoverCards } from "../hooks/useDiscoverCards.js";
import { useUserDecks } from "../hooks/useUserDecks.js";
import { useLanguage } from "../contexts/LanguageContext.jsx";

const COLOR_OPTIONS = [
  { value: "W", label: "White", symbolClass: "ms ms-w ms-cost" },
  { value: "U", label: "Blue", symbolClass: "ms ms-u ms-cost" },
  { value: "B", label: "Black", symbolClass: "ms ms-b ms-cost" },
  { value: "R", label: "Red", symbolClass: "ms ms-r ms-cost" },
  { value: "G", label: "Green", symbolClass: "ms ms-g ms-cost" },
];

const TYPE_OPTIONS_EN = [
  "Creature", "Instant", "Sorcery", "Enchantment",
  "Artifact", "Land", "Planeswalker", "Battle", "Kindred",
];

const TYPE_OPTIONS_ZH = [
  "生物", "瞬间", "法术", "结界",
  "神器", "地", "鹏洛客", "战斗", "族类",
];

const RARITY_OPTIONS_EN = [
  { value: "", label: "Any" },
  { value: "common", label: "Common" },
  { value: "uncommon", label: "Uncommon" },
  { value: "rare", label: "Rare" },
  { value: "mythic", label: "Mythic" },
];

const RARITY_OPTIONS_ZH = [
  { value: "", label: "任意" },
  { value: "common", label: "普通" },
  { value: "uncommon", label: "非普通" },
  { value: "rare", label: "稀有" },
  { value: "mythic", label: "秘稀" },
];

function DiscoverBrowser({ imageMode, onToggleImageMode, enabled = true }) {
  const { t, language } = useLanguage();
  const decks = useUserDecks();
  const {
    q, setQ,
    colors, setColors,
    types, setTypes,
    rarity, setRarity,
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
    subtypeSearch, setSubtypeSearch,
    filtersOpen, setFiltersOpen,
    toggleSet,
    clearAll,
    handleSearch,
    handlePageChange,
    showSubtypes,
    subtypeFacets,
    keywordFacets,
    allKeywords,
    hasFilters,
    totalPages,
  } = useDiscoverCards({ enabled });

  const TYPE_OPTIONS = language === 'zh' ? TYPE_OPTIONS_ZH : TYPE_OPTIONS_EN;
  const RARITY_OPTIONS = language === 'zh' ? RARITY_OPTIONS_ZH : RARITY_OPTIONS_EN;

  const handleKeywordSelect = (e) => {
    const value = e.target.value;
    if (value && !selectedKeywords.has(value)) {
      setSelectedKeywords(new Set([...selectedKeywords, value]));
    }
    e.target.value = "";
  };

  const removeKeyword = (keyword) => {
    const next = new Set(selectedKeywords);
    next.delete(keyword);
    setSelectedKeywords(next);
  };

  // Use allKeywords for the dropdown options
  const keywordOptions = allKeywords.length > 0 ? allKeywords : keywordFacets.map((kw) => kw.name);

  return (
    <>
      <div className="discover-search-bar">
        <div className="discover-search-row">
          <input
            type="text"
            className="discover-search-input"
            placeholder={t('searchPlaceholderDiscover')}
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

        <button className="discover-filter-toggle" onClick={() => setFiltersOpen(!filtersOpen)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="8" y1="12" x2="20" y2="12" />
            <line x1="12" y1="18" x2="20" y2="18" />
          </svg>
          {filtersOpen ? t('hideFilters') : t('filters')}
        </button>
      </div>

      <div className={`discover-filters-bar ${filtersOpen ? "open" : ""}`}>
        <div className="discover-filters-row">
          <div className="filter-group">
            <span className="filter-group-title">{t('colors')}</span>
            <div className="filter-color-inline">
              {COLOR_OPTIONS.map((c) => (
                <label key={c.value} className={`filter-color-check ${colors.has(c.value) ? "active" : ""}`} title={c.label}>
                  <input type="checkbox" checked={colors.has(c.value)} onChange={() => toggleSet(setColors, c.value)} />
                  <i className={c.symbolClass} aria-hidden="true" />
                </label>
              ))}
            </div>
          </div>

          <div className="filter-group">
            <span className="filter-group-title">{t('type')}</span>
            <select
              className="filter-select"
              value={types.size === 1 ? [...types][0] : ""}
              onChange={(e) => {
                if (e.target.value) {
                  setTypes(new Set([e.target.value]));
                  if (e.target.value !== "Creature" && e.target.value !== "生物") {
                    setSelectedSubtypes(new Set());
                    setSubtypeSearch("");
                  }
                } else {
                  setTypes(new Set());
                  setSelectedSubtypes(new Set());
                  setSubtypeSearch("");
                }
              }}
            >
              <option value="">{t('any')}</option>
              {TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          {showSubtypes && (
            <div className="filter-group filter-abilities-group">
              <span className="filter-group-title">{t('subtype')}</span>
              <div className="filter-abilities-wrapper">
                <input
                  type="text"
                  className="filter-text-input-small"
                  placeholder=""
                  value={subtypeSearch}
                  onChange={(e) => {
                    const val = e.target.value;
                    setSubtypeSearch(val);
                    const allSubs = facets.subtypes || [];
                    const match = allSubs.find(st => st.name.toLowerCase() === val.toLowerCase());
                    if (match && !selectedSubtypes.has(match.name)) {
                      setSelectedSubtypes(new Set([...selectedSubtypes, match.name]));
                      setSubtypeSearch("");
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && subtypeSearch.trim()) {
                      e.preventDefault();
                      if (!selectedSubtypes.has(subtypeSearch.trim())) {
                        setSelectedSubtypes(new Set([...selectedSubtypes, subtypeSearch.trim()]));
                      }
                      setSubtypeSearch("");
                    }
                  }}
                  list="subtype-list"
                />
                <datalist id="subtype-list">
                  {subtypeFacets.slice(0, 10).map((st) => (
                    <option key={st.name} value={st.name} />
                  ))}
                </datalist>
                {selectedSubtypes.size > 0 && (
                  <div className="filter-selected-keywords">
                    {[...selectedSubtypes].map((st) => (
                      <span key={st} className="filter-keyword-tag" onClick={() => {
                        const next = new Set(selectedSubtypes);
                        next.delete(st);
                        setSelectedSubtypes(next);
                      }}>
                        {st}
                        <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="filter-group">
            <span className="filter-group-title">{t('rarity')}</span>
            <select
              className="filter-select"
              value={rarity}
              onChange={(e) => setRarity(e.target.value)}
            >
              {RARITY_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>

          <div className="filter-group">
            <span className="filter-group-title">{t('cmc')}</span>
            <div className="filter-range-inline">
              <input
                type="number"
                className="filter-range-input-small"
                placeholder=""
                value={cmcMin}
                onChange={(e) => setCmcMin(e.target.value)}
                min="0"
                step="1"
              />
              <span className="filter-range-sep">-</span>
              <input
                type="number"
                className="filter-range-input-small"
                placeholder=""
                value={cmcMax}
                onChange={(e) => setCmcMax(e.target.value)}
                min="0"
                step="1"
              />
            </div>
          </div>

          <div className="filter-group">
            <span className="filter-group-title">{t('power')}</span>
            <div className="filter-range-inline">
              <input
                type="number"
                className="filter-range-input-small"
                placeholder=""
                value={powerMin}
                onChange={(e) => setPowerMin(e.target.value)}
                min="0"
              />
              <span className="filter-range-sep">-</span>
              <input
                type="number"
                className="filter-range-input-small"
                placeholder=""
                value={powerMax}
                onChange={(e) => setPowerMax(e.target.value)}
                min="0"
              />
            </div>
          </div>

          <div className="filter-group">
            <span className="filter-group-title">{t('toughness')}</span>
            <div className="filter-range-inline">
              <input
                type="number"
                className="filter-range-input-small"
                placeholder=""
                value={toughnessMin}
                onChange={(e) => setToughnessMin(e.target.value)}
                min="0"
              />
              <span className="filter-range-sep">-</span>
              <input
                type="number"
                className="filter-range-input-small"
                placeholder=""
                value={toughnessMax}
                onChange={(e) => setToughnessMax(e.target.value)}
                min="0"
              />
            </div>
          </div>

          <div className="filter-group filter-abilities-group">
            <span className="filter-group-title">{t('abilities')}</span>
            <div className="filter-abilities-wrapper">
              <select
                className="filter-select filter-abilities-select"
                value=""
                onChange={handleKeywordSelect}
              >
                <option value="">{t('addAbility')}</option>
                {keywordOptions.map((kw) => (
                  <option key={kw} value={kw} disabled={selectedKeywords.has(kw)}>
                    {kw}
                  </option>
                ))}
              </select>
              {selectedKeywords.size > 0 && (
                <div className="filter-selected-keywords">
                  {[...selectedKeywords].map((kw) => (
                    <span key={kw} className="filter-keyword-tag" onClick={() => removeKeyword(kw)}>
                      {kw}
                      <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          <label className="filter-checkbox-inline filter-playtest">
            <input type="checkbox" checked={includePlaytest} onChange={(e) => setIncludePlaytest(e.target.checked)} />
            <span>{t('playtest')}</span>
          </label>

          <button className="discover-clear-all-inline" onClick={clearAll} disabled={!hasFilters}>
            {t('clearAll')}
          </button>
        </div>
      </div>

      <div className="discover-results">
        {loading && <div className="loading"><div className="loading-spinner" /></div>}
        {!loading && results.length === 0 && <div className="no-results"><p>{t('noCardsFound')}</p></div>}
        {!loading && results.length > 0 && (
          <>
            <CardGrid cards={results} imageMode={imageMode} decks={decks} />
            {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onChange={handlePageChange} />}
          </>
        )}
      </div>
    </>
  );
}

function Pagination({ page, totalPages, onChange }) {
  const { t } = useLanguage();

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
      <button className="pagination-btn" onClick={() => onChange(page - 1)} disabled={page === 1}>{t('previous')}</button>
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
      <button className="pagination-btn" onClick={() => onChange(page + 1)} disabled={page === totalPages}>{t('next')}</button>
    </div>
  );
}

export default DiscoverBrowser;