import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { FORMATS, getFormatLabel } from "../utils/formats.js";

function DecksPage() {
  const { t, language } = useLanguage();
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
        showToast(language === 'zh' ? `卡组「${deck.name}」已创建` : `Deck "${deck.name}" created`);
      }
    } catch (err) {
      showToast(language === 'zh' ? "创建失败" : "Failed to create", "error");
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <p>{language === 'zh' ? '加载卡组中...' : 'Loading decks...'}</p>
      </div>
    );
  }

  return (
    <div className="decks-page">
      <div className="decks-header">
        <h2>{t('myDecks')}</h2>
        {!showInput ? (
          <button className="btn-accent" onClick={() => setShowInput(true)}>
            + {language === 'zh' ? '新建卡组' : 'New Deck'}
          </button>
        ) : (
          <form onSubmit={handleCreate} className="new-deck-form">
            <input
              type="text"
              value={newDeckName}
              onChange={(e) => setNewDeckName(e.target.value)}
              placeholder={t('deckName')}
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
                  {language === 'zh' ? f.labelZh : f.labelEn}
                </option>
              ))}
            </select>
            <button
              type="submit"
              className="btn-accent"
              disabled={creating || !newDeckName.trim()}
            >
              {t('createDeck')}
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
              {language === 'zh' ? '取消' : 'Cancel'}
            </button>
          </form>
        )}
      </div>
      {decks.length === 0 ? (
        <div className="no-results">
          <p>{language === 'zh' ? '还没有卡组，点击上方按钮创建一个吧' : 'No decks yet. Click the button above to create one.'}</p>
        </div>
      ) : (
        <div className="deck-grid">
          {decks.map((deck) => (
            <div
              key={deck.id}
              className="deck-card"
              onClick={() => navigate(`/decks/${deck.id}`)}
            >
              <div className="deck-card-header">
                <h3 className="deck-card-name">{deck.name}</h3>
                <span
                  className={`format-badge format-${deck.format || "undefined"}`}
                >
                  {getFormatLabel(deck.format, language)}
                </span>
              </div>
              <p className="deck-card-count">{deck.card_count || 0} {language === 'zh' ? '张卡牌' : 'cards'}</p>
              <p className="deck-card-date">
                {new Date(deck.created_at).toLocaleDateString(language === 'zh' ? "zh-CN" : "en-US")}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default DecksPage;