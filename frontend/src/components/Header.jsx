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
        </div>
      </div>
    </header>
  );
}

export default Header;
