import { useState, useEffect } from "react";
import { apiFetch } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";

function DeckSidebar({ collapsed, onToggle }) {
  const [decks, setDecks] = useState([]);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const { showToast } = useToast();

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
        body: { name: newName.trim() },
      });
      if (res.ok) {
        const deck = await res.json();
        setDecks((prev) => [{ ...deck, card_count: 0 }, ...prev]);
        setNewName("");
        showToast(`卡组「${deck.name}」已创建`);
      }
    } catch {
      showToast("创建失败", "error");
    } finally {
      setCreating(false);
    }
  };

  const addCardToDeck = async (deckId, cardId, cardName) => {
    try {
      const res = await apiFetch(`/api/decks/${deckId}/cards`, {
        method: "POST",
        body: { card_id: cardId },
      });
      if (res.ok) {
        const deckName = decks.find((d) => d.id === deckId)?.name || "卡组";
        showToast(`已将「${cardName}」加入「${deckName}」`);
        setDecks((prev) =>
          prev.map((d) =>
            d.id === deckId ? { ...d, card_count: (d.card_count || 0) + 1 } : d
          )
        );
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "添加失败", "error");
      }
    } catch {
      showToast("添加失败", "error");
    }
  };

  return (
    <div className={`deck-sidebar ${collapsed ? "collapsed" : ""}`}>
      <button className="sidebar-toggle" onClick={onToggle} title={collapsed ? "展开卡组栏" : "收起卡组栏"}>
        {collapsed ? "◀" : "▶"}
      </button>
      {!collapsed && (
        <div className="sidebar-content">
          <h3 className="sidebar-title">我的卡组</h3>
          <form onSubmit={handleCreate} className="sidebar-new-deck">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="新建卡组..."
              disabled={creating}
            />
            <button type="submit" disabled={creating || !newName.trim()}>+</button>
          </form>
          <div className="sidebar-deck-list">
            {decks.map((deck) => (
              <div key={deck.id} className="sidebar-deck-item" data-deck-id={deck.id}>
                <span className="sidebar-deck-name">{deck.name}</span>
                <span className="sidebar-deck-count">{deck.card_count || 0}</span>
              </div>
            ))}
            {decks.length === 0 && (
              <p className="sidebar-empty">还没有卡组</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default DeckSidebar;
export { DeckSidebar };
