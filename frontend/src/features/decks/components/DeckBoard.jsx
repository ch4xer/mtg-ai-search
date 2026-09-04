import { useState } from "react";
import {
  TYPE_MANA_CLASSES,
  getDeckCardImage,
} from "../deckModel.js";
import { getLocalizedCardName } from "../../../utils/cardPresentation.js";

const DECK_VIEW_STORAGE_KEY = "mtg-deck-board-view";
const MAX_PILE_COLUMNS = 6;

function DeckStackCard({
  item,
  selectedCard,
  cardIssuesById,
  isOwner,
  onDragStart,
  onDragEnd,
  onContextMenu,
  onTouchStart,
  onTouchMove,
  onTouchEnd,
  onMouseEnter,
  onMouseMove,
  onMouseLeave,
  onSelect,
  onQuantityChange,
  language,
  t,
}) {
  const img = getDeckCardImage(item);
  const displayName = getLocalizedCardName(item.card, language);
  const isSelected = selectedCard?.card_id === item.card_id && selectedCard?.board === item.board;
  const cardIssues = cardIssuesById?.[item.card_id] || [];

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
      onMouseMove={() => onMouseMove(item)}
      onMouseLeave={onMouseLeave}
      onClick={() => onSelect(item)}
    >
      {img ? (
        <img src={img} alt={displayName} className="deck-stack-img" loading="lazy" />
      ) : (
        <div className="deck-stack-placeholder">{displayName}</div>
      )}
      <div className="deck-stack-overlay" />
      <div className="deck-stack-name">
        {cardIssues.length > 0 && <span className="deck-illegal-icon" title={cardIssues.join("\n")}>!</span>}
        {displayName}
      </div>
      {!isOwner ? (
        <div className="deck-stack-qty">{item.quantity > 1 && `x${item.quantity}`}</div>
      ) : (
        <div className="deck-stack-controls">
          <button onClick={(e) => { e.stopPropagation(); onQuantityChange(item.card_id, -1, item.board); }}>-</button>
          <span>{item.quantity}</span>
          <button onClick={(e) => { e.stopPropagation(); onQuantityChange(item.card_id, 1, item.board); }}>
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

function DeckPileCard({ item, pileIndex, cardProps }) {
  const {
    selectedCard,
    cardIssuesById,
    isOwner,
    language,
    onDragStart,
    onDragEnd,
    onContextMenu,
    onTouchStart,
    onTouchMove,
    onTouchEnd,
    onMouseEnter,
    onMouseMove,
    onMouseLeave,
    onSelect,
    onQuantityChange,
  } = cardProps;
  const image = getDeckCardImage(item);
  const displayName = getLocalizedCardName(item.card, language);
  const isSelected = selectedCard?.card_id === item.card_id && selectedCard?.board === item.board;
  const cardIssues = cardIssuesById?.[item.card_id] || [];

  const selectFromKeyboard = (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    onSelect(item);
  };

  return (
    <div
      className={`deck-pile-card ${isSelected ? "selected" : ""}`}
      style={{ "--pile-index": pileIndex + 1 }}
      draggable={isOwner}
      role="button"
      tabIndex={0}
      aria-label={`${displayName}${item.quantity > 1 ? ` ×${item.quantity}` : ""}`}
      onDragStart={(event) => onDragStart(event, item)}
      onDragEnd={onDragEnd}
      onContextMenu={(event) => onContextMenu(event, item)}
      onTouchStart={(event) => onTouchStart(event, item)}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
      onMouseEnter={() => onMouseEnter(item)}
      onMouseMove={() => onMouseMove(item)}
      onMouseLeave={onMouseLeave}
      onClick={() => onSelect(item)}
      onKeyDown={selectFromKeyboard}
    >
      {image ? (
        <img src={image} alt={displayName} className="deck-pile-img" loading="lazy" />
      ) : (
        <div className="deck-pile-placeholder">{displayName}</div>
      )}

      <div className="deck-pile-badges">
        {cardIssues.length > 0 && (
          <span className="deck-illegal-icon" title={cardIssues.join("\n")}>!</span>
        )}
        {item.quantity > 1 && <span className="deck-pile-qty">×{item.quantity}</span>}
      </div>

      {isOwner && (
        <div className="deck-pile-controls">
          <button
            type="button"
            aria-label={`Remove one ${displayName}`}
            onClick={(event) => {
              event.stopPropagation();
              onQuantityChange(item.card_id, -1, item.board);
            }}
          >
            −
          </button>
          <span>{item.quantity}</span>
          <button
            type="button"
            aria-label={`Add one ${displayName}`}
            onClick={(event) => {
              event.stopPropagation();
              onQuantityChange(item.card_id, 1, item.board);
            }}
          >
            +
          </button>
        </div>
      )}
    </div>
  );
}

function splitIntoPiles(items) {
  const pileCount = Math.min(MAX_PILE_COLUMNS, Math.max(1, items.length));
  const piles = Array.from({ length: pileCount }, () => []);
  items.forEach((item, index) => {
    piles[index % pileCount].push(item);
  });
  return piles.filter((pile) => pile.length > 0);
}

function DeckPileTypeGroup({ group, cardProps, keyPrefix = "" }) {
  const piles = splitIntoPiles(group.items);

  return (
    <div className="deck-pile-type-group">
      <div className="deck-type-header">
        {TYPE_MANA_CLASSES[group.type] && (
          <span className="deck-type-icon">
            <i className={`ms ${TYPE_MANA_CLASSES[group.type]}`} aria-hidden="true" />
          </span>
        )}
        <span className="deck-type-label">{group.label}</span>
        <span className="deck-type-count">({group.count})</span>
      </div>
      <div className="deck-pile-columns">
        {piles.map((pile, columnIndex) => (
          <div key={`${keyPrefix}${group.type}-pile-${columnIndex}`} className="deck-pile-column">
            {pile.map((item, pileIndex) => (
              <DeckPileCard
                key={`${keyPrefix}${item.card_id}`}
                item={item}
                pileIndex={pileIndex}
                cardProps={cardProps}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function DeckViewToggle({ viewMode, onChange, t }) {
  return (
    <div className="deck-view-toggle" role="group" aria-label={t("deckViewMode")}>
      <button
        type="button"
        className={viewMode === "compact" ? "active" : ""}
        aria-pressed={viewMode === "compact"}
        title={t("compactDeckView")}
        onClick={() => onChange("compact")}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <line x1="5" y1="6" x2="19" y2="6" />
          <line x1="5" y1="12" x2="19" y2="12" />
          <line x1="5" y1="18" x2="19" y2="18" />
        </svg>
        <span>{t("compactDeckView")}</span>
      </button>
      <button
        type="button"
        className={viewMode === "pile" ? "active" : ""}
        aria-pressed={viewMode === "pile"}
        title={t("pileDeckView")}
        onClick={() => onChange("pile")}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
          <rect x="6" y="3" width="12" height="16" rx="1.5" />
          <path d="M4 7v13a1 1 0 0 0 1 1h11" />
        </svg>
        <span>{t("pileDeckView")}</span>
      </button>
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
  dragOverBoard,
  isOwner,
  language,
  handlers,
  t,
}) {
  const [viewMode, setViewMode] = useState(() => (
    localStorage.getItem(DECK_VIEW_STORAGE_KEY) === "compact" ? "compact" : "pile"
  ));

  const changeViewMode = (nextMode) => {
    setViewMode(nextMode);
    localStorage.setItem(DECK_VIEW_STORAGE_KEY, nextMode);
  };

  const pileColumnCount = Math.max(
    1,
    ...mainboardGroups.map((group) => splitIntoPiles(group.items).length),
    ...sideboardGroups.map((group) => splitIntoPiles(group.items).length)
  );

  const cardProps = {
    selectedCard,
    cardIssuesById,
    isOwner,
    language,
    t,
    onDragStart: handlers.onDragStart,
    onDragEnd: handlers.onDragEnd,
    onContextMenu: handlers.onContextMenu,
    onTouchStart: handlers.onTouchStart,
    onTouchMove: handlers.onTouchMove,
    onTouchEnd: handlers.onTouchEnd,
    onMouseEnter: handlers.onPreviewSelect,
    onMouseMove: handlers.onPreviewPointerMove,
    onMouseLeave: handlers.onPreviewCancel,
    onSelect: handlers.onSelectCard,
    onQuantityChange: handlers.onQuantityChange,
  };

  return (
    <div
      className={`deck-mainboard-section deck-view-${viewMode}`}
      style={{ "--deck-pile-column-count": pileColumnCount }}
    >
      <div className="deck-board-heading-row">
        <div className="deck-board-header">{t("mainboard")} ({mainboardCount})</div>
        <DeckViewToggle viewMode={viewMode} onChange={changeViewMode} t={t} />
      </div>
      <div
        className={`${viewMode === "pile" ? "deck-pile-groups" : "deck-groups"} ${dragOverBoard === "mainboard" ? "drag-over" : ""}`}
        data-drop-hint={language === "zh" ? "将全部卡牌加入主卡组" : "Move all to Mainboard"}
        onDragOver={(e) => handlers.onDragOver(e, "mainboard")}
        onDragLeave={handlers.onDragLeave}
        onDrop={(e) => handlers.onDrop(e, "mainboard")}
      >
        {mainboardGroups.map((group) => viewMode === "pile" ? (
          <DeckPileTypeGroup key={group.type} group={group} cardProps={cardProps} />
        ) : (
          <DeckTypeGroup key={group.type} group={group} cardProps={cardProps} />
        ))}
      </div>

      <div className="deck-sideboard-section">
        <div className="deck-board-header">{t("sideboard")} ({sideboardCount})</div>
        {sideboardGroups.length > 0 ? (
          <div
            className={`${viewMode === "pile" ? "deck-pile-groups deck-sideboard-pile-groups" : "deck-sideboard-groups"} ${dragOverBoard === "sideboard" ? "drag-over" : ""}`}
            data-drop-hint={language === "zh" ? "将全部卡牌加入备牌" : "Move all to Sideboard"}
            onDragOver={(e) => handlers.onDragOver(e, "sideboard")}
            onDragLeave={handlers.onDragLeave}
            onDrop={(e) => handlers.onDrop(e, "sideboard")}
          >
            {sideboardGroups.map((group) => viewMode === "pile" ? (
              <DeckPileTypeGroup key={`side-${group.type}`} group={group} cardProps={cardProps} keyPrefix="side-" />
            ) : (
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
