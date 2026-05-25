import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { createDeck, fetchUserDecks } from "../api/decks.js";
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
      setDecks(await fetchUserDecks());
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
      const res = await createDeck({ name: newDeckName.trim(), format: newDeckFormat });
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
            <svg className="btn-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span className="btn-label">{language === 'zh' ? '新建卡组' : 'New Deck'}</span>
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
              <svg className="btn-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span className="btn-label">{t('createDeck')}</span>
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
              <svg className="btn-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
              <span className="btn-label">{language === 'zh' ? '取消' : 'Cancel'}</span>
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
