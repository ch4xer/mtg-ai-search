import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { addDeckCard, fetchUserDecks } from "../api/decks.js";
import { fetchNormalizedCardPrints } from "../api/cards.js";
import { useAuth } from "../contexts/AuthContext.jsx";
import { getAccessToken } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { getFormatLabel, getCardLegality, legalityLabel } from "../utils/formats.js";
import { getCardImage, getCardPresentation } from "../utils/cardPresentation.js";
import { cacheImage, isImageCached } from "../utils/imageCache.js";
import { getSetIconClass } from "../utils/keyrune.js";
import { parseManaCost, parseOracleText } from "../utils/manaSymbols.js";
import KeywordAbilityTooltip from "./KeywordAbilityTooltip.jsx";
import CardActionMenu from "./CardActionMenu.jsx";

const ART_PICKER_SKELETON_COUNT = 18;

function CardItem({
  card,
  imageMode,
  decks: propDecks,
  abilityCatalog = {},
  tooltipActive = false,
  onTooltipActivate,
  onTooltipDeactivate,
  onFindSimilar,
}) {
  const [imgError, setImgError] = useState(false);
  const [flipped, setFlipped] = useState(false);
  const [showDeckMenu, setShowDeckMenu] = useState(false);
  const [showArtPicker, setShowArtPicker] = useState(false);
  const [prints, setPrints] = useState([]);
  const [loadingPrints, setLoadingPrints] = useState(false);
  const [selectedArt, setSelectedArt] = useState(null);
  const [localDecks, setLocalDecks] = useState(null);
  const [loadingDecks, setLoadingDecks] = useState(false);
  const [actionMenu, setActionMenu] = useState(null);
  const { language, t } = useLanguage();
  const navigate = useNavigate();
  const cardRef = useRef(null);
  const menuRef = useRef(null);
  const { user } = useAuth();
  const { showToast } = useToast();
  const canAddToDeck = Boolean(user || getAccessToken());

  const canUsePropDecks = Boolean(user && propDecks);
  const decks = localDecks ?? (canUsePropDecks ? propDecks : []);

  const isArtCrop = imageMode === "art_crop";
  const selectedCardFaces = selectedArt?.card_faces || card.card_faces || [];
  const presentation = getCardPresentation(card, {
    language,
    faceIndex: flipped ? 1 : 0,
    faces: selectedCardFaces,
    imageUris: selectedArt?.image_uris || card.image_uris,
    imageMode,
  });
  const {
    isDoubleFaced,
    name: displayName,
    secondaryName: displaySecondaryName,
    mana_cost: displayManaCost,
    type_line: displayTypeLine,
    oracle_text: displayOracleText,
    flavor_text: displayFlavorText,
    power: displayPower,
    toughness: displayToughness,
    loyalty: displayLoyalty,
    frontImageUrl: frontImageUri,
    backImageUrl: backImageUri,
  } = presentation;
  const displaySetName = selectedArt?.setName || presentation.set_name;
  const displaySet = selectedArt?.set || card.set;
  const displayRarity = selectedArt?.rarity || card.rarity;
  const setIconClass = getSetIconClass({ set: displaySet, rarity: displayRarity });
  const keywordExplanations = (card.keywords || [])
    .map((keyword) => abilityCatalog[keyword.trim().toLowerCase()])
    .filter(Boolean);

  useEffect(() => {
    setImgError(false);
  }, [frontImageUri, backImageUri]);

  // Preload art_crop image so drag ghost renders immediately on first drag
  const artCropPreloadUri = getCardImage(card, { mode: "art_crop" });
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
    if (!canAddToDeck) {
      navigate("/login");
      return;
    }
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
    if (selectedArt?.normal) return selectedArt.normal;
    return getCardImage(card, {
      mode: "normal",
      faces: selectedArt?.card_faces || card.card_faces,
      imageUris: selectedArt?.image_uris || card.image_uris,
    }) || null;
  };

  const getDisplayUrlForDeck = () => {
    if (!selectedArt) return null;
    return getCardImage(card, {
      mode: "art_crop",
      faces: selectedArt.card_faces,
      imageUris: selectedArt.image_uris,
    }) || null;
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

  const openActionMenu = (clientX, clientY) => {
    const menuWidth = 210;
    const menuHeight = 52;
    setActionMenu({
      left: Math.max(8, Math.min(clientX, window.innerWidth - menuWidth - 8)),
      top: Math.max(8, Math.min(clientY, window.innerHeight - menuHeight - 8)),
    });
    onTooltipDeactivate?.();
  };

  const handleContextMenu = (event) => {
    if (!onFindSimilar || !card.id) return;
    event.preventDefault();
    openActionMenu(event.clientX, event.clientY);
  };

  const handleMoreClick = (event) => {
    event.stopPropagation();
    const rect = event.currentTarget.getBoundingClientRect();
    openActionMenu(rect.right - 210, rect.bottom + 6);
  };

  return (
    <div
      ref={cardRef}
      className={`card-item ${isArtCrop ? "art-crop" : ""}`}
      draggable={!isArtCrop}
      onDragStart={!isArtCrop ? handleDragStart : undefined}
      onMouseEnter={onTooltipActivate}
      onMouseMove={onTooltipActivate}
      onMouseLeave={onTooltipDeactivate}
      onContextMenu={handleContextMenu}
    >
      {tooltipActive && keywordExplanations.length > 0 && (
        <KeywordAbilityTooltip
          anchorRef={cardRef}
          abilities={keywordExplanations}
          language={language}
        />
      )}
      {actionMenu && (
        <CardActionMenu
          card={card}
          position={actionMenu}
          onClose={() => setActionMenu(null)}
          onSearch={onFindSimilar}
        />
      )}
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
        <div className="card-side-actions">
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
          {card.id && (
            <button
              className="add-to-deck-btn"
              onClick={handleOpenDeckMenu}
              title="加入卡组"
            >
              +
            </button>
          )}
          {onFindSimilar && card.id && (
            <button
              type="button"
              className="card-more-btn"
              onClick={handleMoreClick}
              title={t("moreCardActions")}
              aria-label={t("moreCardActions")}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <circle cx="5" cy="12" r="1.7" />
                <circle cx="12" cy="12" r="1.7" />
                <circle cx="19" cy="12" r="1.7" />
              </svg>
            </button>
          )}
        </div>
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
