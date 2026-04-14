import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";
import { FORMATS, getFormatLabel } from "../utils/formats.js";

function DecksPage() {
  const [decks, setDecks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newDeckName, setNewDeckName] = useState("");
  const [newDeckFormat, setNewDeckFormat] = useState("undefined");
  const [creating, setCreating] = useState(false);
  const [showInput, setShowInput] = useState(false);
  const navigate = useNavigate();
  const { showToast } = useToast();

  const fetchDecks = async () => {
    try {
      const res = await apiFetch("/api/decks");
      if (res.ok) {
        setDecks(await res.json());
      }
    } catch (err) {
      console.error("Failed to fetch decks:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDecks();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newDeckName.trim()) return;
    setCreating(true);
    try {
      const res = await apiFetch("/api/decks", {
        method: "POST",
        body: { name: newDeckName.trim(), format: newDeckFormat },
      });
      if (res.ok) {
        const deck = await res.json();
        setDecks((prev) => [{ ...deck, card_count: 0 }, ...prev]);
        setNewDeckName("");
        setNewDeckFormat("undefined");
        setShowInput(false);
        showToast(`卡组「${deck.name}」已创建`);
      }
    } catch (err) {
      showToast("创建失败", "error");
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <p>加载卡组中...</p>
      </div>
    );
  }

  return (
    <div className="decks-page">
      <div className="decks-header">
        <h2>打印卡组</h2>
        {!showInput ? (
          <button className="btn-accent" onClick={() => setShowInput(true)}>
            + 新建卡组
          </button>
        ) : (
          <form onSubmit={handleCreate} className="new-deck-form">
            <input
              type="text"
              value={newDeckName}
              onChange={(e) => setNewDeckName(e.target.value)}
              placeholder="卡组名称"
              autoFocus
              disabled={creating}
            />
            <select
              className="deck-format-select"
              value={newDeckFormat}
              onChange={(e) => setNewDeckFormat(e.target.value)}
              disabled={creating}
            >
              {FORMATS.map((f) => (
                <option key={f.key} value={f.key}>
                  {f.label}
                </option>
              ))}
            </select>
            <button
              type="submit"
              className="btn-accent"
              disabled={creating || !newDeckName.trim()}
            >
              创建
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setShowInput(false);
                setNewDeckName("");
                setNewDeckFormat("undefined");
              }}
            >
              取消
            </button>
          </form>
        )}
      </div>
      {decks.length === 0 ? (
        <div className="no-results">
          <p>还没有卡组，点击上方按钮创建一个吧</p>
        </div>
      ) : (
        <div className="deck-grid">
          {decks.map((deck) => (
            <div
              key={deck.id}
              className="deck-card"
              onClick={() => navigate(`/decks/${deck.id}`)}
            >
              <h3 className="deck-card-name">{deck.name}</h3>
              <span
                className={`format-badge format-${deck.format || "undefined"}`}
              >
                {getFormatLabel(deck.format)}
              </span>
              <p className="deck-card-count">{deck.card_count || 0} 张卡牌</p>
              <p className="deck-card-date">
                {new Date(deck.created_at).toLocaleDateString("zh-CN")}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default DecksPage;
