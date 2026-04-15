import { useState } from "react";
import { useNavigate } from "react-router-dom";
import SearchBar from "../components/SearchBar.jsx";
import CardGrid from "../components/CardGrid.jsx";
import DiscoverBrowser from "../components/DiscoverBrowser.jsx";
import { useUserDecks } from "../hooks/useUserDecks.js";
import { useAuth } from "../contexts/AuthContext.jsx";
import { useToast } from "../contexts/ToastContext.jsx";
import { apiFetch } from "../utils/apiFetch.js";

const FEATURES = [
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.4V11h3a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2h-1v3a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-3H6a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3h3V9.4C8.8 8.8 8 7.5 8 6a4 4 0 0 1 4-4z" />
      </svg>
    ),
    title: "AI 智能搜索",
    desc: "用自然语言描述你想要的卡牌，AI 会理解你的意图并找到最匹配的结果，支持中英文混合查询。",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="18" rx="2" />
        <line x1="2" y1="9" x2="22" y2="9" />
        <line x1="10" y1="3" x2="10" y2="9" />
      </svg>
    ),
    title: "卡组管理",
    desc: "创建并管理你的卡组，在搜索结果中一键添加卡牌，支持按类型分组浏览和牌表导入导出。",
  },
  {
    icon: (
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 2h12a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" />
        <path d="M8 7h8" />
        <path d="M8 11h8" />
        <path d="M8 15h4" />
      </svg>
    ),
    title: "导出可打印 PDF",
    desc: "将卡组导出为 A4 尺寸的 PDF 文件，每页 9 张卡牌按 3\u00d73 排列，使用高清卡图，方便打印代牌。",
  },
];

function SearchPage({ imageMode, onToggleImageMode }) {
  const [mode, setMode] = useState("ai");
  const [aiResults, setAiResults] = useState([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiSearched, setAiSearched] = useState(false);
  const decks = useUserDecks();
  const { user } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();

  const requireAuth = () => {
    if (!user) {
      showToast("请先登录后再使用搜索功能", "warning");
      navigate("/login");
      return false;
    }
    return true;
  };

  const handleAiSearch = async (query) => {
    if (!query.trim()) return;
    if (!requireAuth()) return;
    setAiLoading(true);
    setAiSearched(true);
    try {
      const res = await apiFetch("/api/search", {
        method: "POST",
        body: { query },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "搜索失败", "error");
        setAiResults([]);
        return;
      }
      const data = await res.json();
      setAiResults(data.results || []);
    } catch (err) {
      console.error("Search failed:", err);
      setAiResults([]);
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <>
      <div className="mode-toggle-wrapper">
        <div className="mode-toggle" role="tablist" aria-label="搜索模式">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "ai"}
            className={`mode-toggle-btn ${mode === "ai" ? "active" : ""}`}
            onClick={() => requireAuth() && setMode("ai")}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a4 4 0 0 1 4 4c0 1.5-.8 2.8-2 3.4V11h3a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2h-1v3a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-3H6a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3h3V9.4C8.8 8.8 8 7.5 8 6a4 4 0 0 1 4-4z" />
            </svg>
            AI 搜索
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "discover"}
            className={`mode-toggle-btn ${mode === "discover" ? "active" : ""}`}
            onClick={() => requireAuth() && setMode("discover")}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="4" y1="6" x2="20" y2="6" />
              <line x1="8" y1="12" x2="20" y2="12" />
              <line x1="12" y1="18" x2="20" y2="18" />
            </svg>
            精准匹配
          </button>
        </div>
        <button
          type="button"
          className="image-mode-btn"
          onClick={onToggleImageMode}
          title={imageMode === "border_crop" ? "切换为画作模式" : "切换为卡牌模式"}
        >
          {imageMode === "border_crop" ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <polyline points="21 15 16 10 5 21" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="3" width="20" height="18" rx="2" ry="2" />
              <line x1="2" y1="7" x2="22" y2="7" />
              <line x1="2" y1="17" x2="22" y2="17" />
            </svg>
          )}
        </button>
      </div>

      {mode === "ai" && (
        <>
          <SearchBar onSearch={handleAiSearch} loading={aiLoading} />
          {aiLoading && (
            <div className="loading">
              <div className="loading-spinner" />
              <p>AI is searching for cards...</p>
            </div>
          )}
          {!aiLoading && aiSearched && aiResults.length === 0 && (
            <div className="no-results">
              <p>No cards found, try a different description</p>
            </div>
          )}
          {!aiLoading && aiResults.length > 0 && (
            <CardGrid cards={aiResults} imageMode={imageMode} decks={decks} />
          )}
          {!aiLoading && !aiSearched && (
            <div className="features-section">
              {FEATURES.map((f) => (
                <div key={f.title} className="feature-card">
                  <div className="feature-icon">{f.icon}</div>
                  <h3 className="feature-title">{f.title}</h3>
                  <p className="feature-desc">{f.desc}</p>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {mode === "discover" && (
        <DiscoverBrowser
          imageMode={imageMode}
          onToggleImageMode={onToggleImageMode}
          enabled={mode === "discover"}
        />
      )}
    </>
  );
}

export default SearchPage;
