import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import { useToast } from "../contexts/ToastContext.jsx";

function SearchBar({ onSearch, loading }) {
  const [query, setQuery] = useState("");
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const inputRef = useRef(null);

  const handleFocus = () => {
    if (!user) {
      inputRef.current?.blur();
      showToast("请先登录后再使用搜索功能", "warning");
      navigate("/login");
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!user) {
      showToast("请先登录后再使用搜索功能", "warning");
      navigate("/login");
      return;
    }
    onSearch(query);
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <div className="search-input-wrapper">
        <input
          ref={inputRef}
          type="text"
          className="search-input"
          placeholder="描述你想找的卡牌... (例如: 能让对手弃牌的黑色生物)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={handleFocus}
          disabled={loading}
        />
        <button type="submit" className="search-btn" disabled={loading || !query.trim()}>
          {loading ? "Searching..." : "Search"}
        </button>
      </div>
    </form>
  );
}

export default SearchBar;
