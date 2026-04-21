import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import { apiFetch } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { getFormatLabel, getCardLegality, legalityLabel } from "../utils/formats.js";
import { getImageUri } from "../utils/cardImage.js";
import { getSetIconClass } from "../utils/keyrune.js";
import { parseManaCost, parseOracleText } from "../utils/manaSymbols.js";

function CardItem({ card, imageMode, decks: propDecks }) {
  const [imgError, setImgError] = useState(false);
  const [flipped, setFlipped] = useState(false);
  const [showDeckMenu, setShowDeckMenu] = useState(false);
  const [showArtPicker, setShowArtPicker] = useState(false);
  const [prints, setPrints] = useState([]);
  const [loadingPrints, setLoadingPrints] = useState(false);
  const [selectedArt, setSelectedArt] = useState(null);
  const [localDecks, setLocalDecks] = useState(null);
  const [loadingDecks, setLoadingDecks] = useState(false);
  const { language } = useLanguage();
  const menuRef = useRef(null);
  const { user } = useAuth();
  const { showToast } = useToast();

  const decks = localDecks ?? propDecks ?? [];

  const selectedCardFaces = selectedArt?.card_faces || card.card_faces || [];
  const doubleFacedLayouts = new Set(["transform", "modal_dfc", "double_faced_token", "reversible_card"]);
  const isDoubleFaced =
    selectedCardFaces.length >= 2 &&
    (doubleFacedLayouts.has(card.layout) ||
      selectedCardFaces[0]?.image_uris ||
      selectedCardFaces[1]?.image_uris);

  let frontImageUri = "";
  let backImageUri = "";

  if (isDoubleFaced) {
    frontImageUri = getImageUri(selectedCardFaces[0]?.image_uris, imageMode);
    backImageUri = getImageUri(selectedCardFaces[1]?.image_uris, imageMode);
  } else if (selectedArt) {
    frontImageUri = getImageUri(selectedArt.image_uris, imageMode);
  } else if (card.image_uris) {
    frontImageUri = getImageUri(card.image_uris, imageMode);
  } else if (card.card_faces && card.card_faces[0]?.image_uris) {
    frontImageUri = getImageUri(card.card_faces[0].image_uris, imageMode);
  }

  const isArtCrop = imageMode === "art_crop";

  const activeFace = isDoubleFaced ? selectedCardFaces[flipped ? 1 : 0] : null;
  const frontFace = selectedCardFaces?.[0];
  const getDisplayField = (field) => activeFace ? activeFace[field] : (card[field] ?? frontFace?.[field]);
  const displayName = activeFace?.name || card.name || frontFace?.name;
  const displayManaCost = getDisplayField("mana_cost");
  const displayTypeLine = getDisplayField("type_line");
  const displayOracleText = getDisplayField("oracle_text");
  const displayFlavorText = getDisplayField("flavor_text");
  const displayPower = getDisplayField("power");
  const displayToughness = getDisplayField("toughness");
  const displayLoyalty = getDisplayField("loyalty");
  const displaySetName = selectedArt?.setName || card.set_name;
  const displaySet = selectedArt?.set || card.set;
  const displayRarity = selectedArt?.rarity || card.rarity;
  const setIconClass = getSetIconClass({ set: displaySet, rarity: displayRarity });

  useEffect(() => {
    if (!showDeckMenu) return;
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setShowDeckMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showDeckMenu]);

  const handleFetchPrints = async () => {
    if (prints.length > 0) {
      setShowArtPicker(!showArtPicker);
      return;
    }
    if (!card.id) return;
    setLoadingPrints(true);
    setShowArtPicker(true);
    try {
      const res = await apiFetch(`/api/cards/${card.id}/prints`);
      if (!res.ok) return;
      const data = await res.json();
      const allPrints = (data.prints || [])
        .map((p) => ({
          id: p.id,
          normal: p.image_normal || getImageUri(p.card_faces?.[0]?.image_uris, "normal"),
          image_uris: {
            small: p.image_small,
            normal: p.image_normal,
            large: p.image_large,
            png: p.image_png,
            art_crop: p.image_art_crop,
            border_crop: p.image_border_crop,
          },
          card_faces: p.card_faces,
          setName: p.set_name,
          set: p.set_code,
          rarity: p.rarity,
          artist: p.artist,
        }))
        .filter((p) => p.normal);
      setPrints(allPrints);
    } catch {
      showToast("获取版本列表失败", "error");
    } finally {
      setLoadingPrints(false);
    }
  };

  const handleOpenDeckMenu = async () => {
    if (showDeckMenu) {
      setShowDeckMenu(false);
      return;
    }
    setLoadingDecks(true);
    setShowDeckMenu(true);
    try {
      const res = await apiFetch("/api/decks");
      if (res.ok) {
        setLocalDecks(await res.json());
      } else {
        setLocalDecks([]);
      }
    } catch {
      setLocalDecks([]);
    } finally {
      setLoadingDecks(false);
    }
  };

  const handleSelectArt = (print) => {
    setSelectedArt(print);
    setShowArtPicker(false);
    setImgError(false);
  };

  const handleResetArt = () => {
    setSelectedArt(null);
    setShowArtPicker(false);
    setImgError(false);
  };

  const getImageUrlForDeck = () => {
    if (selectedArt) return selectedArt.normal || getImageUri(selectedArt.card_faces?.[0]?.image_uris, "normal");
    if (card.image_uris?.normal) return card.image_uris.normal;
    if (card.card_faces?.[0]?.image_uris?.normal) return card.card_faces[0].image_uris.normal;
    return null;
  };

  const getDisplayUrlForDeck = () => {
    if (selectedArt) {
      return getImageUri(selectedArt.image_uris, "art_crop")
        || getImageUri(selectedArt.card_faces?.[0]?.image_uris, "art_crop");
    }
    return null;
  };

  const handleAddToDeck = async (deckId, deckName) => {
    setShowDeckMenu(false);
    try {
      const body = { card_id: card.id };
      if (selectedArt?.id) body.print_id = selectedArt.id;
      const imageUrl = getImageUrlForDeck();
      if (imageUrl) body.image_url = imageUrl;
      const displayUrl = getDisplayUrlForDeck();
      if (displayUrl) body.display_url = displayUrl;
      const res = await apiFetch(`/api/decks/${deckId}/cards`, {
        method: "POST",
        body,
      });
      if (res.ok) {
        showToast(`已将「${card.name}」加入「${deckName}」`);
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "添加失败", "error");
      }
    } catch {
      showToast("添加失败", "error");
    }
  };

  return (
    <div className={`card-item ${isArtCrop ? "art-crop" : ""}`}>
      <div className={`card-image-wrapper ${isDoubleFaced ? "flippable" : ""} ${isArtCrop ? "art-crop" : ""}`}>
        {isDoubleFaced ? (
          <div className={`card-flip-container ${flipped ? "flipped" : ""}`}>
            <div className="card-flip-front">
              {frontImageUri && !imgError ? (
                <img
                  src={frontImageUri}
                  alt={selectedCardFaces[0]?.name || card.name}
                  className="card-image"
                  loading="lazy"
                  onError={() => setImgError(true)}
                />
              ) : (
                <div className="card-image-placeholder">
                  <span>{selectedCardFaces[0]?.name || card.name}</span>
                </div>
              )}
            </div>
            <div className="card-flip-back">
              {backImageUri ? (
                <img
                  src={backImageUri}
                  alt={selectedCardFaces[1]?.name || card.name}
                  className="card-image"
                  loading="lazy"
                />
              ) : (
                <div className="card-image-placeholder">
                  <span>{selectedCardFaces[1]?.name || card.name}</span>
                </div>
              )}
            </div>
          </div>
        ) : frontImageUri && !imgError ? (
          <img
            src={frontImageUri}
            alt={card.name}
            className="card-image"
            loading="lazy"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="card-image-placeholder">
            <span>{card.name}</span>
          </div>
        )}
        {isDoubleFaced && (
          <button
            className="card-flip-btn"
            onClick={() => setFlipped(!flipped)}
            title="翻面"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M17 1l4 4-4 4" />
              <path d="M3 11V9a4 4 0 0 1 4-4h14" />
              <path d="M7 23l-4-4 4-4" />
              <path d="M21 13v2a4 4 0 0 1-4 4H3" />
            </svg>
          </button>
        )}
        {card.id && (
          <button
            className="card-art-btn"
            onClick={handleFetchPrints}
            title="切换卡图"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7" />
              <rect x="14" y="3" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" />
            </svg>
          </button>
        )}
        {user && (
          <button
            className="add-to-deck-btn"
            onClick={handleOpenDeckMenu}
            title="加入卡组"
          >
            +
          </button>
        )}
        {isArtCrop && displayFlavorText && (
          <div className="card-overlay">
            <p className="card-overlay-flavor">{displayFlavorText}</p>
          </div>
        )}
      </div>

      {showDeckMenu && user && (
        <div className="deck-dropdown-overlay" ref={menuRef}>
          <div className="deck-dropdown">
            {loadingDecks ? (
              <p className="deck-dropdown-empty">加载中...</p>
            ) : decks.length === 0 ? (
              <p className="deck-dropdown-empty">还没有卡组</p>
            ) : (
              decks.map((d) => {
                const legality = getCardLegality(card, d.format);
                const showLegality = d.format && d.format !== "undefined";
                return (
                  <button
                    key={d.id}
                    className="deck-dropdown-item"
                    onClick={() => handleAddToDeck(d.id, d.name)}
                    title={showLegality ? `${getFormatLabel(d.format, language)} · ${legalityLabel(legality, language)}` : getFormatLabel(d.format, language)}
                  >
                    <span className="deck-dropdown-name">{d.name}</span>
                    <span className="deck-dropdown-meta">
                      <span className={`format-badge format-${d.format || "undefined"}`}>
                        {getFormatLabel(d.format, language)}
                      </span>
                      {showLegality && (
                        <span className={`legality-chip legality-${legality}`}>
                          {legalityLabel(legality, language)}
                        </span>
                      )}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}

      {showArtPicker && createPortal(
        <>
          <div className="art-picker-backdrop" onClick={() => setShowArtPicker(false)} />
          <div className="art-picker">
            <div className="art-picker-header">
              <span>选择卡图版本 ({prints.length})</span>
              <div className="art-picker-header-actions">
                {selectedArt && (
                  <button className="art-picker-reset" onClick={handleResetArt}>恢复默认</button>
                )}
                <button className="art-picker-close" onClick={() => setShowArtPicker(false)}>&times;</button>
              </div>
            </div>
            {loadingPrints ? (
              <div className="art-picker-loading">加载中...</div>
            ) : (
              <div className="art-picker-grid">
                {prints.map((p) => (
                  <div
                    key={p.id}
                    className={`art-picker-item ${selectedArt?.id === p.id ? "selected" : ""}`}
                    onClick={() => handleSelectArt(p)}
                    title={`${p.setName} - ${p.artist}`}
                  >
                    <img src={p.normal} alt={p.setName} loading="lazy" />
                    <span className="art-picker-label">{p.setName}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>,
        document.body
      )}

      <div className="card-info">
        <h3 className="card-name">{displayName}</h3>
        <div className="card-meta">
          <div className="card-meta-left">
            {displayManaCost && (
              <span className="card-mana">
                {parseManaCost(displayManaCost).map((sym, idx) =>
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
          </div>
          <div className="card-meta-right">
            {displayRarity && <span className="card-rarity">{displayRarity}</span>}
            {setIconClass && (
              <span
                className="card-set-icon-wrap"
                title={`${displaySetName || displaySet}`}
              >
                <i className={setIconClass} aria-hidden="true" />
              </span>
            )}
          </div>
        </div>
        <p className="card-type">{displayTypeLine}</p>
        {displayOracleText && <p className="card-text">{parseOracleText(displayOracleText, React.createElement)}</p>}
        {isArtCrop && (displayPower || displayLoyalty || displaySetName) && (
          <div className="card-info-footer">
            <span className="card-info-pt">
              {displayPower && displayToughness && `${displayPower}/${displayToughness}`}
              {displayLoyalty && displayLoyalty}
            </span>
            {displaySetName && <span className="card-info-set">{displaySetName}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

export default CardItem;
