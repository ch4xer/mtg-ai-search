import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { addDeckCard, createDeck, fetchUserDecks, fetchSharedDeckCardsData, removeDeckCard } from "../api/decks.js";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { FORMATS, getFormatLabel } from "../utils/formats.js";
import { buildCardGroups, getCardDisplayImage, getCardFullImage, getLocalizedCardName, TYPE_MANA_CLASSES } from "../features/decks/deckModel.js";

function DeckExplorerSidebar({ isOpen, onClose }) {
  const [decks, setDecks] = useState([]);
  const [selectedDeckId, setSelectedDeckId] = useState(null);
  const [selectedDeckName, setSelectedDeckName] = useState("");
  const [deckCards, setDeckCards] = useState([]);
  const [loadingCards, setLoadingCards] = useState(false);
  const [newName, setNewName] = useState("");
  const [newFormat, setNewFormat] = useState("undefined");
  const [creating, setCreating] = useState(false);
  const [dragOverDeckId, setDragOverDeckId] = useState(null);
  const [dragOverContents, setDragOverContents] = useState(false);
  const [hoveredCard, setHoveredCard] = useState(null);
  const [previewTop, setPreviewTop] = useState(16);
  const [mutatingCardKey, setMutatingCardKey] = useState(null);
  const dragEnterCount = useRef(0);

  // Animation state machine: mounted → visible → slide-in, visible→false → slide-out → unmounted
  const [mounted, setMounted] = useState(false);
  const [visible, setVisible] = useState(false);
  const visibleRef = useRef(false);

  const { showToast } = useToast();
  const { t, language } = useLanguage();

  const fetchDecks = useCallback(async ({ force = false } = {}) => {
    try {
      setDecks(await fetchUserDecks({ force }));
    } catch {}
  }, []);

  useEffect(() => {
    if (isOpen) {
      fetchDecks();
      setSelectedDeckId(null);
      setDeckCards([]);
      setMounted(true);
      // Trigger slide-in on next frame so the browser paints the initial off-screen position first
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setVisible(true);
          visibleRef.current = true;
        });
      });
    } else {
      setVisible(false);
      visibleRef.current = false;
      // Wait for slide-out transition to finish before unmounting
      const timer = setTimeout(() => setMounted(false), 300);
      return () => clearTimeout(timer);
    }
  }, [isOpen, fetchDecks]);

  const handleClose = () => {
    onClose();
  };

  const loadDeckCards = useCallback(async (deckId, { force = false } = {}) => {
    return fetchSharedDeckCardsData(deckId, { force });
  }, []);

  const handleSelectDeck = async (deck, { force = false } = {}) => {
    setSelectedDeckId(deck.id);
    setSelectedDeckName(deck.name);
    setLoadingCards(true);
    setHoveredCard(null);
    try {
      const cards = await loadDeckCards(deck.id, { force });
      setDeckCards(cards);
    } catch {
      showToast(t("loadFailed"), "error");
      setSelectedDeckId(null);
      setSelectedDeckName("");
    } finally {
      setLoadingCards(false);
    }
  };

  const handleBack = () => {
    setSelectedDeckId(null);
    setSelectedDeckName("");
    setDeckCards([]);
    setHoveredCard(null);
  };

  const refreshSelectedDeck = async ({ force = true } = {}) => {
    if (!selectedDeckId) return;
    try {
      const [cards] = await Promise.all([
        loadDeckCards(selectedDeckId, { force }),
        fetchDecks({ force: true }),
      ]);
      setDeckCards(cards);
      setHoveredCard(null);
    } catch {
      showToast(t("loadFailed"), "error");
    }
  };

  const handleDragOver = (e, deckId) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    setDragOverDeckId(deckId);
  };

  const handleDragLeave = () => {
    setDragOverDeckId(null);
  };

  const handleContentsDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
    setDragOverContents(true);
  };

  const handleContentsDragEnter = () => {
    dragEnterCount.current += 1;
    setDragOverContents(true);
  };

  const handleContentsDragLeave = () => {
    dragEnterCount.current -= 1;
    if (dragEnterCount.current <= 0) {
      dragEnterCount.current = 0;
      setDragOverContents(false);
    }
  };

  const handleContentsDrop = async (e) => {
    e.preventDefault();
    dragEnterCount.current = 0;
    setDragOverContents(false);
    if (!selectedDeckId) return;
    try {
      const data = JSON.parse(e.dataTransfer.getData("application/json"));
      if (!data.card_id) return;
      const res = await addDeckCard(selectedDeckId, {
        card_id: data.card_id,
        quantity: 1,
        board: "mainboard",
      });
      if (res.ok) {
        await refreshSelectedDeck({ force: true });
        showToast(
          language === "zh"
            ? `「${data.name}」已加入「${selectedDeckName}」`
            : `"${data.name}" added to "${selectedDeckName}"`
        );
      } else {
        showToast(
          language === "zh" ? "添加失败" : "Failed to add card",
          "error"
        );
      }
    } catch {
      // ignore invalid drag data
    }
  };

  const handleDrop = async (e, deckId, deckName) => {
    e.preventDefault();
    setDragOverDeckId(null);
    try {
      const data = JSON.parse(e.dataTransfer.getData("application/json"));
      if (!data.card_id) return;
      const res = await addDeckCard(deckId, {
        card_id: data.card_id,
        quantity: 1,
        board: "mainboard",
      });
      if (res.ok) {
        // Refresh deck counts
        await fetchDecks({ force: true });
        showToast(
          language === "zh"
            ? `「${data.name}」已加入「${deckName}」`
            : `"${data.name}" added to "${deckName}"`
        );
        // If viewing this deck's contents, refresh them
        if (selectedDeckId === deckId) {
          handleSelectDeck({ id: deckId, name: deckName }, { force: true });
        }
      } else {
        showToast(
          language === "zh" ? "添加失败" : "Failed to add card",
          "error"
        );
      }
    } catch {
      // ignore invalid drag data
    }
  };

  const handleQuantityChange = async (item, delta) => {
    if (!selectedDeckId || mutatingCardKey) return;
    const board = item.board || "mainboard";
    const nextQuantity = item.quantity + delta;
    const mutationKey = `${item.card_id}:${board}`;
    setMutatingCardKey(mutationKey);
    try {
      const res = nextQuantity <= 0
        ? await removeDeckCard(selectedDeckId, item.card_id, board)
        : await addDeckCard(selectedDeckId, {
            card_id: item.card_id,
            quantity: delta,
            board,
          });

      if (!res.ok) {
        showToast(language === "zh" ? "更新数量失败" : "Failed to update quantity", "error");
        return;
      }

      await refreshSelectedDeck({ force: true });
    } catch {
      showToast(language === "zh" ? "更新数量失败" : "Failed to update quantity", "error");
    } finally {
      setMutatingCardKey(null);
    }
  };

  const handleCardHover = (item, element) => {
    const { top } = element.getBoundingClientRect();
    const previewHeight = 456;
    const viewportPadding = 16;
    const maxTop = Math.max(viewportPadding, window.innerHeight - previewHeight - viewportPadding);
    setPreviewTop(Math.min(Math.max(top, viewportPadding), maxTop));
    setHoveredCard(item);
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      const res = await createDeck({ name: newName.trim(), format: newFormat });
      if (res.ok) {
        const deck = await res.json();
        setDecks((prev) => [{ ...deck, card_count: 0 }, ...prev]);
        setNewName("");
        setNewFormat("undefined");
        showToast(language === "zh" ? `卡组「${deck.name}」已创建` : `Deck "${deck.name}" created`);
      }
    } catch {
      showToast(language === "zh" ? "创建失败" : "Failed to create", "error");
    } finally {
      setCreating(false);
    }
  };

  if (!mounted) return null;

  const groups = selectedDeckId
    ? buildCardGroups(deckCards, language)
    : [];
  const hoveredCardImage = hoveredCard ? getCardFullImage(hoveredCard) : "";
  const hoveredCardName = hoveredCard ? getLocalizedCardName(hoveredCard.card, language) : "";

  return createPortal(
    <>
      {hoveredCardImage && visible && (
        <div className="deck-explorer-card-preview" style={{ top: previewTop }} aria-hidden="true">
          <img src={hoveredCardImage} alt="" />
          <span>{hoveredCardName}</span>
        </div>
      )}
      <aside className={`deck-explorer-panel${visible ? " open" : ""}`}>
        {/* Header */}
        <div className="deck-explorer-header">
          {selectedDeckId ? (
            <button className="deck-explorer-back-btn" onClick={handleBack} title={t("back")}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
          ) : (
            <div className="deck-explorer-spacer" />
          )}
          <h3 className="deck-explorer-title">
            {selectedDeckId ? selectedDeckName : t("myDecks")}
          </h3>
          <button className="deck-explorer-close-btn" onClick={handleClose} title={t("close")}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="deck-explorer-body" onScroll={() => setHoveredCard(null)}>
          {!selectedDeckId ? (
            <>
              {/* New Deck Form */}
              <form onSubmit={handleCreate} className="deck-explorer-new-deck">
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder={language === "zh" ? "新建卡组..." : "New deck..."}
                  disabled={creating}
                  className="deck-explorer-input"
                />
                <select
                  className="deck-explorer-format-select"
                  value={newFormat}
                  onChange={(e) => setNewFormat(e.target.value)}
                  disabled={creating}
                >
                  {FORMATS.map((f) => (
                    <option key={f.key} value={f.key}>
                      {language === "zh" ? f.labelZh : f.labelEn}
                    </option>
                  ))}
                </select>
                <button
                  type="submit"
                  className="deck-explorer-create-btn"
                  disabled={creating || !newName.trim()}
                >
                  +
                </button>
              </form>

              {/* Deck List */}
              <div className="deck-explorer-list">
                {decks.map((deck) => (
                  <button
                    key={deck.id}
                    className={`deck-explorer-deck-item${dragOverDeckId === deck.id ? " drag-over" : ""}`}
                    onClick={() => handleSelectDeck(deck)}
                    onDragOver={(e) => handleDragOver(e, deck.id)}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDrop(e, deck.id, deck.name)}
                  >
                    <div className="deck-explorer-deck-info">
                      <span className="deck-explorer-deck-name">{deck.name}</span>
                      <span className={`format-badge format-${deck.format || "undefined"}`}>
                        {getFormatLabel(deck.format, language)}
                      </span>
                    </div>
                    <span className="deck-explorer-deck-count">
                      {deck.card_count || 0}
                    </span>
                  </button>
                ))}
                {decks.length === 0 && (
                  <p className="deck-explorer-empty">
                    {language === "zh" ? "还没有卡组" : "No decks yet"}
                  </p>
                )}
              </div>
            </>
          ) : loadingCards ? (
            <div className="deck-explorer-loading">
              <div className="loading-spinner" />
              <p>{t("loading")}</p>
            </div>
          ) : (
            /* Deck Contents */
            <div
              className={`deck-explorer-contents${dragOverContents ? " drag-over" : ""}`}
              onDragOver={handleContentsDragOver}
              onDragEnter={handleContentsDragEnter}
              onDragLeave={handleContentsDragLeave}
              onDrop={handleContentsDrop}
            >
              {groups.map((group) => (
                <div key={group.type} className="deck-explorer-type-group">
                  <div className="deck-explorer-type-header">
                    {TYPE_MANA_CLASSES[group.type] && (
                      <i className={`ms ${TYPE_MANA_CLASSES[group.type]} deck-explorer-type-icon`} />
                    )}
                    <span className="deck-explorer-type-label">{group.label}</span>
                    <span className="deck-explorer-type-count">{group.count}</span>
                  </div>
                  <div className="deck-explorer-card-list">
                    {group.items.map((item, idx) => (
                      <div
                        key={`${item.card_id}-${item.board || "main"}-${idx}`}
                        className="deck-explorer-card-item"
                        onMouseEnter={(e) => handleCardHover(item, e.currentTarget)}
                        onMouseLeave={() => setHoveredCard(null)}
                      >
                        {getCardDisplayImage(item) ? (
                          <img
                            className="deck-explorer-card-img"
                            src={getCardDisplayImage(item)}
                            alt=""
                            loading="lazy"
                          />
                        ) : (
                          <div className="deck-explorer-card-placeholder">
                            {getLocalizedCardName(item.card, language)}
                          </div>
                        )}
                        <div className="deck-explorer-card-overlay" />
                        <span className="deck-explorer-card-name">
                          {getLocalizedCardName(item.card, language)}
                        </span>
                        <div className="deck-explorer-card-counter">
                          <button
                            type="button"
                            className="deck-explorer-counter-btn"
                            onClick={() => handleQuantityChange(item, -1)}
                            disabled={mutatingCardKey === `${item.card_id}:${item.board || "mainboard"}`}
                            title={language === "zh" ? "减少数量" : "Decrease quantity"}
                          >
                            -
                          </button>
                          <span className="deck-explorer-card-qty">{item.quantity}</span>
                          <button
                            type="button"
                            className="deck-explorer-counter-btn"
                            onClick={() => handleQuantityChange(item, 1)}
                            disabled={mutatingCardKey === `${item.card_id}:${item.board || "mainboard"}`}
                            title={language === "zh" ? "增加数量" : "Increase quantity"}
                          >
                            +
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {groups.length === 0 && (
                <p className="deck-explorer-empty">
                  {language === "zh" ? "卡组为空" : "Deck is empty"}
                </p>
              )}
            </div>
          )}
        </div>
      </aside>
    </>,
    document.body
  );
}

export default DeckExplorerSidebar;
