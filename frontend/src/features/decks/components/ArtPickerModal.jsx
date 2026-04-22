import { createPortal } from "react-dom";
import { getImageUri } from "../../../utils/cardImage.js";

export default function ArtPickerModal({
  selectedCard,
  artPrints,
  loadingPrints,
  language,
  onClose,
  onResetArt,
  onSelectArt,
  t,
}) {
  if (!selectedCard) return null;

  const currentImageUrl = selectedCard.image_url
    || getImageUri(selectedCard.card.image_uris, "normal")
    || getImageUri(selectedCard.card.card_faces?.[0]?.image_uris, "normal");

  return createPortal(
    <>
      <div className="art-picker-backdrop" onClick={onClose} />
      <div className="art-picker">
        <div className="art-picker-header">
          <span>{t("selectArtVersion")} ({artPrints.length})</span>
          <div className="art-picker-header-actions">
            {selectedCard?.image_url && (
              <button className="art-picker-reset" onClick={onResetArt}>{t("resetDefaultArt")}</button>
            )}
            <button className="art-picker-close" onClick={onClose}>&times;</button>
          </div>
        </div>
        {loadingPrints ? (
          <div className="art-picker-loading">{t("loadingVersions")}</div>
        ) : (
          <div className="art-picker-grid">
            {artPrints.map((print) => {
              const isSelected = currentImageUrl === print.normal;
              return (
                <div
                  key={print.id}
                  className={`art-picker-item ${isSelected ? "selected" : ""}`}
                  onClick={() => onSelectArt(print)}
                  title={`${print.label} - ${print.artist}`}
                >
                  <img src={print.normal} alt={print.label} loading="lazy" />
                  <span className="art-picker-label">{print.label}</span>
                  {isSelected && (
                    <span className="art-picker-current-badge">
                      {language === "zh" ? "当前" : "Current"}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>,
    document.body
  );
}
