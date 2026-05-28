import { useRef } from "react";
import { createPortal } from "react-dom";
import React from "react";
import { getCardLegality, getFormatLabel, legalityLabel } from "../../../utils/formats.js";
import { parseManaCost, parseOracleText } from "../../../utils/manaSymbols.js";

export default function MobileDeckSheet({
  selectedCard,
  selectedPreview,
  deck,
  language,
  isOwner,
  previewFlipped,
  onFlip,
  onClose,
  onOpenArtPicker,
  t,
}) {
  const sheetRef = useRef(null);
  const dragStartY = useRef(0);
  const dragDelta = useRef(0);

  if (!selectedCard) return null;

  const handleTouchStart = (e) => {
    dragStartY.current = e.touches[0].clientY;
    dragDelta.current = 0;
    if (sheetRef.current) sheetRef.current.style.transition = "none";
  };

  const handleTouchMove = (e) => {
    const dy = e.touches[0].clientY - dragStartY.current;
    if (dy > 0 && sheetRef.current) {
      sheetRef.current.style.transform = `translateY(${dy}px)`;
      dragDelta.current = dy;
    }
  };

  const handleTouchEnd = () => {
    if (sheetRef.current) sheetRef.current.style.transition = "";
    if (dragDelta.current > 120) onClose();
    if (sheetRef.current) sheetRef.current.style.transform = "";
    dragDelta.current = 0;
  };

  return createPortal(
    <>
      <div className="mobile-sheet-backdrop" onClick={onClose} />
      <div className="mobile-sheet" ref={sheetRef}>
        <div
          className="mobile-sheet-header"
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
        >
          <div className="mobile-sheet-handle" />
          <button className="mobile-sheet-close" onClick={onClose} aria-label={t("close") || "Close"}>
            &times;
          </button>
        </div>
        <div className="mobile-sheet-body">
          <div className="mobile-sheet-image">
            {selectedPreview.isDoubleFaced ? (
              <div className={`card-flip-container ${previewFlipped ? "flipped" : ""}`}>
                <div className="card-flip-front">
                  {selectedPreview.front_image_url ? (
                    <img src={selectedPreview.front_image_url} alt={selectedPreview.front_name} />
                  ) : (
                    <div className="card-image-placeholder"><span>{selectedPreview.front_name}</span></div>
                  )}
                </div>
                <div className="card-flip-back">
                  {selectedPreview.back_image_url ? (
                    <img src={selectedPreview.back_image_url} alt={selectedPreview.back_name} />
                  ) : (
                    <div className="card-image-placeholder"><span>{selectedPreview.back_name}</span></div>
                  )}
                </div>
              </div>
            ) : (
              <img src={selectedPreview.image_url} alt={selectedPreview.name} />
            )}
            {selectedPreview.isDoubleFaced && (
              <button className="card-flip-btn" onClick={onFlip} title="翻面">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 1l4 4-4 4" />
                  <path d="M3 11V9a4 4 0 0 1 4-4h14" />
                  <path d="M7 23l-4-4 4-4" />
                  <path d="M21 13v2a4 4 0 0 1-4 4H3" />
                </svg>
              </button>
            )}
            {isOwner && selectedCard.card_id && (
              <button className="card-art-btn" onClick={onOpenArtPicker} title={t("changeArt")}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="7" height="7" />
                  <rect x="14" y="3" width="7" height="7" />
                  <rect x="3" y="14" width="7" height="7" />
                  <rect x="14" y="14" width="7" height="7" />
                </svg>
              </button>
            )}
          </div>
          <div className="mobile-sheet-info">
            <h3 className="deck-preview-name">
              <span>{selectedPreview.name}</span>
              {selectedPreview.secondary_name && <span className="card-name-secondary">{selectedPreview.secondary_name}</span>}
            </h3>
            {selectedPreview.mana_cost && (
              <span className="deck-preview-mana">
                {parseManaCost(selectedPreview.mana_cost).map((sym, idx) =>
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
            <p className="deck-preview-type">{selectedPreview.type_line}</p>
            {selectedPreview.oracle_text && (
              <p className="deck-preview-oracle">{parseOracleText(selectedPreview.oracle_text, React.createElement)}</p>
            )}
            {(selectedPreview.power || selectedPreview.toughness || selectedPreview.loyalty) && (
              <p className="deck-preview-pt">
                {selectedPreview.power && selectedPreview.toughness && `${selectedPreview.power}/${selectedPreview.toughness}`}
                {selectedPreview.loyalty && selectedPreview.loyalty}
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
        </div>
      </div>
    </>,
    document.body
  );
}
