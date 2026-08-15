import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { addDeckCard, fetchUserDecks } from "../api/decks.js";
import { fetchNormalizedCardPrints } from "../api/cards.js";
import { useAuth } from "../contexts/AuthContext.jsx";
import { getAccessToken } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { getFormatLabel, getCardLegality, legalityLabel } from "../utils/formats.js";
import { getImageUri } from "../utils/cardImage.js";
import { cacheImage, isImageCached } from "../utils/imageCache.js";
import { getSetIconClass } from "../utils/keyrune.js";
import { parseManaCost, parseOracleText } from "../utils/manaSymbols.js";

const DOUBLE_FACED_LAYOUTS = new Set(["transform", "modal_dfc", "double_faced_token", "reversible_card"]);
const ART_PICKER_SKELETON_COUNT = 18;

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
  const canAddToDeck = Boolean(user || getAccessToken());

  const canUsePropDecks = Boolean(user && propDecks);
  const decks = localDecks ?? (canUsePropDecks ? propDecks : []);

  const isArtCrop = imageMode === "art_crop";
  const zhCard = language === "zh" ? card.zh : null;
  const zhFaces = zhCard?.card_faces || [];
  const selectedCardFaces = selectedArt?.card_faces || card.card_faces || [];
  const isDoubleFaced =
    selectedCardFaces.length >= 2 &&
    DOUBLE_FACED_LAYOUTS.has(card.layout);

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

  const activeFaceIndex = isDoubleFaced ? (flipped ? 1 : 0) : 0;
  const activeFace = isDoubleFaced ? selectedCardFaces[activeFaceIndex] : null;
  const activeZhFace = zhFaces[activeFaceIndex] || null;
  const frontFace = selectedCardFaces?.[0];
  const getEnglishField = (field) => activeFace ? activeFace[field] : (card[field] ?? frontFace?.[field]);
  const getTranslatedField = (field) => activeZhFace?.[field] || (!isDoubleFaced ? zhCard?.[field] : null);
  const getDisplayField = (field) => getTranslatedField(field) || getEnglishField(field);
  const englishName = activeFace?.name || card.name || frontFace?.name;
  const translatedName = activeZhFace?.name || (!isDoubleFaced ? zhCard?.name : null);
  const displayName = translatedName || englishName;
  const displaySecondaryName = translatedName && englishName && translatedName !== englishName ? englishName : "";
  const displayManaCost = getDisplayField("mana_cost");
  const displayTypeLine = getDisplayField("type_line");
  const displayOracleText = getDisplayField("oracle_text");
  const displayFlavorText = getDisplayField("flavor_text");
  const displayPower = getDisplayField("power");
  const displayToughness = getDisplayField("toughness");
  const displayLoyalty = getDisplayField("loyalty");
  const displaySetName = selectedArt?.setName || activeZhFace?.set_name || zhCard?.set_name || card.set_name;
  const displaySet = selectedArt?.set || card.set;
  const displayRarity = selectedArt?.rarity || card.rarity;
  const setIconClass = getSetIconClass({ set: displaySet, rarity: displayRarity });

  useEffect(() => {
    setImgError(false);
  }, [frontImageUri, backImageUri]);

  // Preload art_crop image so drag ghost renders immediately on first drag
  const artCropPreloadUri = card.image_uris
    ? getImageUri(card.image_uris, "art_crop")
    : card.card_faces?.[0]?.image_uris
      ? getImageUri(card.card_faces[0].image_uris, "art_crop")
      : "";
  useEffect(() => {
    if (!artCropPreloadUri) return;
    const img = new Image();
    img.src = artCropPreloadUri;
  }, [artCropPreloadUri]);

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
      setPrints(await fetchNormalizedCardPrints(card.id));
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
    setShowDeckMenu(true);
    setLoadingDecks(true);
    try {
      setLocalDecks(await fetchUserDecks());
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
      const printId = selectedArt?.id || card.print_id;
      if (printId) {
        body.print_id = printId;
      }
      if (selectedArt?.id) {
        const imageUrl = getImageUrlForDeck();
        if (imageUrl) body.image_url = imageUrl;
        const displayUrl = getDisplayUrlForDeck();
        if (displayUrl) body.display_url = displayUrl;
      }
      const res = await addDeckCard(deckId, body);
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

  const handleDragStart = (e) => {
    if (isArtCrop && e.target.closest("button")) {
      e.preventDefault();
      return;
    }

    e.dataTransfer.setData(
      "application/json",
      JSON.stringify({
        card_id: card.id,
        name: card.name,
        image_uri: artCropPreloadUri,
      })
    );
    e.dataTransfer.effectAllowed = "copy";

    // art_crop is preloaded in useEffect – already cached by now
    const ghostImgSrc = artCropPreloadUri;

    const ghost = document.createElement("div");
    ghost.style.cssText =
      "position:fixed;top:-9999px;left:-9999px;width:240px;height:58px;" +
      "border-radius:8px;overflow:hidden;isolation:isolate;" +
      "box-shadow:0 2px 12px rgba(0,0,0,0.4);";
    ghost.innerHTML =
      `<img src="${ghostImgSrc}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;" />` +
      `<div style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,0.75) 0%,rgba(0,0,0,0.46) 55%,rgba(0,0,0,0.2) 100%);"></div>` +
      `<span style="position:absolute;left:0.65rem;right:0.65rem;top:50%;transform:translateY(-50%);color:#fff;font-family:'Crimson Text',Georgia,serif;font-size:0.88rem;font-weight:700;line-height:1.2;text-shadow:0 2px 8px rgba(0,0,0,0.9);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${card.name}</span>`;
    document.body.appendChild(ghost);
    e.dataTransfer.setDragImage(ghost, 120, 29);
    requestAnimationFrame(() => document.body.removeChild(ghost));
  };

  return (
    <div
      className={`card-item ${isArtCrop ? "art-crop" : ""}`}
      draggable={!isArtCrop}
      onDragStart={!isArtCrop ? handleDragStart : undefined}
    >
      <div
        className={`card-image-wrapper ${isDoubleFaced ? "flippable" : ""} ${isArtCrop ? "art-crop" : ""}`}
        draggable={isArtCrop}
        onDragStart={isArtCrop ? handleDragStart : undefined}
      >
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
        {canAddToDeck && (
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

      {showDeckMenu && canAddToDeck && (
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
            {loadingPrints && prints.length === 0 ? (
              <div className="art-picker-grid" aria-busy="true">
                {Array.from({ length: ART_PICKER_SKELETON_COUNT }, (_, index) => (
                  <div key={index} className="art-picker-item art-picker-skeleton" />
                ))}
              </div>
            ) : (
              <div className="art-picker-grid">
                {prints.map((p) => {
                  const pickerImage = p.thumbnail || p.normal;
                  return (
                    <div
                      key={p.id}
                      className={`art-picker-item ${selectedArt?.id === p.id ? "selected" : ""}`}
                      onClick={() => handleSelectArt(p)}
                      title={`${p.label} - ${p.artist}`}
                    >
                      <img
                        src={pickerImage}
                        alt={p.label}
                        loading={isImageCached(pickerImage) ? "eager" : "lazy"}
                        onLoad={() => cacheImage(pickerImage)}
                      />
                      <span className="art-picker-label">{p.label}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>,
        document.body
      )}

      <div className="card-info">
        <h3 className="card-name">
          <span>{displayName}</span>
          {displaySecondaryName && <span className="card-name-secondary">{displaySecondaryName}</span>}
        </h3>
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
