import { useEffect, useRef, useState } from "react";
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
  "Artifact", "Land", "Planeswalker", "Battle",
];

const TYPE_OPTIONS_ZH = [
  "生物", "瞬间", "法术", "结界",
  "神器", "地", "鹏洛客", "战斗",
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

const EXACT_MATCH_FEATURES = [
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 5h16" />
        <path d="M7 12h10" />
        <path d="M10 19h4" />
      </svg>
    ),
    titleKey: "exactFeatureFiltersTitle",
    descKey: "exactFeatureFiltersDesc",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="8" />
        <path d="M12 8v4l3 2" />
      </svg>
    ),
    titleKey: "exactFeatureDeterministicTitle",
    descKey: "exactFeatureDeterministicDesc",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 7h16" />
        <path d="M4 12h10" />
        <path d="M4 17h7" />
        <path d="M17 14l3 3-3 3" />
      </svg>
    ),
    titleKey: "exactFeatureFacetsTitle",
    descKey: "exactFeatureFacetsDesc",
  },
];

function DiscoverBrowser({ imageMode, onToggleImageMode, enabled = true }) {
  const { t, language } = useLanguage();
  const decks = useUserDecks();
  const [keywordsOpen, setKeywordsOpen] = useState(false);
  const keywordsRef = useRef(null);
  const filtersRef = useRef(null);
  const {
    q, setQ,
    colors, setColors,
    types, setTypes,
    rarity, setRarity,
    selectedKeywords, setSelectedKeywords,
    selectedSubtypes, setSelectedSubtypes,
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
    activeFilterCount,
    totalPages,
  } = useDiscoverCards({ enabled, includeZh: language === "zh" });

  const TYPE_OPTIONS = language === 'zh' ? TYPE_OPTIONS_ZH : TYPE_OPTIONS_EN;
  const RARITY_OPTIONS = language === 'zh' ? RARITY_OPTIONS_ZH : RARITY_OPTIONS_EN;
  const selectedKeywordCount = selectedKeywords.size;
  const keywordSummary = selectedKeywordCount
    ? (language === "zh" ? `已选择 ${selectedKeywordCount} 个能力` : `${selectedKeywordCount} abilities selected`)
    : t('addAbility');

  const toggleKeyword = (keyword) => {
    setSelectedKeywords((prev) => {
      const next = new Set(prev);
      if (next.has(keyword)) {
        next.delete(keyword);
      } else {
        next.add(keyword);
      }
      return next;
    });
  };

  // Use allKeywords for the dropdown options
  const keywordOptions = allKeywords.length > 0 ? allKeywords : keywordFacets.map((kw) => kw.name);
  const showFeatureCards = !loading && results.length === 0 && !hasFilters;

  useEffect(() => {
    if (!keywordsOpen) return;

    const closeOnOutsideClick = (event) => {
      if (!keywordsRef.current?.contains(event.target)) {
        setKeywordsOpen(false);
      }
    };

    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setKeywordsOpen(false);
      }
    };

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);

    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [keywordsOpen]);

  useEffect(() => {
    if (!filtersOpen) return;

    const closeOnOutsideClick = (event) => {
      if (!filtersRef.current?.contains(event.target)) {
        setFiltersOpen(false);
      }
    };

    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setFiltersOpen(false);
      }
    };

    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);

    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [filtersOpen, setFiltersOpen]);

  return (
    <>
      <div className="discover-filter-popover" ref={filtersRef}>
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
            <button
              type="button"
              className={`discover-filter-toggle search-row-toggle ${filtersOpen || activeFilterCount > 0 ? "active" : ""}`}
              onClick={() => setFiltersOpen(!filtersOpen)}
              aria-expanded={filtersOpen}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="4" y1="6" x2="20" y2="6" />
                <line x1="8" y1="12" x2="20" y2="12" />
                <line x1="12" y1="18" x2="20" y2="18" />
              </svg>
              <span>{t('filters')}</span>
              {activeFilterCount > 0 && <span className="filter-count-badge">{activeFilterCount}</span>}
            </button>
          </div>
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
              className="filter-select filter-select-type"
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
              className="filter-select filter-select-rarity"
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
              <div className="filter-ability-multiselect" ref={keywordsRef}>
                <button
                  type="button"
                  className={`filter-ability-trigger ${selectedKeywordCount > 0 ? "active" : ""}`}
                  onClick={() => setKeywordsOpen((open) => !open)}
                  aria-expanded={keywordsOpen}
                >
                  <span>{keywordSummary}</span>
                  {selectedKeywordCount > 0 && <span className="filter-count-badge">{selectedKeywordCount}</span>}
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M6 9l6 6 6-6" />
                  </svg>
                </button>
                {keywordsOpen && (
                  <div className="filter-ability-menu" role="listbox" aria-multiselectable="true">
                    {keywordOptions.map((kw) => (
                      <label key={kw} className="filter-ability-option">
                        <input
                          type="checkbox"
                          checked={selectedKeywords.has(kw)}
                          onChange={() => toggleKeyword(kw)}
                        />
                        <span>{kw}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          <button className="discover-clear-all-inline" onClick={clearAll} disabled={!hasFilters}>
            {t('clearAll')}
          </button>
          </div>
        </div>
      </div>

      <div className="discover-results">
        {loading && <div className="loading"><div className="loading-spinner" /></div>}
        {showFeatureCards && (
          <div className="features-section exact-match-features">
            {EXACT_MATCH_FEATURES.map((feature) => (
              <div key={feature.titleKey} className="feature-card">
                <div className="feature-icon">{feature.icon}</div>
                <h3 className="feature-title">{t(feature.titleKey)}</h3>
                <p className="feature-desc">{t(feature.descKey)}</p>
              </div>
            ))}
          </div>
        )}
        {!loading && results.length === 0 && hasFilters && <div className="no-results"><p>{t('noCardsFound')}</p></div>}
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
