import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

function Header({ theme, onToggleTheme }) {
  const { user, logout } = useAuth();
  const { t, language, toggleLanguage } = useLanguage();

  return (
    <header className="header">
      <div className="header-inner">
        <Link to="/" className="logo">
          <h1>{t('appTitle')}</h1>
        </Link>
        <div className="header-actions">
          <button className="lang-toggle-btn" onClick={toggleLanguage} title={language === 'en' ? '切换中文' : 'Switch to English'}>
            <svg className="header-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="2" y1="12" x2="22" y2="12" />
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
            </svg>
            <span className="btn-label">{language === 'en' ? '中文' : 'EN'}</span>
          </button>
          {user ? (
            <>
              {user.role === "admin" && (
                <Link to="/admin" className="header-link header-link-admin" title={t('admin')}>
                  <svg className="header-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                  <span className="btn-label">{t('admin')}</span>
                </Link>
              )}
              <Link to="/decks" className="header-link" title={t('decks')}>
                <svg className="header-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="12 2 2 7 12 12 22 7 12 2" />
                  <polyline points="2 17 12 22 22 17" />
                  <polyline points="2 12 12 17 22 12" />
                </svg>
                <span className="btn-label">{t('decks')}</span>
              </Link>
              <Link to="/settings" className="header-user-link" title={user.username}>
                <svg className="header-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                <span className="btn-label">{user.username}</span>
              </Link>
              <button className="header-link-btn" onClick={logout} title={t('logout')}>
                <svg className="header-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                <span className="btn-label">{t('logout')}</span>
              </button>
            </>
          ) : (
            <Link to="/login" className="header-link" title={t('login')}>
              <svg className="header-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
                <polyline points="10 17 15 12 10 7" />
                <line x1="15" y1="12" x2="3" y2="12" />
              </svg>
              <span className="btn-label">{t('login')}</span>
            </Link>
          )}
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
          <a
            href="https://github.com/ch4xer/mtg-ai-search"
            className="theme-toggle github-link"
            target="_blank"
            rel="noreferrer"
            title="GitHub"
            aria-label="GitHub"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2C6.48 2 2 6.58 2 12.23c0 4.52 2.87 8.35 6.84 9.71.5.1.68-.22.68-.49 0-.24-.01-.88-.01-1.73-2.78.62-3.37-1.37-3.37-1.37-.45-1.18-1.11-1.49-1.11-1.49-.91-.64.07-.63.07-.63 1 .07 1.53 1.06 1.53 1.06.89 1.56 2.34 1.11 2.91.85.09-.66.35-1.11.63-1.37-2.22-.26-4.56-1.14-4.56-5.06 0-1.12.39-2.03 1.03-2.75-.1-.26-.45-1.3.1-2.71 0 0 .84-.28 2.75 1.05A9.32 9.32 0 0 1 12 6.96c.85 0 1.7.12 2.5.34 1.9-1.33 2.74-1.05 2.74-1.05.55 1.41.2 2.45.1 2.71.64.72 1.03 1.63 1.03 2.75 0 3.93-2.34 4.8-4.57 5.05.36.32.68.94.68 1.9 0 1.37-.01 2.47-.01 2.81 0 .27.18.59.69.49A10.1 10.1 0 0 0 22 12.23C22 6.58 17.52 2 12 2z" />
            </svg>
          </a>
        </div>
      </div>
    </header>
  );
}

export default Header;
