import { useState } from "react";

function getImageUri(imageUris, mode) {
  if (!imageUris) return "";
  return imageUris[mode] || imageUris.normal || imageUris.small || "";
}

function CardItem({ card, rank, imageMode }) {
  const [imgError, setImgError] = useState(false);
  const [flipped, setFlipped] = useState(false);

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

  if (isDoubleFaced) {
    frontImageUri = getImageUri(card.card_faces[0].image_uris, imageMode);
    backImageUri = getImageUri(card.card_faces[1].image_uris, imageMode);
  } else if (card.image_uris) {
    frontImageUri = getImageUri(card.image_uris, imageMode);
  } else if (card.card_faces && card.card_faces[0]?.image_uris) {
    frontImageUri = getImageUri(card.card_faces[0].image_uris, imageMode);
  }

  const isArtCrop = imageMode === "art_crop";

  const activeFace = isDoubleFaced && flipped ? card.card_faces[1] : null;
  const displayName = activeFace?.name || card.name;
  const displayManaCost = activeFace?.mana_cost || card.mana_cost;
  const displayTypeLine = activeFace?.type_line || card.type_line;
  const displayOracleText = activeFace?.oracle_text || card.oracle_text;
  const displayFlavorText = activeFace?.flavor_text || card.flavor_text;
  const displayPower = activeFace?.power || card.power;
  const displayToughness = activeFace?.toughness || card.toughness;
  const displayLoyalty = activeFace?.loyalty || card.loyalty;

  return (
    <div className="card-item">
      <div className="card-rank">#{rank}</div>
      <div className={`card-image-wrapper ${isDoubleFaced ? "flippable" : ""} ${isArtCrop ? "art-crop" : ""}`}>
        {isDoubleFaced ? (
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
      </div>
      <div className="card-info">
        <h3 className="card-name">{displayName}</h3>
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
          {displayPower && displayToughness && (
            <span className="card-pt">
              {displayPower}/{displayToughness}
            </span>
          )}
          {displayLoyalty && <span className="card-pt">{displayLoyalty}</span>}
          {card.set_name && <span className="card-set">{card.set_name}</span>}
        </div>
      </div>
    </div>
  );
}

export default CardItem;
