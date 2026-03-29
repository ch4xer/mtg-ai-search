import { useState } from "react";

function SearchBar({ onSearch, loading, imageMode, onToggleImageMode }) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch(query);
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <div className="search-input-wrapper">
        <input
          type="text"
          className="search-input"
          placeholder="描述你想找的卡牌... (例如: 能让对手弃牌的黑色生物)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="search-btn" disabled={loading || !query.trim()}>
          {loading ? "Searching..." : "Search"}
        </button>
        <button
          type="button"
          className="image-mode-btn"
          onClick={onToggleImageMode}
          title={imageMode === "border_crop" ? "切换为画作模式" : "切换为卡牌模式"}
        >
          {imageMode === "border_crop" ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="3" width="20" height="18" rx="2" ry="2" />
              <line x1="2" y1="7" x2="22" y2="7" />
              <line x1="2" y1="17" x2="22" y2="17" />
            </svg>
          )}
        </button>
      </div>
    </form>
  );
}

export default SearchBar;
