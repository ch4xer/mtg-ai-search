import { useState, useRef, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext.jsx";
import { apiFetch } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";

function getImageUri(imageUris, mode) {
  if (!imageUris) return "";
  return imageUris[mode] || imageUris.normal || imageUris.small || "";
}

function CardItem({ card, imageMode, decks }) {
  const [imgError, setImgError] = useState(false);
  const [flipped, setFlipped] = useState(false);
  const [showDeckMenu, setShowDeckMenu] = useState(false);
  const [showArtPicker, setShowArtPicker] = useState(false);
  const [prints, setPrints] = useState([]);
  const [loadingPrints, setLoadingPrints] = useState(false);
  const [selectedArt, setSelectedArt] = useState(null); // { png, imageUri, setName }
  const menuRef = useRef(null);
  const artRef = useRef(null);
  const { user } = useAuth();
  const { showToast } = useToast();

  const colorMap = {
    W: "mana-white",
    U: "mana-blue",
    B: "mana-black",
    R: "mana-red",
    G: "mana-green",
  };

  const colors = Array.isArray(card.colors) ? card.colors : [];

  const isDoubleFaced =
    card.card_faces &&
    card.card_faces.length === 2 &&
    card.card_faces[0]?.image_uris &&
    card.card_faces[1]?.image_uris;

  let frontImageUri = "";
  let backImageUri = "";

  if (selectedArt) {
    frontImageUri = selectedArt.imageUri;
  } else if (isDoubleFaced) {
    frontImageUri = getImageUri(card.card_faces[0].image_uris, imageMode);
    backImageUri = getImageUri(card.card_faces[1].image_uris, imageMode);
  } else if (card.image_uris) {
    frontImageUri = getImageUri(card.image_uris, imageMode);
  } else if (card.card_faces && card.card_faces[0]?.image_uris) {
    frontImageUri = getImageUri(card.card_faces[0].image_uris, imageMode);
  }

  const isArtCrop = imageMode === "art_crop";

  const activeFace = isDoubleFaced && flipped && !selectedArt ? card.card_faces[1] : null;
  const frontFace = card.card_faces?.[0];
  const displayName = activeFace?.name || card.name || frontFace?.name;
  const displayManaCost = activeFace?.mana_cost || card.mana_cost || frontFace?.mana_cost;
  const displayTypeLine = activeFace?.type_line || card.type_line || frontFace?.type_line;
  const displayOracleText = activeFace?.oracle_text || card.oracle_text || frontFace?.oracle_text;
  const displayFlavorText = activeFace?.flavor_text || card.flavor_text || frontFace?.flavor_text;
  const displayPower = activeFace?.power || card.power || frontFace?.power;
  const displayToughness = activeFace?.toughness || card.toughness || frontFace?.toughness;
  const displayLoyalty = activeFace?.loyalty || card.loyalty || frontFace?.loyalty;

  // Close deck menu on outside click
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

  // Close art picker on outside click
  useEffect(() => {
    if (!showArtPicker) return;
    const handleClick = (e) => {
      if (artRef.current && !artRef.current.contains(e.target)) {
        setShowArtPicker(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showArtPicker]);

  const handleFetchPrints = async () => {
    if (prints.length > 0) {
      setShowArtPicker(!showArtPicker);
      return;
    }
    setLoadingPrints(true);
    setShowArtPicker(true);
    try {
      const searchUri = card.prints_search_uri;
      if (!searchUri) return;
      const res = await fetch(searchUri);
      if (!res.ok) return;
      const data = await res.json();
      const allPrints = (data.data || [])
        .filter((p) => p.image_uris?.png)
        .map((p) => ({
          id: p.id,
          png: p.image_uris.png,
          imageUri: getImageUri(p.image_uris, imageMode),
          setName: p.set_name,
          artist: p.artist,
        }));
      setPrints(allPrints);
    } catch {
      showToast("获取版本列表失败", "error");
    } finally {
      setLoadingPrints(false);
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

  // Get the PNG URL to store in deck (for export)
  const getPngUrlForDeck = () => {
    if (selectedArt) return selectedArt.png;
    if (card.image_uris?.png) return card.image_uris.png;
    if (card.card_faces?.[0]?.image_uris?.png) return card.card_faces[0].image_uris.png;
    return null;
  };

  const handleAddToDeck = async (deckId, deckName) => {
    setShowDeckMenu(false);
    try {
      const body = { card_id: card.id };
      const pngUrl = getPngUrlForDeck();
      if (pngUrl) body.image_url = pngUrl;
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
    <div className="card-item">
      <div className={`card-image-wrapper ${isDoubleFaced && !selectedArt ? "flippable" : ""} ${isArtCrop ? "art-crop" : ""}`}>
        {isDoubleFaced && !selectedArt ? (
          <div className={`card-flip-container ${flipped ? "flipped" : ""}`}>
            <div className="card-flip-front">
              {frontImageUri && !imgError ? (
                <img
                  src={frontImageUri}
                  alt={card.card_faces[0].name}
                  className="card-image"
                  loading="lazy"
                  onError={() => setImgError(true)}
                />
              ) : (
                <div className="card-image-placeholder">
                  <span>{card.card_faces[0].name}</span>
                </div>
              )}
            </div>
            <div className="card-flip-back">
              {backImageUri ? (
                <img
                  src={backImageUri}
                  alt={card.card_faces[1].name}
                  className="card-image"
                  loading="lazy"
                />
              ) : (
                <div className="card-image-placeholder">
                  <span>{card.card_faces[1].name}</span>
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
        {isDoubleFaced && !selectedArt && (
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
        {card.prints_search_uri && (
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
      </div>

      {/* Art picker panel */}
      {showArtPicker && (
        <div className="art-picker" ref={artRef}>
          <div className="art-picker-header">
            <span>选择卡图版本 ({prints.length})</span>
            {selectedArt && (
              <button className="art-picker-reset" onClick={handleResetArt}>恢复默认</button>
            )}
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
                  <img src={p.imageUri} alt={p.setName} loading="lazy" />
                  <span className="art-picker-label">{p.setName}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="card-info">
        <h3 className="card-name">
          {displayName}
          {selectedArt && <span className="card-alt-set"> ({selectedArt.setName})</span>}
        </h3>
        <div className="card-meta">
          {displayManaCost && <span className="card-mana">{displayManaCost}</span>}
          {colors.length > 0 && (
            <span className="card-colors">
              {colors.map((c) => (
                <span key={c} className={`mana-dot ${colorMap[c] || ""}`} title={c} />
              ))}
            </span>
          )}
          {card.rarity && <span className="card-rarity">{card.rarity}</span>}
        </div>
        <p className="card-type">{displayTypeLine}</p>
        {displayOracleText && <p className="card-text">{displayOracleText}</p>}
        {card.keywords && card.keywords.length > 0 && (
          <p className="card-keywords">{card.keywords.join(", ")}</p>
        )}
        {displayFlavorText && <p className="card-flavor">{displayFlavorText}</p>}
        <div className="card-footer">
          <div className="card-footer-left">
            {displayPower && displayToughness && (
              <span className="card-pt">
                {displayPower}/{displayToughness}
              </span>
            )}
            {displayLoyalty && <span className="card-pt">{displayLoyalty}</span>}
          </div>
          <div className="card-footer-right">
            {card.set_name && <span className="card-set">{card.set_name}</span>}
            {user && decks && (
              <div className="add-to-deck-wrapper" ref={menuRef}>
                <button
                  className="add-to-deck-btn"
                  onClick={() => setShowDeckMenu(!showDeckMenu)}
                  title="加入卡组"
                >
                  +
                </button>
                {showDeckMenu && (
                  <div className="deck-dropdown">
                    {decks.length === 0 ? (
                      <p className="deck-dropdown-empty">还没有卡组</p>
                    ) : (
                      decks.map((d) => (
                        <button
                          key={d.id}
                          className="deck-dropdown-item"
                          onClick={() => handleAddToDeck(d.id, d.name)}
                        >
                          {d.name}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default CardItem;
