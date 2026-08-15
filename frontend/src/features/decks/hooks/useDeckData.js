import { useEffect, useMemo, useState } from "react";
import {
  analyzeDeck,
  deleteDeck,
  fetchSharedDeckCardsData,
  fetchSharedDeckData,
  updateDeck,
} from "../../../api/decks.js";
import {
  buildDeckAnalysis,
  splitDeckBoards,
  validateDeck,
} from "../deckModel.js";
import { getFormatLabel } from "../../../utils/formats.js";

export function useDeckData({ id, navigate, showToast, t, language }) {
  const [deck, setDeck] = useState(null);
  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [analyzing, setAnalyzing] = useState(false);

  const fetchDeck = async () => {
    try {
      const [deckData, deckCards] = await Promise.all([
        fetchSharedDeckData(id),
        fetchSharedDeckCardsData(id, { force: true }),
      ]);
      setDeck(deckData);
      setEditName(deckData.name);
      setCards(deckCards);
    } catch (error) {
      if (error.status === 404) {
        showToast(t("deckNotFound"), "error");
        navigate("/");
        return;
      }
      showToast(t("loadFailed"), "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeck();
  }, [id]);

  const { mainCards, sideCards, mainboardGroups, sideboardGroups } = useMemo(
    () => splitDeckBoards(cards, language),
    [cards, language]
  );

  const groupedCards = mainboardGroups;
  const deckAnalysis = useMemo(() => buildDeckAnalysis(mainCards, language), [mainCards, language]);
  const deckValidation = useMemo(() => validateDeck(cards, deck?.format, language), [cards, deck?.format, language]);
  const mainboardCount = useMemo(
    () => mainCards.reduce((sum, card) => sum + card.quantity, 0),
    [mainCards]
  );
  const sideboardCount = useMemo(
    () => sideCards.reduce((sum, card) => sum + card.quantity, 0),
    [sideCards]
  );

  const handleRename = async () => {
    if (!deck) return;
    if (!editName.trim() || editName.trim() === deck.name) {
      setEditing(false);
      return;
    }
    const res = await updateDeck(id, { name: editName.trim() });
    if (res.ok) {
      const updated = await res.json();
      setDeck((prev) => ({ ...prev, name: updated.name }));
      showToast(t("deckRenamed"));
    }
    setEditing(false);
  };

  const handleFormatChange = async (event) => {
    if (!deck) return;
    const newFormat = event.target.value;
    if (newFormat === deck.format) return;
    const res = await updateDeck(id, { name: deck.name, format: newFormat });
    if (res.ok) {
      const updated = await res.json();
      setDeck((prev) => ({ ...prev, format: updated.format }));
      showToast(
        language === "zh"
          ? `赛制已切换为「${getFormatLabel(updated.format, language)}」`
          : `Format changed to "${getFormatLabel(updated.format, language)}"`
      );
    }
  };

  const handleDelete = async () => {
    const confirmed = window.confirm(
      language === "zh" ? "确定要删除这个卡组吗？" : "Are you sure you want to delete this deck?"
    );
    if (!confirmed) return;
    const res = await deleteDeck(id);
    if (res.ok) {
      showToast(t("deckDeleted"));
      navigate("/decks");
    }
  };

  const handleAnalyze = async () => {
    if (analyzing) return;
    if (!cards.length) {
      showToast(t("analysisEmptyDeck"), "error");
      return;
    }
    setAnalyzing(true);
    try {
      const res = await analyzeDeck(id);
      if (!res.ok) {
        const detail = (await res.json().catch(() => ({}))).detail;
        showToast(detail || t("analysisFailed"), "error");
        return;
      }
      const analysis = await res.json();
      setDeck((prev) => (prev ? { ...prev, analysis, updated_at: prev.updated_at } : prev));
    } catch {
      showToast(t("analysisFailed"), "error");
    } finally {
      setAnalyzing(false);
    }
  };

  return {
    deck,
    setDeck,
    cards,
    setCards,
    loading,
    editing,
    setEditing,
    editName,
    setEditName,
    analyzing,
    fetchDeck,
    handleRename,
    handleFormatChange,
    handleDelete,
    handleAnalyze,
    mainCards,
    sideCards,
    mainboardGroups,
    sideboardGroups,
    groupedCards,
    deckAnalysis,
    deckValidation,
    mainboardCount,
    sideboardCount,
  };
}
