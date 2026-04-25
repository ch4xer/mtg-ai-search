import { FORMATS, getFormatLabel } from "../../../utils/formats.js";

export default function DeckDetailHeader({
  deck,
  cards,
  isOwner,
  editing,
  editName,
  language,
  copyDecklistButtonRef,
  exportBusy,
  exportButtonLabel,
  exportButtonStyle,
  showExportMenu,
  setEditing,
  setEditName,
  setShowExportMenu,
  navigate,
  t,
  onRename,
  onFormatChange,
  onShare,
  onShowImport,
  onExportText,
  onExportPdf,
  onExportImages,
  onDelete,
}) {
  return (
    <div className="deck-detail-header">
      {!isOwner ? (
        <button className="btn-secondary btn-back" onClick={() => navigate("/")}>
          <svg className="btn-back-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          <span className="btn-back-text">&larr; {t("backToHome")}</span>
        </button>
      ) : (
        <button className="btn-secondary btn-back" onClick={() => navigate("/decks")}>
          <svg className="btn-back-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          <span className="btn-back-text">&larr; {t("backToDecks")}</span>
        </button>
      )}

      <div className="deck-detail-title">
        {isOwner && editing ? (
          <form onSubmit={(event) => { event.preventDefault(); onRename(); }} className="deck-rename-form">
            <input
              value={editName}
              onChange={(event) => setEditName(event.target.value)}
              autoFocus
              onBlur={onRename}
            />
          </form>
        ) : (
          <h2
            onClick={isOwner ? () => setEditing(true) : undefined}
            title={isOwner ? t("clickToRename") : undefined}
            style={isOwner ? undefined : { cursor: "default" }}
          >
            {deck.name}
          </h2>
        )}

        {!isOwner ? (
          <span className="deck-format-badge">{getFormatLabel(deck.format || "undefined", language)}</span>
        ) : (
          <select
            className={`deck-format-select format-${deck.format || "undefined"}`}
            value={deck.format || "undefined"}
            onChange={onFormatChange}
            title={t("switchFormat")}
          >
            {FORMATS.map((format) => (
              <option key={format.key} value={format.key}>
                {language === "zh" ? format.labelZh : format.labelEn}
              </option>
            ))}
          </select>
        )}
      </div>

      <div className="deck-detail-actions">
        {isOwner && (
          <button className="btn-secondary" onClick={onShare} title={t("share")}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="18" cy="5" r="3" />
              <circle cx="6" cy="12" r="3" />
              <circle cx="18" cy="19" r="3" />
              <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
              <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
            </svg>
            <span className="btn-label">{t("share")}</span>
          </button>
        )}

        {isOwner && (
          <button className="btn-secondary" onClick={onShowImport} title={t("importDecklist")}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="12" y1="18" x2="12" y2="12" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
            <span className="btn-label">{t("importDecklist")}</span>
          </button>
        )}

        <button
          ref={copyDecklistButtonRef}
          className="btn-secondary"
          onClick={onExportText}
          disabled={cards.length === 0}
          title={t("copyDecklist")}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
          </svg>
          <span className="btn-label">{t("copyDecklist")}</span>
        </button>

        <div className="export-dropdown">
          <button
            className={`btn-accent export-trigger${exportBusy ? " export-trigger-busy" : ""}`}
            onClick={() => setShowExportMenu(!showExportMenu)}
            disabled={exportBusy || cards.length === 0}
            title={exportButtonLabel}
            style={exportButtonStyle}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            <span className="btn-label">{exportButtonLabel}</span>
            {!exportBusy && (
              <svg className="export-trigger-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: "4px" }}>
                <polyline points="6 9 12 15 18 9" />
              </svg>
            )}
          </button>
          {showExportMenu && (
            <div className="export-dropdown-menu">
              <button onClick={onExportPdf}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="2" y="3" width="20" height="18" rx="2" ry="2" />
                  <line x1="2" y1="7" x2="22" y2="7" />
                  <line x1="2" y1="17" x2="22" y2="17" />
                </svg>
                {t("exportPdf")}
              </button>
              <button onClick={onExportImages}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                  <circle cx="8.5" cy="8.5" r="1.5" />
                  <polyline points="21 15 16 10 5 21" />
                </svg>
                {t("exportImages")}
              </button>
            </div>
          )}
        </div>

        {isOwner && (
          <button className="btn-danger" onClick={onDelete} title={t("deleteDeck")}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              <line x1="10" y1="11" x2="10" y2="17" />
              <line x1="14" y1="11" x2="14" y2="17" />
            </svg>
            <span className="btn-label">{t("deleteDeck")}</span>
          </button>
        )}
      </div>
    </div>
  );
}
