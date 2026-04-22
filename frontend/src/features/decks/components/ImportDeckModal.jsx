export default function ImportDeckModal({
  importText,
  importing,
  language,
  onTextChange,
  onSubmit,
  onCancel,
  t,
}) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-content import-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{t("importDecklist")}</h3>
          <button className="modal-close" onClick={onCancel}>&times;</button>
        </div>
        <textarea
          className="import-textarea"
          value={importText}
          onChange={(e) => onTextChange(e.target.value)}
          placeholder={t("importPlaceholder")}
          autoFocus
          rows={12}
        />
        <div className="modal-actions">
          <button className="btn-secondary" onClick={onCancel}>{t("cancel")}</button>
          <button className="btn-accent" onClick={onSubmit} disabled={importing || !importText.trim()}>
            {importing ? `${language === "zh" ? "导入中..." : "Importing..."}` : `${language === "zh" ? "导入" : "Import"}`}
          </button>
        </div>
      </div>
    </div>
  );
}
