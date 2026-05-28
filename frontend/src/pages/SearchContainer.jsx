import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar.jsx";
import CardGrid from "../components/CardGrid.jsx";
import DiscoverBrowser from "../components/DiscoverBrowser.jsx";
import { useUserDecks } from "../hooks/useUserDecks.js";
import { useAuth } from "../contexts/AuthContext.jsx";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { searchCards } from "../api/search.js";

const AI_SEARCH_FEATURES = [
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.4V11h3a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2h-1v3a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-3H6a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3h3V9.4C8.8 8.8 8 7.5 8 6a4 4 0 0 1 4-4z" />
      </svg>
    ),
    titleKey: 'aiSearchFeatureIntentTitle',
    descKey: 'aiSearchFeatureIntentDesc',
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="18" rx="2" />
        <line x1="2" y1="9" x2="22" y2="9" />
        <line x1="10" y1="3" x2="10" y2="9" />
      </svg>
    ),
    titleKey: 'aiSearchFeatureHybridTitle',
    descKey: 'aiSearchFeatureHybridDesc',
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 2h12a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" />
        <path d="M8 7h8" />
        <path d="M8 11h8" />
        <path d="M8 15h4" />
      </svg>
    ),
    titleKey: 'aiSearchFeatureRerankTitle',
    descKey: 'aiSearchFeatureRerankDesc',
  },
];

const AI_PAGE_SIZE = 60;

function SearchContainer({ imageMode, onToggleImageMode }) {
  const { t, language } = useLanguage();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const decks = useUserDecks();

  const isDiscover = location.pathname === "/exact-match";
  const isAiSearch = !isDiscover;

  // AI search state
  const [aiResults, setAiResults] = useState([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiLoadingMore, setAiLoadingMore] = useState(false);
  const [aiSearched, setAiSearched] = useState(false);
  const [aiQuery, setAiQuery] = useState("");
  const [aiSearchId, setAiSearchId] = useState(null);
  const [aiTotal, setAiTotal] = useState(0);
  const [aiHasMore, setAiHasMore] = useState(false);

  const handleAiSearch = async (query) => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) return;
    setAiLoading(true);
    setAiSearched(true);
    setAiQuery(trimmedQuery);
    setAiSearchId(null);
    setAiTotal(0);
    setAiHasMore(false);
    try {
      const res = await searchCards(trimmedQuery, {
        limit: AI_PAGE_SIZE,
        offset: 0,
        includeZh: language === "zh",
      });
      if (res.status === 429) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t('searchLimitReached'), "error");
        if (!user) navigate("/login");
        setAiResults([]);
        setAiSearchId(null);
        setAiTotal(0);
        setAiHasMore(false);
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t('searchFailed'), "error");
        setAiResults([]);
        setAiSearchId(null);
        setAiTotal(0);
        setAiHasMore(false);
        return;
      }
      const data = await res.json();
      setAiResults(data.results || []);
      setAiSearchId(data.search_id || null);
      setAiTotal(data.total || 0);
      setAiHasMore(Boolean(data.has_more && data.search_id));
    } catch (err) {
      console.error("Search failed:", err);
      showToast(t('searchFailed'), "error");
      setAiResults([]);
      setAiSearchId(null);
      setAiTotal(0);
      setAiHasMore(false);
    } finally {
      setAiLoading(false);
    }
  };

  const handleLoadMoreAi = async () => {
    if (!aiQuery || !aiSearchId || aiLoadingMore || aiLoading) return;
    setAiLoadingMore(true);
    try {
      const res = await searchCards(aiQuery, {
        limit: AI_PAGE_SIZE,
        offset: aiResults.length,
        searchId: aiSearchId,
        includeZh: language === "zh",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t('searchFailed'), "error");
        if ([400, 404, 410].includes(res.status)) {
          setAiHasMore(false);
          setAiSearchId(null);
        }
        return;
      }
      const data = await res.json();
      setAiResults((prev) => [...prev, ...(data.results || [])]);
      setAiSearchId(data.search_id || aiSearchId);
      setAiTotal(data.total || aiTotal);
      setAiHasMore(Boolean(data.has_more && (data.search_id || aiSearchId)));
    } catch (err) {
      console.error("Load more failed:", err);
      showToast(t('searchFailed'), "error");
    } finally {
      setAiLoadingMore(false);
    }
  };

  return (
    <>
      <div className="mode-toggle-wrapper">
        <div className="mode-toggle" role="tablist" aria-label="搜索模式">
          <Link
            to="/"
            role="tab"
            aria-selected={isAiSearch}
            className={`mode-toggle-btn ${isAiSearch ? "active" : ""}`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.4V11h3a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2h-1v3a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-3H6a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3h3V9.4C8.8 8.8 8 7.5 8 6a4 4 0 0 1 4-4z" />
            </svg>
            {t('aiSearch')}
          </Link>
          <Link
            to="/exact-match"
            role="tab"
            aria-selected={isDiscover}
            className={`mode-toggle-btn ${isDiscover ? "active" : ""}`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="4" y1="6" x2="20" y2="6" />
              <line x1="8" y1="12" x2="20" y2="12" />
              <line x1="12" y1="18" x2="20" y2="18" />
            </svg>
            {t('exactMatch')}
          </Link>
        </div>
        <button
          type="button"
          className="image-mode-btn"
          onClick={onToggleImageMode}
          title={imageMode === "border_crop" ? t('switchToArtMode') : t('switchToCardMode')}
        >
          {imageMode === "border_crop" ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="3" width="20" height="18" rx="2" ry="2" />
              <line x1="2" y1="7" x2="22" y2="7" />
              <line x1="2" y1="17" x2="22" y2="17" />
            </svg>
          )}
        </button>
      </div>

      {/* AI search panel — hidden when on exact match, but stays mounted */}
      <div style={{ display: isAiSearch ? undefined : "none" }}>
        <SearchBar onSearch={handleAiSearch} loading={aiLoading} />
        {aiLoading && (
          <div className="loading">
            <div className="loading-spinner" />
            <p>{t('searching')}</p>
          </div>
        )}
        {!aiLoading && aiSearched && aiResults.length === 0 && (
          <div className="no-results">
            <p>{t('noCardsFoundAI')}</p>
          </div>
        )}
        {!aiLoading && aiResults.length > 0 && (
          <>
            <CardGrid cards={aiResults} imageMode={imageMode} decks={decks} />
            {aiHasMore && (
              <div className="load-more-row">
                <button className="load-more-btn" onClick={handleLoadMoreAi} disabled={aiLoadingMore}>
                  {aiLoadingMore
                    ? t('loadingMore')
                    : t('loadMoreCards')
                        .replace("{shown}", aiResults.length)
                        .replace("{total}", aiTotal)}
                </button>
              </div>
            )}
          </>
        )}
        {!aiLoading && !aiSearched && (
          <div className="features-section">
            {AI_SEARCH_FEATURES.map((f) => (
              <div key={f.titleKey} className="feature-card">
                <div className="feature-icon">{f.icon}</div>
                <h3 className="feature-title">{t(f.titleKey)}</h3>
                <p className="feature-desc">{t(f.descKey)}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Discover panel — hidden when on /, but stays mounted */}
      <div style={{ display: isDiscover ? undefined : "none" }}>
        <DiscoverBrowser imageMode={imageMode} onToggleImageMode={onToggleImageMode} enabled={true} />
      </div>
    </>
  );
}

export default SearchContainer;
