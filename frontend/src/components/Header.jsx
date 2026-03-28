import ThemeToggle from "./ThemeToggle.jsx";

function Header({ theme, onToggleTheme }) {
  return (
    <header className="header">
      <div className="header-inner">
        <div className="logo">
          <h1>MTG Card Search</h1>
          <p className="subtitle">AI-Powered Card Finder</p>
        </div>
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
    </header>
  );
}

export default Header;
