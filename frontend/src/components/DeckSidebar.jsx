import { useState, useEffect } from "react";
import { apiFetch } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { FORMATS, getFormatLabel } from "../utils/formats.js";

function DeckSidebar({ collapsed, onToggle }) {
  const [decks, setDecks] = useState([]);
  const [newName, setNewName] = useState("");
  const [newFormat, setNewFormat] = useState("undefined");
  const [creating, setCreating] = useState(false);
  const { showToast } = useToast();
  const { language } = useLanguage();

  const fetchDecks = async () => {
    try {
      const res = await apiFetch("/api/decks");
      if (res.ok) setDecks(await res.json());
    } catch {}
  };

  useEffect(() => {
    fetchDecks();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const res = await apiFetch("/api/decks", {
        method: "POST",
        body: { name: newName.trim(), format: newFormat },
      });
      if (res.ok) {
        const deck = await res.json();
        setDecks((prev) => [{ ...deck, card_count: 0 }, ...prev]);
        setNewName("");
        setNewFormat("undefined");
        showToast(language === 'zh' ? `卡组「${deck.name}」已创建` : `Deck "${deck.name}" created`);
      }
    } catch {
      showToast(language === 'zh' ? "创建失败" : "Failed to create", "error");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className={`deck-sidebar ${collapsed ? "collapsed" : ""}`}>
      <button
        className="sidebar-toggle"
        onClick={onToggle}
        title={language === 'zh' ? (collapsed ? "展开卡组栏" : "收起卡组栏") : (collapsed ? "Expand sidebar" : "Collapse sidebar")}
      >
        {collapsed ? "◀" : "▶"}
      </button>
      {!collapsed && (
        <div className="sidebar-content">
          <h3 className="sidebar-title">{language === 'zh' ? '卡组' : 'Decks'}</h3>
          <form onSubmit={handleCreate} className="sidebar-new-deck">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder={language === 'zh' ? '新建卡组...' : 'New deck...'}
              disabled={creating}
            />
            <select
              className="sidebar-format-select"
              value={newFormat}
              onChange={(e) => setNewFormat(e.target.value)}
              disabled={creating}
            >
              {FORMATS.map((f) => (
                <option key={f.key} value={f.key}>
                  {language === 'zh' ? f.labelZh : f.labelEn}
                </option>
              ))}
            </select>
            <button type="submit" disabled={creating || !newName.trim()}>
              +
            </button>
          </form>
          <div className="sidebar-deck-list">
            {decks.map((deck) => (
              <div
                key={deck.id}
                className="sidebar-deck-item"
                data-deck-id={deck.id}
              >
                <div className="sidebar-deck-info">
                  <span className="sidebar-deck-name">{deck.name}</span>
                  <span
                    className={`format-badge format-${deck.format || "undefined"}`}
                  >
                    {getFormatLabel(deck.format, language)}
                  </span>
                </div>
                <span className="sidebar-deck-count">
                  {deck.card_count || 0}
                </span>
              </div>
            ))}
            {decks.length === 0 && <p className="sidebar-empty">{language === 'zh' ? '还没有卡组' : 'No decks yet'}</p>}
          </div>
        </div>
      )}
    </div>
  );
}

export default DeckSidebar;
