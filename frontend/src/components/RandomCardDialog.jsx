import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { getCardPresentation } from "../utils/cardPresentation.js";
import { parseManaCost, parseOracleText } from "../utils/manaSymbols.js";

function RandomCardDialog({ card, loading, error, onAgain, onClose }) {
  const { language, t } = useLanguage();
  const [faceIndex, setFaceIndex] = useState(0);
  const dialogRef = useRef(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    setFaceIndex(0);
  }, [card?.id]);

  useEffect(() => {
    const previousFocus = document.activeElement;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onCloseRef.current();
      if (event.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll("button:not(:disabled)");
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    document.body.classList.add("modal-open");
    requestAnimationFrame(() => dialogRef.current?.querySelector("button")?.focus());
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.classList.remove("modal-open");
      previousFocus?.focus?.();
    };
  }, []);

  const faces = card?.card_faces || [];
  const presentation = getCardPresentation(card, {
    language,
    faceIndex,
    imageMode: "border_crop",
  });
  const {
    isDoubleFaced,
    name: displayName,
    secondaryName: englishName,
    imageUrl: imageUri,
  } = presentation;
  const field = (name) => presentation[name] || "";
  const actions = (
    <footer className="random-card-actions">
      <button type="button" className="btn-secondary" onClick={onClose}>{t("closeRandomCard")}</button>
      <button type="button" className="btn-accent" onClick={() => onAgain(card?.id || null)} disabled={loading}>
        {loading ? t("drawingRandomCard") : t("drawAgain")}
      </button>
    </footer>
  );

  return createPortal(
    <div className="random-card-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section
        ref={dialogRef}
        className="random-card-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={t("randomCard")}
      >
        <button type="button" className="random-card-close" onClick={onClose} aria-label={t("closeRandomCard")}>
          &times;
        </button>

        {loading && !card && (
          <div className="random-card-loading" aria-busy="true">
            <div className="random-card-image-skeleton" />
            <div className="random-card-copy-skeleton"><span /><span /><span /><span /></div>
          </div>
        )}

        {error && !card && (
          <div className="random-card-error" role="alert">
            <p>{error}</p>
            <button type="button" className="btn-accent" onClick={() => onAgain(null)}>{t("retry")}</button>
          </div>
        )}

        {card && (
          <div className={`random-card-content ${loading ? "is-refreshing" : ""}`}>
            <div className="random-card-visual">
              {imageUri ? <img src={imageUri} alt={displayName} /> : <div className="random-card-no-image">{displayName}</div>}
              {isDoubleFaced && (
                <button type="button" className="random-card-flip" onClick={() => setFaceIndex((value) => (value + 1) % faces.length)}>
                  {t("flipCard")}
                </button>
              )}
            </div>
            <div className="random-card-details">
              <div className="random-card-title-row">
                <div>
                  <h3>{displayName}</h3>
                  {englishName && <p>{englishName}</p>}
                </div>
                {field("mana_cost") && (
                  <span className="card-mana">
                    {parseManaCost(field("mana_cost")).map((symbol, index) => (
                      symbol.half
                        ? <span key={index} className="ms-half"><i className={`ms ${symbol.classes}`} aria-hidden="true" /></span>
                        : <i key={index} className={`ms ${symbol.classes}`} aria-hidden="true" />
                    ))}
                  </span>
                )}
              </div>
              <p className="random-card-type">{field("type_line")}</p>
              {field("oracle_text") && <div className="random-card-rules">{parseOracleText(field("oracle_text"), React.createElement)}</div>}
              {(field("power") || field("loyalty")) && (
                <p className="random-card-stats">
                  {field("power") && field("toughness") ? `${field("power")}/${field("toughness")}` : field("loyalty")}
                </p>
              )}
              <dl className="random-card-meta">
                {field("set_name") && <><dt>{t("set")}</dt><dd>{field("set_name")}</dd></>}
                {card.artist && <><dt>{t("artist")}</dt><dd>{card.artist}</dd></>}
              </dl>
              {error && <p className="random-card-inline-error" role="alert">{error}</p>}
              {actions}
            </div>
          </div>
        )}

        {!card && actions}
      </section>
    </div>,
    document.body,
  );
}

export default RandomCardDialog;
