import { useState, useRef } from "react";
import { useLanguage } from "../contexts/LanguageContext.jsx";

function SearchBar({ onSearch, loading }) {
  const { t } = useLanguage();
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    const searchQuery = query.trim() || inputRef.current?.placeholder || "";
    onSearch(searchQuery);
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <div className="search-input-wrapper">
        <input
          ref={inputRef}
          type="text"
          className="search-input"
          placeholder={t('searchPlaceholder')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={loading}
        />
        <button type="submit" className="search-btn" disabled={loading}>
          {loading ? t('searching') : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          )}
        </button>
      </div>
    </form>
  );
}

export default SearchBar;