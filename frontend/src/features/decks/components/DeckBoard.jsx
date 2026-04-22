import { TYPE_MANA_CLASSES, getCardDisplayImage } from "../deckModel.js";

function DeckStackCard({
  item,
  selectedCard,
  cardIssuesById,
  quantityIncreaseGuards,
  isOwner,
  onDragStart,
  onDragEnd,
  onContextMenu,
  onTouchStart,
  onTouchMove,
  onTouchEnd,
  onMouseEnter,
  onMouseLeave,
  onSelect,
  onQuantityChange,
  t,
}) {
  const img = getCardDisplayImage(item);
  const isSelected = selectedCard?.card_id === item.card_id && selectedCard?.board === item.board;
  const cardIssues = cardIssuesById?.[item.card_id] || [];
  const increaseGuard = quantityIncreaseGuards?.[`${item.card_id}:${item.board}`];
  const increaseDisabled = increaseGuard?.canIncrease === false;

  return (
    <div
      className={`deck-stack-card ${isSelected ? "selected" : ""}`}
      draggable={isOwner}
      onDragStart={(e) => onDragStart(e, item)}
      onDragEnd={onDragEnd}
      onContextMenu={(e) => onContextMenu(e, item)}
      onTouchStart={(e) => onTouchStart(e, item)}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
      onMouseEnter={() => onMouseEnter(item)}
      onMouseLeave={onMouseLeave}
      onClick={() => onSelect(item)}
    >
      {img ? (
        <img src={img} alt={item.card.name} className="deck-stack-img" loading="lazy" />
      ) : (
        <div className="deck-stack-placeholder">{item.card.name}</div>
      )}
      <div className="deck-stack-overlay" />
      <div className="deck-stack-name">
        {cardIssues.length > 0 && <span className="deck-illegal-icon" title={cardIssues.join("\n")}>!</span>}
        {item.card.name}
      </div>
      {!isOwner ? (
        <div className="deck-stack-qty">{item.quantity > 1 && `x${item.quantity}`}</div>
      ) : (
        <div className="deck-stack-controls">
          <button onClick={(e) => { e.stopPropagation(); onQuantityChange(item.card_id, -1, item.board); }}>-</button>
          <span>{item.quantity}</span>
          <button
            disabled={increaseDisabled}
            title={increaseDisabled ? increaseGuard.reason : undefined}
            onClick={(e) => { e.stopPropagation(); onQuantityChange(item.card_id, 1, item.board); }}
          >
            +
          </button>
        </div>
      )}
    </div>
  );
}

function DeckTypeGroup({ group, cardProps, keyPrefix = "" }) {
  return (
    <div key={`${keyPrefix}${group.type}`} className="deck-type-group">
      <div className="deck-type-header">
        {TYPE_MANA_CLASSES[group.type] && (
          <span className="deck-type-icon">
            <i className={`ms ${TYPE_MANA_CLASSES[group.type]}`} aria-hidden="true" />
          </span>
        )}
        <span className="deck-type-label">{group.label}</span>
        <span className="deck-type-count">{group.count}</span>
      </div>
      <div className="deck-stack-grid">
        {group.items.map((item) => (
          <DeckStackCard key={`${keyPrefix}${item.card_id}`} item={item} {...cardProps} />
        ))}
      </div>
    </div>
  );
}

export default function DeckBoard({
  mainboardGroups,
  sideboardGroups,
  mainboardCount,
  sideboardCount,
  selectedCard,
  cardIssuesById,
  quantityIncreaseGuards,
  dragOverBoard,
  isOwner,
  language,
  handlers,
  t,
}) {
  const cardProps = {
    selectedCard,
    cardIssuesById,
    quantityIncreaseGuards,
    isOwner,
    t,
    onDragStart: handlers.onDragStart,
    onDragEnd: handlers.onDragEnd,
    onContextMenu: handlers.onContextMenu,
    onTouchStart: handlers.onTouchStart,
    onTouchMove: handlers.onTouchMove,
    onTouchEnd: handlers.onTouchEnd,
    onMouseEnter: handlers.onPreviewSelect,
    onMouseLeave: handlers.onPreviewCancel,
    onSelect: handlers.onSelectCard,
    onQuantityChange: handlers.onQuantityChange,
  };

  return (
    <div className="deck-mainboard-section">
      <div className="deck-board-header">{t("mainboard")} ({mainboardCount})</div>
      <div
        className={`deck-groups ${dragOverBoard === "mainboard" ? "drag-over" : ""}`}
        data-drop-hint={language === "zh" ? "将全部卡牌加入主卡组" : "Move all to Mainboard"}
        onDragOver={(e) => handlers.onDragOver(e, "mainboard")}
        onDragLeave={handlers.onDragLeave}
        onDrop={(e) => handlers.onDrop(e, "mainboard")}
      >
        {mainboardGroups.map((group) => (
          <DeckTypeGroup key={group.type} group={group} cardProps={cardProps} />
        ))}
      </div>

      <div className="deck-sideboard-section">
        <div className="deck-board-header">{t("sideboard")} ({sideboardCount})</div>
        {sideboardGroups.length > 0 ? (
          <div
            className={`deck-sideboard-groups ${dragOverBoard === "sideboard" ? "drag-over" : ""}`}
            data-drop-hint={language === "zh" ? "将全部卡牌加入备牌" : "Move all to Sideboard"}
            onDragOver={(e) => handlers.onDragOver(e, "sideboard")}
            onDragLeave={handlers.onDragLeave}
            onDrop={(e) => handlers.onDrop(e, "sideboard")}
          >
            {sideboardGroups.map((group) => (
              <DeckTypeGroup key={`side-${group.type}`} group={group} cardProps={cardProps} keyPrefix="side-" />
            ))}
          </div>
        ) : (
          <div
            className={`deck-sideboard-empty drag-drop-zone ${dragOverBoard === "sideboard" ? "drag-over" : ""}`}
            onDragOver={(e) => handlers.onDragOver(e, "sideboard")}
            onDragLeave={handlers.onDragLeave}
            onDrop={(e) => handlers.onDrop(e, "sideboard")}
          >
            <p>{language === "zh" ? "拖拽卡牌到这里添加到备牌" : "Drag cards here to add to sideboard"}</p>
          </div>
        )}
      </div>
    </div>
  );
}
