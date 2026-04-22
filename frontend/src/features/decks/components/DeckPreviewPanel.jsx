import DeckPreviewContent from "./DeckPreviewContent.jsx";

export default function DeckPreviewPanel({
  selectedCard,
  selectedPreview,
  deck,
  language,
  isOwner,
  previewFlipped,
  onFlip,
  onOpenArtPicker,
  onMouseEnter,
  onMouseLeave,
  t,
}) {
  return (
    <aside className="deck-preview-panel" onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave}>
      {selectedCard ? (
        <DeckPreviewContent
          preview={selectedPreview}
          selectedCard={selectedCard}
          deck={deck}
          language={language}
          isOwner={isOwner}
          flipped={previewFlipped}
          onFlip={onFlip}
          onChangeArt={onOpenArtPicker}
          changeArtLabel={t("changeArt")}
        />
      ) : (
        <div className="deck-preview-empty">
          <p>{t("clickCardDetails")}</p>
        </div>
      )}
    </aside>
  );
}
