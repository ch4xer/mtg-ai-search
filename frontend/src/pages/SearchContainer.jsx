import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar.jsx";
import CardGrid from "../components/CardGrid.jsx";
import DeckExplorerSidebar from "../components/DeckExplorerSidebar.jsx";
import DiscoverBrowser from "../components/DiscoverBrowser.jsx";
import RandomCardDialog from "../components/RandomCardDialog.jsx";
import { useUserDecks } from "../hooks/useUserDecks.js";
import { useAuth } from "../contexts/AuthContext.jsx";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { fetchRandomCard } from "../api/cards.js";
import { searchCards } from "../api/search.js";
import { ApiError } from "../utils/apiFetch.js";
import {
  buildAiSearchUrl,
  buildExactSearchUrl,
  parseSearchLocation,
} from "../utils/searchUrlState.js";

const AI_SEARCH_FEATURES = [
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.4V11h3a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2h-1v3a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-3H6a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3h3V9.4C8.8 8.8 8 7.5 8 6a4 4 0 0 1 4-4z" />
      </svg>
    ),
    titleKey: "aiSearchFeatureIntentTitle",
    descKey: "aiSearchFeatureIntentDesc",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="18" rx="2" />
        <line x1="2" y1="9" x2="22" y2="9" />
        <line x1="10" y1="3" x2="10" y2="9" />
      </svg>
    ),
    titleKey: "aiSearchFeatureHybridTitle",
    descKey: "aiSearchFeatureHybridDesc",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 5h16" />
        <path d="M7 12h10" />
        <path d="M10 19h4" />
      </svg>
    ),
    titleKey: "aiSearchFeatureRerankTitle",
    descKey: "aiSearchFeatureRerankDesc",
  },
];

const AI_PAGE_SIZE = 60;

