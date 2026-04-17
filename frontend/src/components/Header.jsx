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
            {language === 'en' ? '中文' : 'EN'}
          </button>
          {user ? (
            <>
              {user.role === "admin" && (
                <Link to="/admin" className="header-link header-link-admin">
                  {t('admin')}
                </Link>
              )}
              <Link to="/decks" className="header-link">
                {t('decks')}
              </Link>
              <Link to="/settings" className="header-user-link">
                {user.username}
              </Link>
              <button className="header-link-btn" onClick={logout}>
                {t('logout')}
              </button>
            </>
          ) : (
            <Link to="/login" className="header-link">
              {t('login')}
            </Link>
          )}
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>
    </header>
  );
}

export default Header;