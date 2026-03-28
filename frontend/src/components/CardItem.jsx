import { useState } from "react";

function CardItem({ card, rank }) {
  const [imgError, setImgError] = useState(false);

  const colorMap = {
    W: "mana-white",
    U: "mana-blue",
    B: "mana-black",
    R: "mana-red",
    G: "mana-green",
  };

  // Scryfall returns colors as an array
  const colors = Array.isArray(card.colors) ? card.colors : [];

  // Get image URI — handle both normal cards and multi-face cards
  let imageUri = "";
  if (card.image_uris) {
    imageUri = card.image_uris.normal || card.image_uris.small || "";
  } else if (card.card_faces && card.card_faces[0]?.image_uris) {
    imageUri = card.card_faces[0].image_uris.normal || card.card_faces[0].image_uris.small || "";
  }

  return (
    <div className="card-item">
      <div className="card-rank">#{rank}</div>
      <div className="card-image-wrapper">
        {imageUri && !imgError ? (
          <img
            src={imageUri}
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
      </div>
      <div className="card-info">
        <h3 className="card-name">{card.name}</h3>
        <div className="card-meta">
          {card.mana_cost && <span className="card-mana">{card.mana_cost}</span>}
          {colors.length > 0 && (
            <span className="card-colors">
              {colors.map((c) => (
                <span key={c} className={`mana-dot ${colorMap[c] || ""}`} title={c} />
              ))}
            </span>
          )}
          {card.rarity && <span className="card-rarity">{card.rarity}</span>}
        </div>
        <p className="card-type">{card.type_line}</p>
        {card.oracle_text && <p className="card-text">{card.oracle_text}</p>}
        {card.keywords && card.keywords.length > 0 && (
          <p className="card-keywords">{card.keywords.join(", ")}</p>
        )}
        {card.flavor_text && <p className="card-flavor">{card.flavor_text}</p>}
        <div className="card-footer">
          {card.power && card.toughness && (
            <span className="card-pt">
              {card.power}/{card.toughness}
            </span>
          )}
          {card.loyalty && <span className="card-pt">{card.loyalty}</span>}
          {card.set_name && <span className="card-set">{card.set_name}</span>}
        </div>
      </div>
    </div>
  );
}

export default CardItem;
