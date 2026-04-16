import { Link } from "react-router-dom";
import DiscoverBrowser from "../components/DiscoverBrowser.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";

function DiscoverPage({ imageMode, onToggleImageMode }) {
  const { t } = useLanguage();

  return (
    <>
      <div className="mode-toggle-wrapper">
        <div className="mode-toggle" role="tablist" aria-label="搜索模式">
          <Link
            to="/"
            role="tab"
            aria-selected="false"
            className="mode-toggle-btn"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.4V11h3a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2h-1v3a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-3H6a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3h3V9.4C8.8 8.8 8 7.5 8 6a4 4 0 0 1 4-4z" />
            </svg>
            {t('aiSearch')}
          </Link>
          <Link
            to="/discover"
            role="tab"
            aria-selected="true"
            className="mode-toggle-btn active"
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

      <DiscoverBrowser imageMode={imageMode} onToggleImageMode={onToggleImageMode} enabled={true} />
    </>
  );
}

export default DiscoverPage;