import { useState, useEffect } from "react";
import SearchBar from "../components/SearchBar.jsx";
import CardGrid from "../components/CardGrid.jsx";
import { useAuth } from "../contexts/AuthContext.jsx";
import { apiFetch } from "../utils/apiFetch.js";

function SearchPage({ imageMode, onToggleImageMode }) {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [decks, setDecks] = useState([]);
  const { user } = useAuth();

  useEffect(() => {
    if (user) {
      apiFetch("/api/decks")
        .then((res) => (res.ok ? res.json() : []))
        .then(setDecks)
        .catch(() => {});
    } else {
      setDecks([]);
    }
  }, [user]);

  const handleSearch = async (query) => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error("Search failed:", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <SearchBar onSearch={handleSearch} loading={loading} imageMode={imageMode} onToggleImageMode={onToggleImageMode} />
      {loading && (
        <div className="loading">
          <div className="loading-spinner" />
          <p>AI正在为你搜寻卡牌...</p>
        </div>
      )}
      {!loading && searched && results.length === 0 && (
        <div className="no-results">
          <p>未找到匹配的卡牌，请尝试其他描述</p>
        </div>
      )}
      {!loading && results.length > 0 && (
        <CardGrid cards={results} imageMode={imageMode} decks={decks} />
      )}
    </>
  );
}

export default SearchPage;
