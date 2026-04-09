import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiFetch, getAccessToken } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";

function getImageUri(imageUris, mode) {
  if (!imageUris) return "";
  return imageUris[mode] || imageUris.normal || imageUris.small || "";
}

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
  const [artPickerCardId, setArtPickerCardId] = useState(null);
  const [printsCache, setPrintsCache] = useState({});
  const [loadingPrints, setLoadingPrints] = useState(false);
  const [artCropOverrides, setArtCropOverrides] = useState({});
  const artRef = useRef(null);

  const fetchDeck = async () => {
    try {
      const [deckRes, cardsRes] = await Promise.all([
        apiFetch(`/api/decks`),
        apiFetch(`/api/decks/${id}/cards`),
      ]);
      if (deckRes.ok && cardsRes.ok) {
        const allDecks = await deckRes.json();
        const deckData = allDecks.find((d) => d.id === id);
        if (!deckData) {
          showToast("卡组不存在", "error");
          navigate("/decks");
          return;
        }
        setDeck(deckData);
        setEditName(deckData.name);
        setCards(await cardsRes.json());
      }
    } catch (err) {
      showToast("加载失败", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeck();
  }, [id]);

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
    }
  };

  const handleRemoveCard = async (cardId) => {
    const res = await apiFetch(`/api/decks/${id}/cards/${cardId}`, {
      method: "DELETE",
    });
    if (res.ok) {
      setCards((prev) => prev.filter((c) => c.card_id !== cardId));
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
          if (data.type === "progress") {
            setExportProgress(data);
          } else if (data.type === "complete") {
            exportId = data.export_id;
          }
        }
      }

      if (exportId) {
        const pdfRes = await apiFetch(`/api/decks/${id}/export/download/${exportId}`);
        if (!pdfRes.ok) {
          showToast("下载 PDF 失败", "error");
          return;
        }
        const blob = await pdfRes.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${deck?.name || "deck"}_cards.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        showToast("PDF 导出成功");
      }
    } catch {
      showToast("导出失败", "error");
    } finally {
      setExporting(false);
      setExportProgress(null);
    }
  };

  const handleExportText = async () => {
    try {
      const res = await apiFetch(`/api/decks/${id}/export/text`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "导出失败", "error");
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${deck?.name || "deck"}.txt`;
      a.click();
      URL.revokeObjectURL(url);
      showToast("牌表导出成功");
    } catch {
      showToast("导出失败", "error");
    }
  };

  const handleImportSubmit = async () => {
    if (!importText.trim()) return;
    setImporting(true);
    try {
      const res = await apiFetch(`/api/decks/${id}/import`, {
        method: "POST",
        body: { text: importText },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "导入失败", "error");
        return;
      }
      const data = await res.json();
      const addedCount = data.added.reduce((s, c) => s + c.quantity, 0);
      const notFoundCount = data.not_found.length;
      showToast(`成功导入 ${addedCount} 张卡牌${notFoundCount > 0 ? `，${notFoundCount} 张未找到` : ""}`, notFoundCount > 0 ? "warning" : "success");
      if (notFoundCount > 0) {
        setImportNotFound(data.not_found);
      }
      setShowImportModal(false);
      setImportText("");
      await fetchDeck();
    } catch {
      showToast("导入失败", "error");
    } finally {
      setImporting(false);
    }
  };

  // Close art picker on outside click
  useEffect(() => {
    if (!artPickerCardId) return;
    const handleClick = (e) => {
      if (artRef.current && !artRef.current.contains(e.target)) {
        setArtPickerCardId(null);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [artPickerCardId]);

  const handleToggleArtPicker = async (item) => {
    const cardId = item.card_id;
    if (artPickerCardId === cardId) {
      setArtPickerCardId(null);
      return;
    }
    setArtPickerCardId(cardId);
    if (printsCache[cardId]) return;

    const searchUri = item.card.prints_search_uri;
    if (!searchUri) return;

    setLoadingPrints(true);
    try {
      const res = await fetch(searchUri);
      if (!res.ok) return;
      const data = await res.json();
      const allPrints = (data.data || [])
        .filter((p) => p.image_uris?.png)
        .map((p) => ({
          id: p.id,
          png: p.image_uris.png,
          artCrop: p.image_uris.art_crop || "",
          imageUri: getImageUri(p.image_uris, imageMode),
          setName: p.set_name,
          artist: p.artist,
        }));
      setPrintsCache((prev) => ({ ...prev, [cardId]: allPrints }));
    } catch {
      showToast("获取版本列表失败", "error");
    } finally {
      setLoadingPrints(false);
    }
  };

  const handleSelectArt = async (item, print) => {
    setArtPickerCardId(null);
    try {
      const res = await apiFetch(`/api/decks/${id}/cards`, {
        method: "POST",
        body: { card_id: item.card_id, quantity: 0, image_url: print.png, display_url: print.artCrop },
      });
      if (res.ok) {
        setCards((prev) =>
          prev.map((c) =>
            c.card_id === item.card_id ? { ...c, image_url: print.png } : c
          )
        );
        setArtCropOverrides((prev) => ({ ...prev, [item.card_id]: print.artCrop }));
        showToast(`已切换「${item.card.name}」卡图`);
      }
    } catch {
      showToast("切换卡图失败", "error");
    }
  };

  const handleResetArt = async (item) => {
    setArtPickerCardId(null);
    try {
      const res = await apiFetch(`/api/decks/${id}/cards`, {
        method: "POST",
        body: { card_id: item.card_id, quantity: 0, image_url: null, display_url: null },
      });
      if (res.ok) {
        setCards((prev) =>
          prev.map((c) =>
            c.card_id === item.card_id ? { ...c, image_url: null } : c
          )
        );
        setArtCropOverrides((prev) => {
          const next = { ...prev };
          delete next[item.card_id];
          return next;
        });
        showToast("已恢复默认卡图");
      }
    } catch {
      showToast("恢复卡图失败", "error");
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

  if (!deck) return null;

  const totalCards = cards.reduce((sum, c) => sum + c.quantity, 0);

  const getCardDisplayImage = (item) => {
    if (artCropOverrides[item.card_id]) return artCropOverrides[item.card_id];
    if (item.display_url) return item.display_url;
    return getImageUri(item.card.image_uris, "art_crop")
      || getImageUri(item.card.card_faces?.[0]?.image_uris, "art_crop");
  };

  return (
    <div className="deck-detail">
      <div className="deck-detail-header">
        <button className="btn-secondary" onClick={() => navigate("/decks")}>
          &larr; 返回卡组列表
        </button>
        <div className="deck-detail-title">
          {editing ? (
            <form onSubmit={(e) => { e.preventDefault(); handleRename(); }} className="deck-rename-form">
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                autoFocus
                onBlur={handleRename}
              />
            </form>
          ) : (
            <h2 onClick={() => setEditing(true)} title="点击重命名">
              {deck.name}
            </h2>
          )}
          <span className="deck-detail-count">{totalCards} 张卡牌</span>
        </div>
        <div className="deck-detail-actions">
          <button className="btn-secondary" onClick={() => setShowImportModal(true)}>
            导入牌表
          </button>
          <button className="btn-secondary" onClick={handleExportText} disabled={cards.length === 0}>
            导出牌表
          </button>
          <button className="btn-accent" onClick={handleExport} disabled={exporting || cards.length === 0}>
            {exporting ? "导出中..." : "导出 PDF"}
          </button>
          <button className="btn-danger" onClick={handleDelete}>
            删除卡组
          </button>
        </div>
      </div>

      {exportProgress && (
        <div className="export-progress">
          <div className="export-progress-bar">
            <div
              className="export-progress-fill"
              style={{ width: `${exportProgress.total > 0 ? (exportProgress.current / exportProgress.total) * 100 : 0}%` }}
            />
          </div>
          <span className="export-progress-text">
            {exportProgress.phase === "download"
              ? `下载卡牌图片 ${exportProgress.current}/${exportProgress.total}`
              : "生成 PDF..."}
          </span>
        </div>
      )}

      {importNotFound.length > 0 && (
        <div className="import-not-found">
          <div className="import-not-found-header">
            <span>以下 {importNotFound.length} 张卡牌未在数据库中找到：</span>
            <button className="import-not-found-close" onClick={() => setImportNotFound([])}>
              &times;
            </button>
          </div>
          <ul>
            {importNotFound.map((name, i) => (
              <li key={i}>{name}</li>
            ))}
          </ul>
        </div>
      )}

      {cards.length === 0 ? (
        <div className="no-results">
          <p>卡组为空，去搜索页面添加卡牌吧</p>
        </div>
      ) : (
        <div className="deck-cards-list">
          {cards.map((item) => {
            const displayImg = getCardDisplayImage(item);
            const pickerOpen = artPickerCardId === item.card_id;
            const prints = printsCache[item.card_id] || [];
            return (
              <div key={item.card_id} className="deck-card-item-wrapper">
                <div className="deck-card-item">
                  <div className="deck-card-image">
                    {displayImg ? (
                      <img src={displayImg} alt={item.card.name} loading="lazy" />
                    ) : (
                      <div className="card-image-placeholder"><span>{item.card.name}</span></div>
                    )}
                  </div>
                  <div className="deck-card-info">
                    <h4>{item.card.name}</h4>
                    <p className="card-type">{item.card.type_line}</p>
                    {item.card.mana_cost && <span className="card-mana">{item.card.mana_cost}</span>}
                  </div>
                  <div className="deck-card-controls">
                    {item.card.prints_search_uri && (
                      <button
                        className="deck-art-btn"
                        onClick={() => handleToggleArtPicker(item)}
                        title="切换卡图"
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="3" y="3" width="7" height="7" />
                          <rect x="14" y="3" width="7" height="7" />
                          <rect x="3" y="14" width="7" height="7" />
                          <rect x="14" y="14" width="7" height="7" />
                        </svg>
                      </button>
                    )}
                    <button onClick={() => handleQuantityChange(item.card_id, -1)}>-</button>
                    <span className="deck-card-qty">{item.quantity}</span>
                    <button onClick={() => handleQuantityChange(item.card_id, 1)}>+</button>
                    <button className="btn-remove" onClick={() => handleRemoveCard(item.card_id)} title="移除">
                      &times;
                    </button>
                  </div>
                </div>
                {pickerOpen && (
                  <div className="art-picker deck-art-picker" ref={artRef}>
                    <div className="art-picker-header">
                      <span>选择卡图版本 ({prints.length})</span>
                      {item.image_url && (
                        <button className="art-picker-reset" onClick={() => handleResetArt(item)}>恢复默认</button>
                      )}
                    </div>
                    {loadingPrints && prints.length === 0 ? (
                      <div className="art-picker-loading">加载中...</div>
                    ) : (
                      <div className="art-picker-grid">
                        {prints.map((p) => (
                          <div
                            key={p.id}
                            className={`art-picker-item ${item.image_url === p.png ? "selected" : ""}`}
                            onClick={() => handleSelectArt(item, p)}
                            title={`${p.setName} - ${p.artist}`}
                          >
                            <img src={p.imageUri} alt={p.setName} loading="lazy" />
                            <span className="art-picker-label">{p.setName}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
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
