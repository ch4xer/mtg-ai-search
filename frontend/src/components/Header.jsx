import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

function Header({ theme, onToggleTheme }) {
  const { user, logout } = useAuth();

  return (
    <header className="header">
      <div className="header-inner">
        <Link to="/" className="logo">
          <h1>MTG Card Search</h1>
        </Link>
        <div className="header-actions">
          {user ? (
            <>
              {user.role === "admin" && (
                <Link to="/admin" className="header-link header-link-admin">
                  管理
                </Link>
              )}
              <Link to="/decks" className="header-link">
                卡组
              </Link>
              <span className="header-user">{user.username}</span>
              <button className="header-link-btn" onClick={logout}>
                退出
              </button>
            </>
          ) : (
            <Link to="/login" className="header-link">
              登录
            </Link>
          )}
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>
    </header>
  );
}

export default Header;
