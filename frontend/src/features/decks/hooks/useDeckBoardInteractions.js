import { useEffect, useRef, useState } from "react";
import { addDeckCard, removeDeckCard } from "../../../api/decks.js";
import { getQuantityIncreaseGuards } from "../deckModel.js";

export function useDeckBoardInteractions({
  id,
  cards,
  setCards,
  selectedCard,
  setSelectedCard,
  deckFormat,
  language,
  isOwner,
  showToast,
  t,
}) {
  const [dragOverBoard, setDragOverBoard] = useState(null);
  const [touchDragCard, setTouchDragCard] = useState(null);
  const [showMovePanel, setShowMovePanel] = useState(false);
  const [contextMenu, setContextMenu] = useState(null);
  const draggedCardRef = useRef(null);
  const longPressTimerRef = useRef(null);

  const handleRemoveCard = async (cardId, board) => {
    const res = await removeDeckCard(id, cardId, board);
    if (res.ok) {
      setCards((prev) => prev.filter((card) => !(card.card_id === cardId && card.board === board)));
      if (selectedCard?.card_id === cardId && selectedCard?.board === board) {
        setSelectedCard(null);
      }
      showToast(t("cardRemoved"));
    }
  };

  const handleQuantityChange = async (cardId, delta, board = "mainboard") => {
    const card = cards.find((item) => item.card_id === cardId && item.board === board);
    if (!card) return;
    const newQty = card.quantity + delta;
    if (newQty <= 0) {
      await handleRemoveCard(cardId, board);
      return;
    }
    if (delta > 0) {
      const guard = getQuantityIncreaseGuards(cards, deckFormat, language)[`${cardId}:${board}`];
      if (guard?.canIncrease === false) {
        showToast(guard.reason, "error");
        return;
      }
    }

    const res = await addDeckCard(id, { card_id: cardId, quantity: delta, board });
    if (res.ok) {
      setCards((prev) =>
        prev.map((item) =>
          item.card_id === cardId && item.board === board ? { ...item, quantity: newQty } : item
        )
      );
      if (selectedCard?.card_id === cardId && selectedCard?.board === board) {
        setSelectedCard((prev) => ({ ...prev, quantity: newQty }));
      }
    }
  };

  const handleMoveCard = async (cardId, fromBoard, toBoard, quantity = "all") => {
    const card = cards.find((item) => item.card_id === cardId && item.board === fromBoard);
    if (!card || fromBoard === toBoard) return;

    const moveCount = quantity === "all" ? card.quantity : 1;
    const targetCard = cards.find((item) => item.card_id === cardId && item.board === toBoard);

    if (quantity === "all") {
      const removeRes = await removeDeckCard(id, cardId, fromBoard);
      if (!removeRes.ok) {
        showToast(language === "zh" ? "移动失败" : "Failed to move card", "error");
        return;
      }
    } else {
      const newSourceQty = card.quantity - moveCount;
      if (newSourceQty <= 0) {
        const removeRes = await removeDeckCard(id, cardId, fromBoard);
        if (!removeRes.ok) {
          showToast(language === "zh" ? "移动失败" : "Failed to move card", "error");
          return;
        }
      } else {
        const updateRes = await addDeckCard(id, { card_id: cardId, quantity: -moveCount, board: fromBoard });
        if (!updateRes.ok) {
          showToast(language === "zh" ? "移动失败" : "Failed to move card", "error");
          return;
        }
      }
    }

    const addRes = await addDeckCard(id, { card_id: cardId, quantity: moveCount, board: toBoard });
    if (!addRes.ok) {
      showToast(language === "zh" ? "移动失败" : "Failed to move card", "error");
      await addDeckCard(id, { card_id: cardId, quantity: moveCount, board: fromBoard });
      return;
    }

    setCards((prev) => {
      let next = prev;
      if (quantity === "all" || card.quantity - moveCount <= 0) {
        next = next.filter((item) => !(item.card_id === cardId && item.board === fromBoard));
      } else {
        next = next.map((item) =>
          item.card_id === cardId && item.board === fromBoard
            ? { ...item, quantity: item.quantity - moveCount }
            : item
        );
      }

      if (targetCard) {
        next = next.map((item) =>
          item.card_id === cardId && item.board === toBoard
            ? { ...item, quantity: item.quantity + moveCount }
            : item
        );
      } else {
        next = [...next, { ...card, board: toBoard, quantity: moveCount }];
      }

      return next;
    });

    if (selectedCard?.card_id === cardId && selectedCard?.board === fromBoard) {
      if (quantity === "all" || card.quantity - moveCount <= 0) {
        setSelectedCard(null);
      } else {
        setSelectedCard((prev) => ({ ...prev, quantity: prev.quantity - moveCount }));
      }
    }

    const actionText = quantity === "all"
      ? (language === "zh" ? "已全部移动到" : "Moved all to")
      : (language === "zh" ? "已移动1张到" : "Moved 1 to");
    const boardText = toBoard === "sideboard"
      ? (language === "zh" ? "备牌" : "sideboard")
      : (language === "zh" ? "主卡组" : "mainboard");
    showToast(`${actionText}${boardText}`);
  };

  const handleDragStart = (event, item) => {
    if (!isOwner) {
      event.preventDefault();
      return;
    }
    draggedCardRef.current = item;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", JSON.stringify({ cardId: item.card_id, board: item.board }));
    setTimeout(() => {
      event.target.classList.add("dragging");
    }, 0);
  };

  const handleDragEnd = (event) => {
    event.target.classList.remove("dragging");
    draggedCardRef.current = null;
    setDragOverBoard(null);
  };

  const handleDragOver = (event, board) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDragOverBoard(board);
  };

  const handleDragLeave = (event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) {
      setDragOverBoard(null);
    }
  };

  const handleDrop = (event, toBoard) => {
    event.preventDefault();
    setDragOverBoard(null);
    try {
      const data = JSON.parse(event.dataTransfer.getData("text/plain"));
      handleMoveCard(data.cardId, data.board, toBoard, "all");
    } catch {
      // Ignore malformed drag payloads.
    }
  };

  const handleTouchStart = (event, item) => {
    if (!isOwner) return;
    longPressTimerRef.current = setTimeout(() => {
      setTouchDragCard(item);
      setShowMovePanel(true);
      if (navigator.vibrate) navigator.vibrate(50);
      event.preventDefault();
    }, 400);
  };

  const handleTouchMove = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  };

  const handleTouchEnd = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  };

  const handleMovePanelClose = () => {
    setShowMovePanel(false);
    setTouchDragCard(null);
  };

  const handleContextMenu = (event, item) => {
    if (!isOwner) return;
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({ x: event.clientX, y: event.clientY, item });
  };

  const handleContextMenuClose = () => setContextMenu(null);

  const handleContextMenuMoveOne = (toBoard) => {
    if (contextMenu?.item) {
      handleMoveCard(contextMenu.item.card_id, contextMenu.item.board, toBoard, 1);
    }
    handleContextMenuClose();
  };

  useEffect(() => {
    const handleClickOutside = () => setContextMenu(null);
    if (contextMenu) {
      document.addEventListener("click", handleClickOutside);
      return () => document.removeEventListener("click", handleClickOutside);
    }
  }, [contextMenu]);

  return {
    dragOverBoard,
    touchDragCard,
    showMovePanel,
    contextMenu,
    handleQuantityChange,
    handleRemoveCard,
    handleMoveCard,
    handleDragStart,
    handleDragEnd,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
    handleMovePanelClose,
    handleContextMenu,
    handleContextMenuMoveOne,
  };
}
