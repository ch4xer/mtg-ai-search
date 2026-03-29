import { useState, useEffect } from "react";
import Header from "./components/Header.jsx";
import SearchBar from "./components/SearchBar.jsx";
import CardGrid from "./components/CardGrid.jsx";

function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("mtg-theme") || "dark";
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [imageMode, setImageMode] = useState(() => {
    return localStorage.getItem("mtg-image-mode") || "border_crop";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("mtg-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const toggleImageMode = () => {
    setImageMode((prev) => {
      const next = prev === "border_crop" ? "art_crop" : "border_crop";
      localStorage.setItem("mtg-image-mode", next);
      return next;
    });
  };

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
    <div className="app">
      <Header theme={theme} onToggleTheme={toggleTheme} />
      <main className="main-content">
        <SearchBar onSearch={handleSearch} loading={loading} imageMode={imageMode} onToggleImageMode={toggleImageMode} />
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
        {!loading && results.length > 0 && <CardGrid cards={results} imageMode={imageMode} />}
      </main>
    </div>
  );
}

export default App;
