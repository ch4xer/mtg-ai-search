import { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiFetch, getAccessToken } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";
import { FORMATS, getFormatLabel, getCardLegality, isCardLegal, legalityLabel } from "../utils/formats.js";
import { getImageUri } from "../utils/cardImage.js";

/* ── Type classification ── */

const TYPE_ORDER = [
  "Planeswalker", "Creature", "Sorcery", "Instant",
  "Artifact", "Enchantment", "Land", "Other",
];

function classifyCard(card) {
  const tl = card.type_line || "";
  for (const t of TYPE_ORDER) {
    if (t !== "Other" && tl.includes(t)) return t;
  }
  return "Other";
}

const TYPE_LABELS = {
  Creature: "生物", Planeswalker: "旅法师", Instant: "瞬间", Sorcery: "法术",
  Enchantment: "结界", Artifact: "神器", Land: "地", Other: "其他",
};


/* ── Main Component ── */

function DeckDetailPage({ imageMode }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [deck, setDeck] = useState(null);
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [exporting, setExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(null);
  const [importing, setImporting] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importText, setImportText] = useState("");
  const [importNotFound, setImportNotFound] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);

  // ── Data fetching ──

  const fetchDeck = async () => {
    try {
      const [deckRes, cardsRes] = await Promise.all([
        apiFetch(`/api/decks/${id}`),
        apiFetch(`/api/decks/${id}/cards`),
      ]);
      if (deckRes.status === 404) {
        showToast("卡组不存在", "error");
        navigate("/decks");
        return;
      }
      if (deckRes.ok && cardsRes.ok) {
        const deckData = await deckRes.json();
        setDeck(deckData);
        setEditName(deckData.name);
        setCards(await cardsRes.json());
      }
    } catch {
      showToast("加载失败", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDeck(); }, [id]);

  // ── Group cards by type ──

  const groupedCards = useMemo(() => {
    const groups = {};
    for (const item of cards) {
      const type = classifyCard(item.card);
      if (!groups[type]) groups[type] = [];
      groups[type].push(item);
    }
    // Sort groups by TYPE_ORDER
    const ordered = [];
    for (const type of TYPE_ORDER) {
      if (groups[type]) {
        const count = groups[type].reduce((s, c) => s + c.quantity, 0);
        ordered.push({ type, label: TYPE_LABELS[type], count, items: groups[type] });
      }
    }
    return ordered;
  }, [cards]);

  // ── Deck analysis ──

  const deckAnalysis = useMemo(() => {
    if (cards.length === 0) return null;

    // Color distribution
    const colorCounts = { W: 0, U: 0, B: 0, R: 0, G: 0 };
    const colorLabels = { W: "白", U: "蓝", B: "黑", R: "红", G: "绿" };
    for (const item of cards) {
      const ci = item.card.color_identity || item.card.colors || [];
      for (const c of ci) {
        if (colorCounts[c] !== undefined) colorCounts[c] += item.quantity;
      }
    }

    // Mana curve (CMC 0–7+)
    const cmcBuckets = [0, 0, 0, 0, 0, 0, 0, 0]; // indices 0-7, index 7 = "7+"
    for (const item of cards) {
      const cmc = Math.floor(item.card.cmc ?? 0);
      const tl = item.card.type_line || "";
      if (tl.includes("Land")) continue;
      const idx = Math.min(cmc, 7);
      cmcBuckets[idx] += item.quantity;
    }
    const cmcMax = Math.max(...cmcBuckets, 1);

    // Rarity distribution
    const rarityOrder = ["common", "uncommon", "rare", "mythic"];
    const rarityLabels = { common: "普通", uncommon: "非普通", rare: "稀有", mythic: "秘稀" };
    const rarityCounts = {};
    for (const item of cards) {
      const r = item.card.rarity || "common";
      rarityCounts[r] = (rarityCounts[r] || 0) + item.quantity;
    }

    const totalColorCards = Object.values(colorCounts).reduce((s, v) => s + v, 0) || 1;

    return { colorCounts, colorLabels, totalColorCards, cmcBuckets, cmcMax, rarityCounts, rarityLabels, rarityOrder };
  }, [cards]);

  // Auto-select first card
  useEffect(() => {
    if (cards.length > 0 && !selectedCard) {
      setSelectedCard(cards[0]);
    }
  }, [cards]);

  // ── Handlers ──

  const handleRename = async () => {
    if (!editName.trim() || editName.trim() === deck.name) {
      setEditing(false);
      return;
    }
    const res = await apiFetch(`/api/decks/${id}`, {
      method: "PUT",
      body: { name: editName.trim() },
    });
    if (res.ok) {
      const updated = await res.json();
      setDeck((prev) => ({ ...prev, name: updated.name }));
      showToast("卡组已重命名");
    }
    setEditing(false);
  };

  const handleFormatChange = async (e) => {
    const newFormat = e.target.value;
    if (newFormat === deck.format) return;
    const res = await apiFetch(`/api/decks/${id}`, {
      method: "PUT",
      body: { name: deck.name, format: newFormat },
    });
    if (res.ok) {
      const updated = await res.json();
      setDeck((prev) => ({ ...prev, format: updated.format }));
      showToast(`模式已切换为「${getFormatLabel(updated.format)}」`);
    }
  };

  const handleDelete = async () => {
    if (!confirm("确定要删除这个卡组吗？")) return;
    const res = await apiFetch(`/api/decks/${id}`, { method: "DELETE" });
    if (res.ok) {
      showToast("卡组已删除");
      navigate("/decks");
    }
  };

  const handleQuantityChange = async (cardId, delta) => {
    const card = cards.find((c) => c.card_id === cardId);
    if (!card) return;
    const newQty = card.quantity + delta;
    if (newQty <= 0) {
      await handleRemoveCard(cardId);
      return;
    }
    const res = await apiFetch(`/api/decks/${id}/cards`, {
      method: "POST",
      body: { card_id: cardId, quantity: delta },
    });
    if (res.ok) {
      setCards((prev) =>
        prev.map((c) => (c.card_id === cardId ? { ...c, quantity: newQty } : c))
      );
      if (selectedCard?.card_id === cardId) {
        setSelectedCard((prev) => ({ ...prev, quantity: newQty }));
      }
    }
  };

  const handleRemoveCard = async (cardId) => {
    const res = await apiFetch(`/api/decks/${id}/cards/${cardId}`, { method: "DELETE" });
    if (res.ok) {
      setCards((prev) => prev.filter((c) => c.card_id !== cardId));
      if (selectedCard?.card_id === cardId) setSelectedCard(null);
      showToast("已移除卡牌");
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setExportProgress({ phase: "download", current: 0, total: 0 });
    try {
      const token = getAccessToken();
      const res = await fetch(`/api/decks/${id}/export/stream`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "导出失败", "error");
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let exportId = null;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop();
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data: ")) continue;
          const data = JSON.parse(line.slice(6));
          if (data.type === "progress") setExportProgress(data);
          else if (data.type === "complete") exportId = data.export_id;
        }
      }
      if (exportId) {
        const pdfRes = await apiFetch(`/api/decks/${id}/export/download/${exportId}`);
        if (!pdfRes.ok) { showToast("下载 PDF 失败", "error"); return; }
        const blob = await pdfRes.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${deck?.name || "deck"}_cards.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        showToast("PDF 导出成功");
      }
    } catch { showToast("导出失败", "error"); }
    finally { setExporting(false); setExportProgress(null); }
  };

  const handleExportText = async () => {
    try {
      const res = await apiFetch(`/api/decks/${id}/export/text`);
      if (!res.ok) { showToast(((await res.json().catch(() => ({}))).detail) || "复制失败", "error"); return; }
      const text = await res.text();
      await navigator.clipboard.writeText(text);
      showToast("牌表已复制到剪切板");
    } catch { showToast("复制失败", "error"); }
  };

  const handleImportSubmit = async () => {
    if (!importText.trim()) return;
    setImporting(true);
    try {
      const res = await apiFetch(`/api/decks/${id}/import`, { method: "POST", body: { text: importText } });
      if (!res.ok) { showToast(((await res.json().catch(() => ({}))).detail) || "导入失败", "error"); return; }
      const data = await res.json();
      const addedCount = data.added.reduce((s, c) => s + c.quantity, 0);
      const notFoundCount = data.not_found.length;
      showToast(`成功导入 ${addedCount} 张卡牌${notFoundCount > 0 ? `，${notFoundCount} 张未找到` : ""}`, notFoundCount > 0 ? "warning" : "success");
      if (notFoundCount > 0) setImportNotFound(data.not_found);
      setShowImportModal(false);
      setImportText("");
      await fetchDeck();
    } catch { showToast("导入失败", "error"); }
    finally { setImporting(false); }
  };

  // ── Helpers ──

  const getCardDisplayImage = (item) => {
    return getImageUri(item.card.image_uris, "art_crop")
      || getImageUri(item.card.card_faces?.[0]?.image_uris, "art_crop");
  };

  const getCardFullImage = (item) => {
    return getImageUri(item.card.image_uris, "png")
      || getImageUri(item.card.card_faces?.[0]?.image_uris, "png");
  };

  // ── Render ──

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <p>加载卡组中...</p>
      </div>
    );
  }
  if (!deck) return null;

  const totalCards = cards.reduce((sum, c) => sum + c.quantity, 0);

  return (
    <div className="deck-detail">
      {/* Header */}
      <div className="deck-detail-header">
        <button className="btn-secondary" onClick={() => navigate("/decks")}>&larr; 返回卡组列表</button>
        <div className="deck-detail-title">
          {editing ? (
            <form onSubmit={(e) => { e.preventDefault(); handleRename(); }} className="deck-rename-form">
              <input value={editName} onChange={(e) => setEditName(e.target.value)} autoFocus onBlur={handleRename} />
            </form>
          ) : (
            <h2 onClick={() => setEditing(true)} title="点击重命名">{deck.name}</h2>
          )}
          <select
            className={`deck-format-select format-${deck.format || "undefined"}`}
            value={deck.format || "undefined"}
            onChange={handleFormatChange}
            title="切换模式"
          >
            {FORMATS.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
          </select>
          <span className="deck-detail-count">{totalCards} 张卡牌</span>
        </div>
        <div className="deck-detail-actions">
          <button className="btn-secondary" onClick={() => setShowImportModal(true)}>导入牌表</button>
          <button className="btn-secondary" onClick={handleExportText} disabled={cards.length === 0}>复制牌表</button>
          <button className="btn-accent" onClick={handleExport} disabled={exporting || cards.length === 0}>
            {exporting ? "导出中..." : "导出 PDF"}
          </button>
          <button className="btn-danger" onClick={handleDelete}>删除卡组</button>
        </div>
      </div>

      {exportProgress && (
        <div className="export-progress">
          <div className="export-progress-bar">
            <div className="export-progress-fill" style={{ width: `${exportProgress.total > 0 ? (exportProgress.current / exportProgress.total) * 100 : 0}%` }} />
          </div>
          <span className="export-progress-text">
            {exportProgress.phase === "download" ? `下载卡牌图片 ${exportProgress.current}/${exportProgress.total}` : "生成 PDF..."}
          </span>
        </div>
      )}

      {importNotFound.length > 0 && (
        <div className="import-not-found">
          <div className="import-not-found-header">
            <span>以下 {importNotFound.length} 张卡牌未在数据库中找到：</span>
            <button className="import-not-found-close" onClick={() => setImportNotFound([])}>&times;</button>
          </div>
          <ul>{importNotFound.map((name, i) => <li key={i}>{name}</li>)}</ul>
        </div>
      )}

      {cards.length === 0 ? (
        <div className="no-results"><p>卡组为空，去搜索页面添加卡牌吧</p></div>
      ) : (
        <div className="deck-body">
          {/* Left: Card detail panel */}
          <aside className="deck-preview-panel">
            {selectedCard ? (
              <>
                <div className="deck-preview-image">
                  <img src={getCardFullImage(selectedCard)} alt={selectedCard.card.name} />
                </div>
                <div className="deck-preview-info">
                  <h3 className="deck-preview-name">{selectedCard.card.name}</h3>
                  {selectedCard.card.mana_cost && (
                    <span className="deck-preview-mana">{selectedCard.card.mana_cost}</span>
                  )}
                  <p className="deck-preview-type">{selectedCard.card.type_line}</p>
                  {selectedCard.card.oracle_text && (
                    <p className="deck-preview-oracle">{selectedCard.card.oracle_text}</p>
                  )}
                  {(selectedCard.card.power || selectedCard.card.toughness) && (
                    <p className="deck-preview-pt">{selectedCard.card.power}/{selectedCard.card.toughness}</p>
                  )}
                  {deck.format && deck.format !== "undefined" && (() => {
                    const legality = getCardLegality(selectedCard.card, deck.format);
                    return (
                      <span className={`legality-chip legality-${legality}`}>
                        {getFormatLabel(deck.format)}: {legalityLabel(legality)}
                      </span>
                    );
                  })()}
                </div>
              </>
            ) : (
              <div className="deck-preview-empty">
                <p>点击卡牌查看详情</p>
              </div>
            )}
          </aside>

          {/* Center: CSS columns layout */}
          <div className="deck-groups">
            {groupedCards.map((group) => (
              <div key={group.type} className="deck-type-group">
                <div className="deck-type-header">
                  <span className="deck-type-label">{group.label}</span>
                  <span className="deck-type-count">{group.count}</span>
                </div>
                <div className="deck-stack-grid">
                  {group.items.map((item) => {
                    const img = getCardDisplayImage(item);
                    const isSelected = selectedCard?.card_id === item.card_id;
                    const illegal = deck.format && deck.format !== "undefined" && !isCardLegal(item.card, deck.format);
                    return (
                      <div
                        key={item.card_id}
                        className={`deck-stack-card ${isSelected ? "selected" : ""}`}
                        onMouseEnter={() => setSelectedCard(item)}
                      >
                        {img ? (
                          <img src={img} alt={item.card.name} className="deck-stack-img" loading="lazy" />
                        ) : (
                          <div className="deck-stack-placeholder">{item.card.name}</div>
                        )}
                        <div className="deck-stack-overlay" />
                        <div className="deck-stack-name">
                          {illegal && <span className="deck-illegal-icon" title={`该卡牌在「${getFormatLabel(deck.format)}」中不合法`}>!</span>}
                          {item.card.name}
                        </div>
                        <div className="deck-stack-controls">
                          <button onClick={(e) => { e.stopPropagation(); handleQuantityChange(item.card_id, -1); }}>-</button>
                          <span>{item.quantity}</span>
                          <button onClick={(e) => { e.stopPropagation(); handleQuantityChange(item.card_id, 1); }}>+</button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          {/* Right: Deck Analysis */}
          {deckAnalysis && (
            <aside className="deck-analysis">
              <div className="analysis-card">
                <h3 className="analysis-title">卡牌类型</h3>
                <div className="analysis-bars">
                  {groupedCards.map((group) => (
                    <div key={group.type} className="analysis-bar-row">
                      <span className="analysis-bar-label">{group.label}</span>
                      <div className="analysis-bar-track">
                        <div
                          className="analysis-bar-fill type-bar"
                          style={{ width: `${(group.count / totalCards) * 100}%` }}
                        />
                      </div>
                      <span className="analysis-bar-value">{group.count}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="analysis-card">
                <h3 className="analysis-title">颜色分布</h3>
                {(() => {
                  const COLOR_HEX = { W: "#d5c67a", U: "#0e68ab", B: "#3d3a3a", R: "#d3202a", G: "#00733e" };
                  const colors = ["W", "U", "B", "R", "G"];
                  const total = deckAnalysis.totalColorCards;
                  let cumulative = 0;
                  const slices = colors.map((c) => {
                    const pct = (deckAnalysis.colorCounts[c] / total) * 100;
                    const start = cumulative;
                    cumulative += pct;
                    return { color: c, pct, start, hex: COLOR_HEX[c] };
                  });
                  const conicGradient = slices
                    .filter((s) => s.pct > 0)
                    .map((s) => `${s.hex} ${s.start}% ${s.start + s.pct}%`)
                    .join(", ");
                  return (
                    <div className="analysis-pie-container">
                      <div
                        className="analysis-pie"
                        style={{ background: conicGradient ? `conic-gradient(${conicGradient})` : "var(--bg-secondary)" }}
                      />
                      <div className="analysis-pie-legend">
                        {colors.map((c) => {
                          const count = deckAnalysis.colorCounts[c];
                          if (count === 0) return null;
                          return (
                            <div key={c} className="pie-legend-item">
                              <span className={`analysis-color-dot mana-${c}`} />
                              <span className="pie-legend-label">{deckAnalysis.colorLabels[c]}</span>
                              <span className="pie-legend-value">{count}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()}
              </div>

              <div className="analysis-card">
                <h3 className="analysis-title">法术力曲线</h3>
                <div className="analysis-mana-curve">
                  {deckAnalysis.cmcBuckets.map((count, i) => (
                    <div key={i} className="mana-curve-col">
                      <span className="mana-curve-value">{count || ""}</span>
                      <div className="mana-curve-bar-wrapper">
                        <div
                          className="mana-curve-bar"
                          style={{ height: `${(count / deckAnalysis.cmcMax) * 100}%` }}
                        />
                      </div>
                      <span className="mana-curve-label">{i < 7 ? i : "7+"}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="analysis-card">
                <h3 className="analysis-title">稀有度分布</h3>
                <div className="analysis-bars">
                  {deckAnalysis.rarityOrder.map((r) => {
                    const count = deckAnalysis.rarityCounts[r] || 0;
                    const totalRarity = cards.reduce((s, c) => s + c.quantity, 0) || 1;
                    return (
                      <div key={r} className="analysis-bar-row">
                        <span className="analysis-bar-label">{deckAnalysis.rarityLabels[r]}</span>
                        <div className="analysis-bar-track">
                          <div
                            className={`analysis-bar-fill rarity-bar-${r}`}
                            style={{ width: `${(count / totalRarity) * 100}%` }}
                          />
                        </div>
                        <span className="analysis-bar-value">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </aside>
          )}
        </div>
      )}

      {/* Import Modal */}
      {showImportModal && (
        <div className="modal-overlay" onClick={() => { setShowImportModal(false); setImportText(""); }}>
          <div className="modal-content import-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>导入牌表</h3>
              <button className="modal-close" onClick={() => { setShowImportModal(false); setImportText(""); }}>&times;</button>
            </div>
            <textarea
              className="import-textarea"
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder={"粘贴牌表文本，每行格式：数量 卡牌名称\n例如：\n1 Sol Ring\n4 Lightning Bolt\n9 Wastes"}
              autoFocus
              rows={12}
            />
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => { setShowImportModal(false); setImportText(""); }}>取消</button>
              <button className="btn-accent" onClick={handleImportSubmit} disabled={importing || !importText.trim()}>
                {importing ? "导入中..." : "导入"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DeckDetailPage;