function SearchContainer({ imageMode, onToggleImageMode }) {
  const { t } = useLanguage();
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const decks = useUserDecks();
  const parsedSearch = useMemo(
    () => parseSearchLocation(location.pathname, location.search),
    [location.pathname, location.search],
  );

  const isDiscover = location.pathname === "/exact-match";
  const isAiRoute = location.pathname === "/";
  const [showDeckExplorer, setShowDeckExplorer] = useState(false);
  const [aiResults, setAiResults] = useState([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiLoadingMore, setAiLoadingMore] = useState(false);
  const [aiSearched, setAiSearched] = useState(false);
  const [aiInput, setAiInput] = useState("");
  const [aiQuery, setAiQuery] = useState("");
  const [aiSearchId, setAiSearchId] = useState(null);
  const [aiTotal, setAiTotal] = useState(0);
  const [aiHasMore, setAiHasMore] = useState(false);
  const [randomDialogOpen, setRandomDialogOpen] = useState(false);
  const [randomCard, setRandomCard] = useState(null);
  const [randomLoading, setRandomLoading] = useState(false);
  const [randomError, setRandomError] = useState("");
  const lastExecutedUrlRef = useRef(null);

  const resetAiResults = useCallback(() => {
    setAiResults([]);
    setAiSearched(false);
    setAiQuery("");
    setAiSearchId(null);
    setAiTotal(0);
    setAiHasMore(false);
  }, []);

  const executeAiSearch = useCallback(async (query) => {
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      resetAiResults();
      return;
    }
    setAiLoading(true);
    setAiSearched(true);
    setAiQuery(trimmedQuery);
    setAiSearchId(null);
    setAiTotal(0);
    setAiHasMore(false);
    try {
      const data = await searchCards(trimmedQuery, { limit: AI_PAGE_SIZE, offset: 0 });
      setAiResults(data.results || []);
      setAiSearchId(data.search_id || null);
      setAiTotal(data.total || 0);
      setAiHasMore(Boolean(data.has_more && data.search_id));
    } catch (error) {
      console.error("Search failed:", error);
      showToast(error.status === 429 ? t("searchLimitReached") : (error.message || t("searchFailed")), "error");
      if (error.status === 429 && !user) navigate("/login");
      setAiResults([]);
      setAiSearchId(null);
      setAiTotal(0);
      setAiHasMore(false);
    } finally {
      setAiLoading(false);
    }
  }, [navigate, resetAiResults, showToast, t, user]);

  useEffect(() => {
    if (!isAiRoute) {
      lastExecutedUrlRef.current = null;
      return;
    }
    const currentUrl = `${location.pathname}${location.search}`;
    if (lastExecutedUrlRef.current === currentUrl) return;
    lastExecutedUrlRef.current = currentUrl;
    setAiInput(parsedSearch.query);
    if (parsedSearch.query) executeAiSearch(parsedSearch.query);
    else resetAiResults();
  }, [executeAiSearch, isAiRoute, location.pathname, location.search, parsedSearch, resetAiResults]);

  const commitAiSearch = useCallback((rawValue) => {
    const nextUrl = buildAiSearchUrl(rawValue);
    const currentUrl = `${location.pathname}${location.search}`;
    if (nextUrl === currentUrl) {
      executeAiSearch(rawValue);
    } else {
      navigate(nextUrl);
    }
  }, [executeAiSearch, location.pathname, location.search, navigate]);

  const handleLoadMoreAi = async () => {
    if (aiLoadingMore || aiLoading) return;
    if (!aiQuery || !aiSearchId) return;
    setAiLoadingMore(true);
    try {
      const data = await searchCards(aiQuery, {
        limit: AI_PAGE_SIZE,
        offset: aiResults.length,
        searchId: aiSearchId,
      });
      setAiResults((previous) => [...previous, ...(data.results || [])]);
      setAiSearchId(data.search_id || aiSearchId);
      setAiTotal(data.total || aiTotal);
      setAiHasMore(Boolean(data.has_more && (data.search_id || aiSearchId)));
    } catch (error) {
      console.error("Load more failed:", error);
      showToast(error.message || t("searchFailed"), "error");
      if (error instanceof ApiError && [400, 404, 410].includes(error.status)) {
        setAiHasMore(false);
        setAiSearchId(null);
      }
    } finally {
      setAiLoadingMore(false);
    }
  };

  const handleFindSimilar = useCallback((card, tags) => {
    if (!tags.length) return;
    navigate(buildExactSearchUrl({ functionTags: tags, sourceCardId: card.id }));
  }, [navigate]);

  const drawRandomCard = useCallback(async (excludeCardId = null) => {
    setRandomDialogOpen(true);
    setRandomLoading(true);
    setRandomError("");
    try {
      const data = await fetchRandomCard(excludeCardId);
      setRandomCard(data.card || null);
    } catch (error) {
      setRandomError(error.message || t("randomCardFailed"));
      if (!randomCard) setRandomCard(null);
    } finally {
      setRandomLoading(false);
    }
  }, [randomCard, t]);

  return (
    <>
      <div className="mode-toggle-wrapper">
        <div className="mode-toggle" role="tablist" aria-label={t("searchModes")}>
          <Link to="/" role="tab" aria-selected={!isDiscover} className={`mode-toggle-btn ${!isDiscover ? "active" : ""}`}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.4V11h3a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2h-1v3a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-3H6a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3h3V9.4C8.8 8.8 8 7.5 8 6a4 4 0 0 1 4-4z" />
            </svg>
            {t("aiSearch")}
          </Link>
          <Link to="/exact-match" role="tab" aria-selected={isDiscover} className={`mode-toggle-btn ${isDiscover ? "active" : ""}`}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="4" y1="6" x2="20" y2="6" /><line x1="8" y1="12" x2="20" y2="12" /><line x1="12" y1="18" x2="20" y2="18" />
            </svg>
            {t("exactMatch")}
          </Link>
        </div>
        <div className="search-toolbar-actions">
          <button type="button" className="random-card-btn" onClick={() => drawRandomCard(null)} title={t("randomCard")}>
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="3" width="18" height="18" rx="4" /><circle cx="8" cy="8" r="1" fill="currentColor" /><circle cx="16" cy="8" r="1" fill="currentColor" /><circle cx="12" cy="12" r="1" fill="currentColor" /><circle cx="8" cy="16" r="1" fill="currentColor" /><circle cx="16" cy="16" r="1" fill="currentColor" />
            </svg>
            <span>{t("randomCard")}</span>
          </button>
          <button type="button" className="image-mode-btn" onClick={onToggleImageMode} title={imageMode === "border_crop" ? t("switchToArtMode") : t("switchToCardMode")}>
            {imageMode === "border_crop" ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="18" rx="2" /><line x1="2" y1="7" x2="22" y2="7" /><line x1="2" y1="17" x2="22" y2="17" /></svg>
            )}
          </button>
        </div>
      </div>

      <div style={{ display: !isDiscover ? undefined : "none" }}>
        <SearchBar
          onSearch={commitAiSearch}
          loading={aiLoading}
          value={aiInput}
          onChange={setAiInput}
        />
        {aiLoading && <div className="loading"><div className="loading-spinner" /><p>{t("searching")}</p></div>}
        {!aiLoading && aiSearched && aiResults.length === 0 && <div className="no-results"><p>{t("noCardsFoundAI")}</p></div>}
        {!aiLoading && aiResults.length > 0 && (
          <>
            <CardGrid cards={aiResults} imageMode={imageMode} decks={decks} onFindSimilar={handleFindSimilar} />
            {aiHasMore && (
              <div className="load-more-row">
                <button className="load-more-btn" onClick={handleLoadMoreAi} disabled={aiLoadingMore}>
                  {aiLoadingMore ? t("loadingMore") : t("loadMoreCards").replace("{shown}", aiResults.length).replace("{total}", aiTotal)}
                </button>
              </div>
            )}
          </>
        )}
        {!aiLoading && !aiSearched && (
          <div className="features-section">
            {AI_SEARCH_FEATURES.map((feature) => (
              <div key={feature.titleKey} className="feature-card">
                <div className="feature-icon">{feature.icon}</div>
                <h3 className="feature-title">{t(feature.titleKey)}</h3>
                <p className="feature-desc">{t(feature.descKey)}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: isDiscover ? undefined : "none" }}>
        <DiscoverBrowser imageMode={imageMode} onToggleImageMode={onToggleImageMode} enabled={isDiscover} onFindSimilar={handleFindSimilar} />
      </div>

      <button className="deck-explorer-fab" onClick={() => setShowDeckExplorer((value) => !value)} title={t("deckExplorer")}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></svg>
      </button>
      <DeckExplorerSidebar isOpen={showDeckExplorer} onClose={() => setShowDeckExplorer(false)} />

      {randomDialogOpen && (
        <RandomCardDialog
          card={randomCard}
          loading={randomLoading}
          error={randomError}
          onAgain={drawRandomCard}
          onClose={() => setRandomDialogOpen(false)}
        />
      )}
    </>
  );
}

export default SearchContainer;
