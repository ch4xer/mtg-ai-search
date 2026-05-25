import { createPortal } from "react-dom";
import { getExactImageUri } from "../../../utils/cardImage.js";
import { cacheImage, isImageCached } from "../../../utils/imageCache.js";

const ART_PICKER_SKELETON_COUNT = 18;

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

  const currentImageUrl = getExactImageUri(selectedCard.card.image_uris, "png")
    || getExactImageUri(selectedCard.card.card_faces?.[0]?.image_uris, "png")
    || selectedCard.image_url;

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
        {loadingPrints && artPrints.length === 0 ? (
          <div className="art-picker-grid" aria-busy="true">
            {Array.from({ length: ART_PICKER_SKELETON_COUNT }, (_, index) => (
              <div key={index} className="art-picker-item art-picker-skeleton" />
            ))}
          </div>
        ) : (
          <div className="art-picker-grid">
            {artPrints.map((print) => {
              const printImageUrl = getExactImageUri(print.image_uris, "png")
                || getExactImageUri(print.card_faces?.[0]?.image_uris, "png");
              const isSelected = currentImageUrl === printImageUrl;
              const pickerImage = print.thumbnail || print.normal;
              return (
                <div
                  key={print.id}
                  className={`art-picker-item ${isSelected ? "selected" : ""}`}
                  onClick={() => onSelectArt(print)}
                  title={`${print.label} - ${print.artist}`}
                >
                  <img
                    src={pickerImage}
                    alt={print.label}
                    loading={isImageCached(pickerImage) ? "eager" : "lazy"}
                    onLoad={() => cacheImage(pickerImage)}
                  />
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
