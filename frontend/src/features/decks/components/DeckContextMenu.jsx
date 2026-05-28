import { createPortal } from "react-dom";

export default function DeckContextMenu({ contextMenu, language, onMoveOne, onSetCover }) {
  if (!contextMenu) return null;

  return createPortal(
    <div
      className="context-menu"
      style={{ left: contextMenu.x, top: contextMenu.y }}
      onClick={(e) => e.stopPropagation()}
    >
      {contextMenu.item.board === "mainboard" ? (
        <div className="context-menu-item" onClick={() => onMoveOne("sideboard")}>
          {language === "zh" ? "发送一张到备牌" : "Send 1 to Sideboard"}
        </div>
      ) : (
        <div className="context-menu-item" onClick={() => onMoveOne("mainboard")}>
          {language === "zh" ? "发送一张到主卡组" : "Send 1 to Mainboard"}
        </div>
      )}
      <div className="context-menu-item" onClick={onSetCover}>
        {language === "zh" ? "设为卡组封面" : "Set as Deck Cover"}
      </div>
    </div>,
    document.body
  );
}
