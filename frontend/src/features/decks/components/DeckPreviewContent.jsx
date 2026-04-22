import React from "react";
import { getCardLegality, getFormatLabel, legalityLabel } from "../../../utils/formats.js";
import { parseManaCost, parseOracleText } from "../../../utils/manaSymbols.js";

function FlipButton({ onClick }) {
  return (
    <button className="card-flip-btn" onClick={onClick} title="翻面">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17 1l4 4-4 4" />
        <path d="M3 11V9a4 4 0 0 1 4-4h14" />
        <path d="M7 23l-4-4 4-4" />
        <path d="M21 13v2a4 4 0 0 1-4 4H3" />
      </svg>
    </button>
  );
}

function ArtButton({ onClick, title }) {
  return (
    <button className="card-art-btn" onClick={onClick} title={title}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
      </svg>
    </button>
  );
}

function PreviewImage({ preview, flipped, onFlip, canChangeArt, onChangeArt, changeArtLabel }) {
  return (
    <div className="deck-preview-image" style={{ position: "relative" }}>
      {preview.isDoubleFaced ? (
        <div className={`card-flip-container ${flipped ? "flipped" : ""}`}>
          <div className="card-flip-front">
            {preview.front_image_url ? (
              <img src={preview.front_image_url} alt={preview.front_name} />
            ) : (
              <div className="card-image-placeholder"><span>{preview.front_name}</span></div>
            )}
          </div>
          <div className="card-flip-back">
            {preview.back_image_url ? (
              <img src={preview.back_image_url} alt={preview.back_name} />
            ) : (
              <div className="card-image-placeholder"><span>{preview.back_name}</span></div>
            )}
          </div>
        </div>
      ) : (
        <img src={preview.image_url} alt={preview.name} />
      )}
      {preview.isDoubleFaced && <FlipButton onClick={onFlip} />}
      {canChangeArt && <ArtButton onClick={onChangeArt} title={changeArtLabel} />}
    </div>
  );
}

function ManaCost({ manaCost }) {
  if (!manaCost) return null;
  return (
    <span className="deck-preview-mana">
      {parseManaCost(manaCost).map((sym, idx) =>
        sym.half ? (
          <span key={idx} className="ms-half">
            <i className={`ms ${sym.classes}`} aria-hidden="true" />
          </span>
        ) : (
          <i key={idx} className={`ms ${sym.classes}`} aria-hidden="true" />
        )
      )}
    </span>
  );
}

function PreviewInfo({ preview, selectedCard, deck, language }) {
  return (
    <div className="deck-preview-info">
      <h3 className="deck-preview-name">{preview.name}</h3>
      <ManaCost manaCost={preview.mana_cost} />
      <p className="deck-preview-type">{preview.type_line}</p>
      {preview.oracle_text && (
        <p className="deck-preview-oracle">{parseOracleText(preview.oracle_text, React.createElement)}</p>
      )}
      {(preview.power || preview.toughness || preview.loyalty) && (
        <p className="deck-preview-pt">
          {preview.power && preview.toughness && `${preview.power}/${preview.toughness}`}
          {preview.loyalty && preview.loyalty}
        </p>
      )}
      {deck.format && deck.format !== "undefined" && (() => {
        const legality = getCardLegality(selectedCard.card, deck.format);
        return (
          <span className={`legality-chip legality-${legality}`}>
            {getFormatLabel(deck.format, language)}: {legalityLabel(legality, language)}
          </span>
        );
      })()}
    </div>
  );
}

export default function DeckPreviewContent({
  preview,
  selectedCard,
  deck,
  language,
  isOwner,
  flipped,
  onFlip,
  onChangeArt,
  changeArtLabel,
}) {
  if (!preview || !selectedCard) return null;

  return (
    <>
      <PreviewImage
        preview={preview}
        flipped={flipped}
        onFlip={onFlip}
        canChangeArt={isOwner && selectedCard.card_id}
        onChangeArt={onChangeArt}
        changeArtLabel={changeArtLabel}
      />
      <PreviewInfo preview={preview} selectedCard={selectedCard} deck={deck} language={language} />
    </>
  );
}
