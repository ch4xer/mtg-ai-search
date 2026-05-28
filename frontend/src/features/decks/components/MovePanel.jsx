import { createPortal } from "react-dom";
import { getLocalizedCardName } from "../deckModel.js";

export default function MovePanel({ card, language, onMove, onClose }) {
  if (!card) return null;
  const displayName = getLocalizedCardName(card.card, language);

  const move = (fromBoard, toBoard, quantity) => {
    onMove(card.card_id, fromBoard, toBoard, quantity);
    onClose();
  };

  return createPortal(
    <>
      <div className="move-panel-backdrop" onClick={onClose} />
      <div className="move-panel">
        <div className="move-panel-header">
          <div className="move-panel-handle" />
          <button className="move-panel-close" onClick={onClose}>&times;</button>
        </div>
        <div className="move-panel-card-info">
          <span className="move-panel-card-name">{displayName}</span>
          <span className="move-panel-card-qty">{card.quantity}x</span>
        </div>
        <div className="move-panel-options">
          {card.board === "mainboard" ? (
            <>
              <button className="move-panel-option active" onClick={() => move("mainboard", "sideboard", "all")}>
                <span className="move-panel-option-icon">📦</span>
                <span className="move-panel-option-label">{language === "zh" ? "全部移动到备牌" : "Move all to Sideboard"}</span>
              </button>
              <button className="move-panel-option active" onClick={() => move("mainboard", "sideboard", 1)}>
                <span className="move-panel-option-icon">📤</span>
                <span className="move-panel-option-label">{language === "zh" ? "移动一张到备牌" : "Move 1 to Sideboard"}</span>
              </button>
            </>
          ) : (
            <>
              <button className="move-panel-option active" onClick={() => move("sideboard", "mainboard", "all")}>
                <span className="move-panel-option-icon">📚</span>
                <span className="move-panel-option-label">{language === "zh" ? "全部移动到主卡组" : "Move all to Mainboard"}</span>
              </button>
              <button className="move-panel-option active" onClick={() => move("sideboard", "mainboard", 1)}>
                <span className="move-panel-option-icon">📤</span>
                <span className="move-panel-option-label">{language === "zh" ? "移动一张到主卡组" : "Move 1 to Mainboard"}</span>
              </button>
            </>
          )}
        </div>
        <button className="move-panel-cancel" onClick={onClose}>
          {language === "zh" ? "取消" : "Cancel"}
        </button>
      </div>
    </>,
    document.body
  );
}
