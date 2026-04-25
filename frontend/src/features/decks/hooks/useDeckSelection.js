import { useEffect, useMemo, useRef, useState } from "react";
import { fetchCardPrints, normalizePrints } from "../../../api/cards.js";
import { patchDeckCard } from "../../../api/decks.js";
import { getImageUri } from "../../../utils/cardImage.js";
import { DOUBLE_FACED_LAYOUTS, getPreviewData } from "../deckModel.js";

export function useDeckSelection({ id, cards, setCards, showToast, t }) {
  const [selectedCard, setSelectedCard] = useState(null);
  const [previewFlipped, setPreviewFlipped] = useState(false);
  const [showMobileSheet, setShowMobileSheet] = useState(false);
  const [showArtPicker, setShowArtPicker] = useState(false);
  const [artPrints, setArtPrints] = useState([]);
  const [loadingPrints, setLoadingPrints] = useState(false);
  const hoverTimerRef = useRef(null);
  const previewLockedRef = useRef(false);

  const cancelPendingSelect = () => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  };

  const schedulePreviewSelect = (item) => {
    if (previewLockedRef.current) return;
    cancelPendingSelect();
    hoverTimerRef.current = setTimeout(() => setSelectedCard(item), 200);
  };

  useEffect(() => cancelPendingSelect, []);

  useEffect(() => {
    if (cards.length > 0 && !selectedCard) {
      setSelectedCard(cards[0]);
    }
  }, [cards, selectedCard]);

  const handleOpenArtPicker = async () => {
    if (!selectedCard) return;
    if (artPrints.length > 0) {
      setShowArtPicker((prev) => !prev);
      return;
    }
    setLoadingPrints(true);
    setShowArtPicker(true);
    try {
      const res = await fetchCardPrints(selectedCard.card_id);
      if (!res.ok) return;
      const data = await res.json();
      setArtPrints(normalizePrints(data));
    } catch {
      showToast(t("fetchVersionsFailed"), "error");
    } finally {
      setLoadingPrints(false);
    }
  };

  const handleSelectArt = async (print) => {
    if (!selectedCard) return;
    const displayUrl = getImageUri(print.image_uris, "art_crop")
      || getImageUri(print.card_faces?.[0]?.image_uris, "art_crop");
    const imageUrl = print.normal || getImageUri(print.card_faces?.[0]?.image_uris, "normal");
    try {
      const res = await patchDeckCard(id, selectedCard.card_id, {
        print_id: print.id,
        image_url: imageUrl,
        display_url: displayUrl,
        board: selectedCard.board,
      });
      if (res.ok) {
        setCards((prev) =>
          prev.map((card) =>
            card.card_id === selectedCard.card_id && card.board === selectedCard.board
              ? {
                  ...card,
                  print_id: print.id,
                  image_url: imageUrl,
                  display_url: displayUrl,
                  card: {
                    ...card.card,
                    rarity: print.rarity || card.card.rarity,
                    card_faces: print.card_faces || card.card.card_faces,
                  },
                }
              : card
          )
        );
        setSelectedCard((prev) => ({
          ...prev,
          print_id: print.id,
          image_url: imageUrl,
          display_url: displayUrl,
          card: {
            ...prev.card,
            rarity: print.rarity || prev.card.rarity,
            card_faces: print.card_faces || prev.card.card_faces,
          },
        }));
        showToast(t("artChanged"));
      } else {
        showToast(t("artChangeFailed"), "error");
      }
    } catch {
      showToast(t("artChangeFailed"), "error");
    }
    setShowArtPicker(false);
  };

  const handleResetArt = async () => {
    if (!selectedCard) return;
    try {
      const res = await patchDeckCard(id, selectedCard.card_id, {
        print_id: null,
        image_url: null,
        display_url: null,
        board: selectedCard.board,
      });
      if (res.ok) {
        setCards((prev) =>
          prev.map((card) =>
            card.card_id === selectedCard.card_id && card.board === selectedCard.board
              ? { ...card, print_id: null, image_url: null, display_url: null }
              : card
          )
        );
        setSelectedCard((prev) => ({ ...prev, print_id: null, image_url: null, display_url: null }));
        showToast(t("artResetSuccess"));
      }
    } catch {
      showToast(t("artChangeFailed"), "error");
    }
    setShowArtPicker(false);
  };

  useEffect(() => {
    setShowArtPicker(false);
    setArtPrints([]);
    setPreviewFlipped(false);
  }, [selectedCard?.card_id, selectedCard?.board, selectedCard?.print_id]);

  useEffect(() => {
    if (!selectedCard?.card_id) return;
    if (selectedCard.card.card_faces?.length >= 2) return;
    if (!DOUBLE_FACED_LAYOUTS.has(selectedCard.card.layout)) return;

    let cancelled = false;
    const hydrateFaces = async () => {
      try {
        const res = await fetchCardPrints(selectedCard.card_id);
        if (!res.ok) return;
        const data = await res.json();
        const prints = data.prints || [];
        const selectedPrint = prints.find((print) => print.id === selectedCard.print_id && print.card_faces?.length >= 2);
        const fallbackPrint = prints.find((print) => print.card_faces?.length >= 2);
        const faces = (selectedPrint || fallbackPrint)?.card_faces;
        if (cancelled || !faces?.length) return;

        setCards((prev) =>
          prev.map((card) =>
            card.card_id === selectedCard.card_id && card.board === selectedCard.board
              ? { ...card, card: { ...card.card, card_faces: faces } }
              : card
          )
        );
        setSelectedCard((prev) =>
          prev && prev.card_id === selectedCard.card_id && prev.board === selectedCard.board
            ? { ...prev, card: { ...prev.card, card_faces: faces } }
            : prev
        );
      } catch {
        // Keep the preview on the existing card data.
      }
    };

    hydrateFaces();
    return () => {
      cancelled = true;
    };
  }, [selectedCard?.card_id, selectedCard?.board, selectedCard?.print_id, selectedCard?.card?.card_faces, selectedCard?.card?.layout]);

  const selectedPreview = useMemo(
    () => getPreviewData(selectedCard, previewFlipped),
    [selectedCard, previewFlipped]
  );

  return {
    selectedCard,
    setSelectedCard,
    selectedPreview,
    previewFlipped,
    setPreviewFlipped,
    showMobileSheet,
    setShowMobileSheet,
    showArtPicker,
    setShowArtPicker,
    artPrints,
    loadingPrints,
    handleOpenArtPicker,
    handleSelectArt,
    handleResetArt,
    previewLockedRef,
    cancelPendingSelect,
    schedulePreviewSelect,
  };
}
