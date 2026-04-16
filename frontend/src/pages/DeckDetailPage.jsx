import React, { useState, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiFetch, getAccessToken } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { FORMATS, getFormatLabel, getCardLegality, isCardLegal, legalityLabel } from "../utils/formats.js";
import { getImageUri } from "../utils/cardImage.js";
import { parseManaCost, parseOracleText } from "../utils/manaSymbols.js";

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

const TYPE_LABELS_EN = {
  Creature: "Creature", Planeswalker: "Planeswalker", Instant: "Instant", Sorcery: "Sorcery",
  Enchantment: "Enchantment", Artifact: "Artifact", Land: "Land", Other: "Other",
};

const TYPE_LABELS_ZH = {
  Creature: "生物", Planeswalker: "旅法师", Instant: "瞬间", Sorcery: "法术",
  Enchantment: "结界", Artifact: "神器", Land: "地", Other: "其他",
};

const TYPE_MANA_CLASSES = {
  Creature: "ms-creature",
  Planeswalker: "ms-planeswalker",
  Instant: "ms-instant",
  Sorcery: "ms-sorcery",
  Enchantment: "ms-enchantment",
  Artifact: "ms-artifact",
  Land: "ms-land",
  Other: null,
};


/* ── Main Component ── */

function DeckDetailPage({ imageMode }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { t, language } = useLanguage();
  const [deck, setDeck] = useState(null);
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [exporting, setExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(null);
  const [exportingImages, setExportingImages] = useState(false);
  const [exportImagesProgress, setExportImagesProgress] = useState(null);
  const [importing, setImporting] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importText, setImportText] = useState("");
  const [importNotFound, setImportNotFound] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [showExportMenu, setShowExportMenu] = useState(false);

  const TYPE_LABELS = language === 'zh' ? TYPE_LABELS_ZH : TYPE_LABELS_EN;

  // ── Data fetching ──

  const fetchDeck = async () => {
    try {
      const [deckRes, cardsRes] = await Promise.all([
        apiFetch(`/api/decks/${id}`),
        apiFetch(`/api/decks/${id}/cards`),
      ]);
      if (deckRes.status === 404) {
        showToast(t('deckNotFound'), "error");
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
      showToast(t('loadFailed'), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDeck(); }, [id]);

  // Close export dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (showExportMenu && !e.target.closest('.export-dropdown')) {
        setShowExportMenu(false);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [showExportMenu]);

  // ── Group cards by board, then by type ──

  const { mainboardGroups, sideboardGroups } = useMemo(() => {
    const buildGroups = (boardCards) => {
      const groups = {};
      for (const item of boardCards) {
        const type = classifyCard(item.card);
        if (!groups[type]) groups[type] = [];
        groups[type].push(item);
      }
      const ordered = [];
      for (const type of TYPE_ORDER) {
        if (groups[type]) {
          const count = groups[type].reduce((s, c) => s + c.quantity, 0);
          ordered.push({ type, label: TYPE_LABELS[type], count, items: groups[type] });
        }
      }
      return ordered;
    };
    const mainCards = cards.filter((c) => c.board !== "sideboard");
    const sideCards = cards.filter((c) => c.board === "sideboard");
    return { mainboardGroups: buildGroups(mainCards), sideboardGroups: buildGroups(sideCards) };
  }, [cards, language]);

  // Combined for analysis (kept for compatibility)
  const groupedCards = useMemo(() => {
    const groups = {};
    for (const item of cards) {
      const type = classifyCard(item.card);
      if (!groups[type]) groups[type] = [];
      groups[type].push(item);
    }
    const ordered = [];
    for (const type of TYPE_ORDER) {
      if (groups[type]) {
        const count = groups[type].reduce((s, c) => s + c.quantity, 0);
        ordered.push({ type, label: TYPE_LABELS[type], count, items: groups[type] });
      }
    }
    return ordered;
  }, [cards, language]);

  // ── Deck analysis ──

  const deckAnalysis = useMemo(() => {
    if (cards.length === 0) return null;

    // Color distribution
    const colorCounts = { W: 0, U: 0, B: 0, R: 0, G: 0 };
    const colorLabelsEn = { W: "White", U: "Blue", B: "Black", R: "Red", G: "Green" };
    const colorLabelsZh = { W: "白", U: "蓝", B: "黑", R: "红", G: "绿" };
    const colorLabels = language === 'zh' ? colorLabelsZh : colorLabelsEn;
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
    const rarityLabelsEn = { common: "Common", uncommon: "Uncommon", rare: "Rare", mythic: "Mythic" };
    const rarityLabelsZh = { common: "普通", uncommon: "非普通", rare: "稀有", mythic: "秘稀" };
    const rarityLabels = language === 'zh' ? rarityLabelsZh : rarityLabelsEn;
    const rarityCounts = {};
    for (const item of cards) {
      const r = item.card.rarity || "common";
      rarityCounts[r] = (rarityCounts[r] || 0) + item.quantity;
    }

    const totalColorCards = Object.values(colorCounts).reduce((s, v) => s + v, 0) || 1;

    return { colorCounts, colorLabels, totalColorCards, cmcBuckets, cmcMax, rarityCounts, rarityLabels, rarityOrder };
  }, [cards, language]);

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
      showToast(t('deckRenamed'));
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
      showToast(language === 'zh' ? `赛制已切换为「${getFormatLabel(updated.format)}」` : `Format changed to "${getFormatLabel(updated.format)}"`);
    }
  };

  const handleDelete = async () => {
    if (!confirm(language === 'zh' ? "确定要删除这个卡组吗？" : "Are you sure you want to delete this deck?")) return;
    const res = await apiFetch(`/api/decks/${id}`, { method: "DELETE" });
    if (res.ok) {
      showToast(t('deckDeleted'));
      navigate("/decks");
    }
  };

  const handleQuantityChange = async (cardId, delta, board = "mainboard") => {
    const card = cards.find((c) => c.card_id === cardId && c.board === board);
    if (!card) return;
    const newQty = card.quantity + delta;
    if (newQty <= 0) {
      await handleRemoveCard(cardId, board);
      return;
    }
    const res = await apiFetch(`/api/decks/${id}/cards`, {
      method: "POST",
      body: { card_id: cardId, quantity: delta, board },
    });
    if (res.ok) {
      setCards((prev) =>
        prev.map((c) => (c.card_id === cardId && c.board === board ? { ...c, quantity: newQty } : c))
      );
      if (selectedCard?.card_id === cardId && selectedCard?.board === board) {
        setSelectedCard((prev) => ({ ...prev, quantity: newQty }));
      }
    }
  };

  const handleRemoveCard = async (cardId, board) => {
    const boardParam = board ? `?board=${board}` : "";
    const res = await apiFetch(`/api/decks/${id}/cards/${cardId}${boardParam}`, { method: "DELETE" });
    if (res.ok) {
      setCards((prev) => prev.filter((c) => !(c.card_id === cardId && c.board === board)));
      if (selectedCard?.card_id === cardId && selectedCard?.board === board) setSelectedCard(null);
      showToast(t('cardRemoved'));
    }
  };

  const handleExport = async () => {
    setShowExportMenu(false);
    setExporting(true);
    setExportProgress({ phase: "download", current: 0, total: 0 });
    try {
      const token = getAccessToken();
      const res = await fetch(`/api/decks/${id}/export/stream`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t('exportFailed'), "error");
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
        if (!pdfRes.ok) { showToast(language === 'zh' ? "下载 PDF 失败" : "Failed to download PDF", "error"); return; }
        const blob = await pdfRes.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${deck?.name || "deck"}_cards.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        showToast(t('exportSuccess'));
      }
    } catch { showToast(t('exportFailed'), "error"); }
    finally { setExporting(false); setExportProgress(null); }
  };

  const handleExportImages = async () => {
    setShowExportMenu(false);
    setExportingImages(true);
    setExportImagesProgress({ phase: "download", current: 0, total: 0 });
    try {
      const token = getAccessToken();
      const res = await fetch(`/api/decks/${id}/export/images/stream`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t('exportFailed'), "error");
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
          if (data.type === "progress") setExportImagesProgress(data);
          else if (data.type === "complete") exportId = data.export_id;
        }
      }
      if (exportId) {
        const zipRes = await apiFetch(`/api/decks/${id}/export/images/download/${exportId}`);
        if (!zipRes.ok) { showToast(language === 'zh' ? "下载 ZIP 失败" : "Failed to download ZIP", "error"); return; }
        const blob = await zipRes.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${deck?.name || "deck"}_images.zip`;
        a.click();
        URL.revokeObjectURL(url);
        showToast(t('exportImagesSuccess'));
      }
    } catch { showToast(t('exportFailed'), "error"); }
    finally { setExportingImages(false); setExportImagesProgress(null); }
  };

  const handleExportText = async () => {
    try {
      const res = await apiFetch(`/api/decks/${id}/export/text`);
      if (!res.ok) { showToast(((await res.json().catch(() => ({}))).detail) || t('copyFailed'), "error"); return; }
      const text = await res.text();
      await navigator.clipboard.writeText(text);
      showToast(t('decklistCopied'));
    } catch { showToast(t('copyFailed'), "error"); }
  };

  const handleImportSubmit = async () => {
    if (!importText.trim()) return;
    setImporting(true);
    try {
      const res = await apiFetch(`/api/decks/${id}/import`, { method: "POST", body: { text: importText } });
      if (!res.ok) { showToast(((await res.json().catch(() => ({}))).detail) || language === 'zh' ? "导入失败" : "Import failed", "error"); return; }
      const data = await res.json();
      const addedCount = data.added.reduce((s, c) => s + c.quantity, 0);
      const notFoundCount = data.not_found.length;
      const msg = language === 'zh'
        ? `成功导入 ${addedCount} 张卡牌${notFoundCount > 0 ? `，${notFoundCount} 张未找到` : ""}`
        : `Successfully imported ${addedCount} cards${notFoundCount > 0 ? `, ${notFoundCount} not found` : ""}`;
      showToast(msg, notFoundCount > 0 ? "warning" : "success");
      if (notFoundCount > 0) setImportNotFound(data.not_found);
      setShowImportModal(false);
      setImportText("");
      await fetchDeck();
    } catch { showToast(language === 'zh' ? "导入失败" : "Import failed", "error"); }
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
        <p>{t('loadingDeck')}</p>
      </div>
    );
  }
  if (!deck) return null;

  const mainboardCount = cards.filter((c) => c.board !== "sideboard").reduce((sum, c) => sum + c.quantity, 0);
  const sideboardCount = cards.filter((c) => c.board === "sideboard").reduce((sum, c) => sum + c.quantity, 0);
  const totalCards = mainboardCount + sideboardCount;

  return (
    <div className="deck-detail">
      {/* Header */}
      <div className="deck-detail-header">
        <button className="btn-secondary" onClick={() => navigate("/decks")}>&larr; {t('backToDecks')}</button>
        <div className="deck-detail-title">
          {editing ? (
            <form onSubmit={(e) => { e.preventDefault(); handleRename(); }} className="deck-rename-form">
              <input value={editName} onChange={(e) => setEditName(e.target.value)} autoFocus onBlur={handleRename} />
            </form>
          ) : (
            <h2 onClick={() => setEditing(true)} title={t('clickToRename')}>{deck.name}</h2>
          )}
          <select
            className={`deck-format-select format-${deck.format || "undefined"}`}
            value={deck.format || "undefined"}
            onChange={handleFormatChange}
            title={t('switchFormat')}
          >
            {FORMATS.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
          </select>
          <span className="deck-detail-count">
            {totalCards} {t('cardsCount')}{sideboardCount > 0 && ` (${t('mainboardCards')} ${mainboardCount} / ${t('sideboardCards')} ${sideboardCount})`}
          </span>
        </div>
        <div className="deck-detail-actions">
          <button className="btn-secondary" onClick={() => setShowImportModal(true)}>{t('importDecklist')}</button>
          <button className="btn-secondary" onClick={handleExportText} disabled={cards.length === 0}>{t('copyDecklist')}</button>
          <div className="export-dropdown">
            <button
              className="btn-accent"
              onClick={() => setShowExportMenu(!showExportMenu)}
              disabled={(exporting || exportingImages) || cards.length === 0}
            >
              {exporting || exportingImages ? `${t('downloadProgress')}...` : t('exportDeck')}
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: '4px' }}>
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {showExportMenu && (
              <div className="export-dropdown-menu">
                <button onClick={handleExport} disabled={exporting}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="3" width="20" height="18" rx="2" ry="2" />
                    <line x1="2" y1="7" x2="22" y2="7" />
                    <line x1="2" y1="17" x2="22" y2="17" />
                  </svg>
                  {t('exportPdf')}
                </button>
                <button onClick={handleExportImages} disabled={exportingImages}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                    <circle cx="8.5" cy="8.5" r="1.5" />
                    <polyline points="21 15 16 10 5 21" />
                  </svg>
                  {t('exportImages')}
                </button>
              </div>
            )}
          </div>
          <button className="btn-danger" onClick={handleDelete}>{t('deleteDeck')}</button>
        </div>
      </div>

      {exportProgress && (
        <div className="export-progress">
          <div className="export-progress-bar">
            <div className="export-progress-fill" style={{ width: `${exportProgress.total > 0 ? (exportProgress.current / exportProgress.total) * 100 : 0}%` }} />
          </div>
          <span className="export-progress-text">
            {exportProgress.phase === "download"
              ? `${t('downloadProgress')} ${exportProgress.current}/${exportProgress.total}`
              : t('generatingPdf')}
          </span>
        </div>
      )}

      {exportImagesProgress && (
        <div className="export-progress">
          <div className="export-progress-bar">
            <div className="export-progress-fill" style={{ width: `${exportImagesProgress.total > 0 ? (exportImagesProgress.current / exportImagesProgress.total) * 100 : 0}%` }} />
          </div>
          <span className="export-progress-text">
            {exportImagesProgress.phase === "download"
              ? `${t('downloadProgress')} ${exportImagesProgress.current}/${exportImagesProgress.total}`
              : t('generatingZip')}
          </span>
        </div>
      )}

      {importNotFound.length > 0 && (
        <div className="import-not-found">
          <div className="import-not-found-header">
            <span>{language === 'zh' ? `以下 ${importNotFound.length} 张卡牌未在数据库中找到：` : `The following ${importNotFound.length} cards were not found in the database:`}</span>
            <button className="import-not-found-close" onClick={() => setImportNotFound([])}>&times;</button>
          </div>
          <ul>{importNotFound.map((name, i) => <li key={i}>{name}</li>)}</ul>
        </div>
      )}

      {cards.length === 0 ? (
        <div className="no-results"><p>{t('deckEmpty')}</p></div>
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
                    <span className="deck-preview-mana">
                      {parseManaCost(selectedCard.card.mana_cost).map((sym, idx) =>
                        sym.half ? (
                          <span key={idx} className="ms-half">
                            <i className={`ms ${sym.classes}`} aria-hidden="true" />
                          </span>
                        ) : (
                          <i key={idx} className={`ms ${sym.classes}`} aria-hidden="true" />
                        )
                      )}
                    </span>
                  )}
                  <p className="deck-preview-type">{selectedCard.card.type_line}</p>
                  {selectedCard.card.oracle_text && (
                    <p className="deck-preview-oracle">{parseOracleText(selectedCard.card.oracle_text, React.createElement)}</p>
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
                <p>{t('clickCardDetails')}</p>
              </div>
            )}
          </aside>

          {/* Center: CSS columns layout */}
          <div className="deck-groups">
            {mainboardGroups.length > 0 && (
              <>
                {sideboardGroups.length > 0 && (
                  <div className="deck-board-header">{t('mainboard')} ({mainboardCount})</div>
                )}
                {mainboardGroups.map((group) => (
                  <div key={group.type} className="deck-type-group">
                    <div className="deck-type-header">
                      {TYPE_MANA_CLASSES[group.type] && (
                        <span className="deck-type-icon">
                          <i className={`ms ${TYPE_MANA_CLASSES[group.type]}`} aria-hidden="true" />
                        </span>
                      )}
                      <span className="deck-type-label">{group.label}</span>
                      <span className="deck-type-count">{group.count}</span>
                    </div>
                    <div className="deck-stack-grid">
                      {group.items.map((item) => {
                        const img = getCardDisplayImage(item);
                        const isSelected = selectedCard?.card_id === item.card_id && selectedCard?.board === item.board;
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
                              {illegal && <span className="deck-illegal-icon" title={t('cardIllegalInFormat')}>!</span>}
                              {item.card.name}
                            </div>
                            <div className="deck-stack-controls">
                              <button onClick={(e) => { e.stopPropagation(); handleQuantityChange(item.card_id, -1, item.board); }}>-</button>
                              <span>{item.quantity}</span>
                              <button onClick={(e) => { e.stopPropagation(); handleQuantityChange(item.card_id, 1, item.board); }}>+</button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </>
            )}
            {sideboardGroups.length > 0 && (
              <>
                <div className="deck-board-header">{t('sideboard')} ({sideboardCount})</div>
                {sideboardGroups.map((group) => (
                  <div key={`side-${group.type}`} className="deck-type-group">
                    <div className="deck-type-header">
                      {TYPE_MANA_CLASSES[group.type] && (
                        <span className="deck-type-icon">
                          <i className={`ms ${TYPE_MANA_CLASSES[group.type]}`} aria-hidden="true" />
                        </span>
                      )}
                      <span className="deck-type-label">{group.label}</span>
                      <span className="deck-type-count">{group.count}</span>
                    </div>
                    <div className="deck-stack-grid">
                      {group.items.map((item) => {
                        const img = getCardDisplayImage(item);
                        const isSelected = selectedCard?.card_id === item.card_id && selectedCard?.board === item.board;
                        const illegal = deck.format && deck.format !== "undefined" && !isCardLegal(item.card, deck.format);
                        return (
                          <div
                            key={`side-${item.card_id}`}
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
                              {illegal && <span className="deck-illegal-icon" title={t('cardIllegalInFormat')}>!</span>}
                              {item.card.name}
                            </div>
                            <div className="deck-stack-controls">
                              <button onClick={(e) => { e.stopPropagation(); handleQuantityChange(item.card_id, -1, item.board); }}>-</button>
                              <span>{item.quantity}</span>
                              <button onClick={(e) => { e.stopPropagation(); handleQuantityChange(item.card_id, 1, item.board); }}>+</button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>

          {/* Right: Deck Analysis */}
          {deckAnalysis && (
            <aside className="deck-analysis">
              <div className="analysis-card">
                <h3 className="analysis-title">{t('cardTypes')}</h3>
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
                <h3 className="analysis-title">{t('colorDistribution')}</h3>
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
                <h3 className="analysis-title">{t('manaCurve')}</h3>
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
                <h3 className="analysis-title">{t('rarityDistribution')}</h3>
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
              <h3>{t('importDecklist')}</h3>
              <button className="modal-close" onClick={() => { setShowImportModal(false); setImportText(""); }}>&times;</button>
            </div>
            <textarea
              className="import-textarea"
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder={t('importPlaceholder')}
              autoFocus
              rows={12}
            />
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => { setShowImportModal(false); setImportText(""); }}>{t('cancel')}</button>
              <button className="btn-accent" onClick={handleImportSubmit} disabled={importing || !importText.trim()}>
                {importing ? `${language === 'zh' ? '导入中...' : 'Importing...'}` : `${language === 'zh' ? '导入' : 'Import'}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default DeckDetailPage;
