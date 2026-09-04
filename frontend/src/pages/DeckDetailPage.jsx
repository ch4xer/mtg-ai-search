import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { useToast } from "../contexts/ToastContext.jsx";
import DeckAnalysisPanel from "../features/decks/components/DeckAnalysisPanel.jsx";
import ArtPickerModal from "../features/decks/components/ArtPickerModal.jsx";
import DeckBoard from "../features/decks/components/DeckBoard.jsx";
import DeckContextMenu from "../features/decks/components/DeckContextMenu.jsx";
import DeckDetailHeader from "../features/decks/components/DeckDetailHeader.jsx";
import DeckPreviewPanel from "../features/decks/components/DeckPreviewPanel.jsx";
import ImportDeckModal from "../features/decks/components/ImportDeckModal.jsx";
import ImportNotFoundBanner from "../features/decks/components/ImportNotFoundBanner.jsx";
import MobileDeckSheet from "../features/decks/components/MobileDeckSheet.jsx";
import MovePanel from "../features/decks/components/MovePanel.jsx";
import { useDeckBoardInteractions } from "../features/decks/hooks/useDeckBoardInteractions.js";
import { useDeckData } from "../features/decks/hooks/useDeckData.js";
import { useDeckImportExport } from "../features/decks/hooks/useDeckImportExport.js";
import { useDeckSelection } from "../features/decks/hooks/useDeckSelection.js";

function formatRelativeTime(isoString, t) {
  if (!isoString) return "";
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return t("justNow");
  if (minutes < 60) return t("minutesAgo").replace("{n}", minutes);
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return t("hoursAgo").replace("{n}", hours);
  const days = Math.floor(hours / 24);
  return t("daysAgo").replace("{n}", days);
}

export default function DeckDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const { t, language } = useLanguage();

  const {
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
    mainboardGroups,
    sideboardGroups,
    groupedCards,
    deckAnalysis,
    deckValidation,
    mainboardCount,
    sideboardCount,
  } = useDeckData({ id, navigate, showToast, t, language });

  const isOwner = !!(user && deck && user.id === deck.user_id);

  const {
    selectedCard,
    setSelectedCard,
    selectedPreview,
    previewFlipped,
    setPreviewFlipped,
    showMobileSheet,
    setShowMobileSheet,
    showArtPicker,
    artPrints,
    loadingPrints,
    handleOpenArtPicker,
    handleCloseArtPicker,
    handleSelectArt,
    handleResetArt,
    previewLockedRef,
    cancelPendingSelect,
    schedulePreviewSelect,
    handlePreviewPointerMove,
  } = useDeckSelection({ id, cards, setCards, showToast, t, language });

  const {
    dragOverBoard,
    touchDragCard,
    showMovePanel,
    contextMenu,
    handleQuantityChange,
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
    handleContextMenuSetCover,
  } = useDeckBoardInteractions({
    id,
    cards,
    setCards,
    selectedCard,
    setSelectedCard,
    mainboardGroups,
    sideboardGroups,
    cancelPendingSelect,
    setDeck,
    language,
    isOwner,
    showToast,
    t,
  });

  const {
    importing,
    showImportModal,
    setShowImportModal,
    importText,
    setImportText,
    importNotFound,
    setImportNotFound,
    copyDecklistButtonRef,
    exportBusy,
    exportButtonLabel,
    exportButtonStyle,
    showExportMenu,
    setShowExportMenu,
    handleExport,
    handleExportImages,
    handleShareDeck,
    handleExportText,
    handleImportSubmit,
    handleImportCancel,
  } = useDeckImportExport({ id, cards, fetchDeck, language, showToast, t });

  useEffect(() => {
    if (!showMobileSheet) return;
    if (window.innerWidth > 768) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [showMobileSheet]);

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <p>{t("loadingDeck")}</p>
      </div>
    );
  }

  if (!deck) return null;

  return (
    <div className="deck-detail">
      <DeckDetailHeader
        deck={deck}
        cards={cards}
        isOwner={isOwner}
        editing={editing}
        editName={editName}
        language={language}
        copyDecklistButtonRef={copyDecklistButtonRef}
        exportBusy={exportBusy}
        exportButtonLabel={exportButtonLabel}
        exportButtonStyle={exportButtonStyle}
        showExportMenu={showExportMenu}
        setEditing={setEditing}
        setEditName={setEditName}
        setShowExportMenu={setShowExportMenu}
        navigate={navigate}
        t={t}
        onRename={handleRename}
        onFormatChange={handleFormatChange}
        onShare={handleShareDeck}
        onShowImport={() => setShowImportModal(true)}
        onExportText={handleExportText}
        onExportPdf={handleExport}
        onExportImages={handleExportImages}
        onDelete={handleDelete}
      />

      <ImportNotFoundBanner
        importNotFound={importNotFound}
        language={language}
        onClose={() => setImportNotFound([])}
      />

      {cards.length === 0 ? (
        <div className="no-results"><p>{t("deckEmpty")}</p></div>
      ) : (
        <div className="deck-body">
          <DeckPreviewPanel
            selectedCard={selectedCard}
            selectedPreview={selectedPreview}
            deck={deck}
            language={language}
            isOwner={isOwner}
            previewFlipped={previewFlipped}
            onFlip={() => setPreviewFlipped((value) => !value)}
            onOpenArtPicker={handleOpenArtPicker}
            onMouseEnter={() => {
              previewLockedRef.current = true;
              cancelPendingSelect();
            }}
            onMouseLeave={() => {
              previewLockedRef.current = false;
            }}
            t={t}
          />

          <DeckBoard
            mainboardGroups={mainboardGroups}
            sideboardGroups={sideboardGroups}
            mainboardCount={mainboardCount}
            sideboardCount={sideboardCount}
            selectedCard={selectedCard}
            cardIssuesById={deckValidation.cardIssuesById}
            dragOverBoard={dragOverBoard}
            isOwner={isOwner}
            language={language}
            t={t}
            handlers={{
              onDragStart: handleDragStart,
              onDragEnd: handleDragEnd,
              onDragOver: handleDragOver,
              onDragLeave: handleDragLeave,
              onDrop: handleDrop,
              onContextMenu: handleContextMenu,
              onTouchStart: handleTouchStart,
              onTouchMove: handleTouchMove,
              onTouchEnd: handleTouchEnd,
              onPreviewSelect: schedulePreviewSelect,
              onPreviewPointerMove: handlePreviewPointerMove,
              onPreviewCancel: cancelPendingSelect,
              onSelectCard: (item) => {
                setSelectedCard(item);
                setShowMobileSheet(true);
              },
              onQuantityChange: handleQuantityChange,
            }}
          />

          <DeckAnalysisPanel
            deck={deck}
            deckAnalysis={deckAnalysis}
            groupedCards={groupedCards}
            language={language}
            isOwner={isOwner}
            analyzing={analyzing}
            onAnalyze={handleAnalyze}
            formatRelativeTime={(isoString) => formatRelativeTime(isoString, t)}
            t={t}
          />
        </div>
      )}

      {showArtPicker && (
        <ArtPickerModal
          selectedCard={selectedCard}
          artPrints={artPrints}
          loadingPrints={loadingPrints}
          language={language}
          onClose={handleCloseArtPicker}
          onResetArt={handleResetArt}
          onSelectArt={handleSelectArt}
          t={t}
        />
      )}

      {showMobileSheet && selectedCard && (
        <MobileDeckSheet
          selectedCard={selectedCard}
          selectedPreview={selectedPreview}
          deck={deck}
          language={language}
          isOwner={isOwner}
          previewFlipped={previewFlipped}
          onFlip={() => setPreviewFlipped((value) => !value)}
          onClose={() => setShowMobileSheet(false)}
          onOpenArtPicker={handleOpenArtPicker}
          t={t}
        />
      )}

      <DeckContextMenu
        contextMenu={contextMenu}
        language={language}
        onMoveOne={handleContextMenuMoveOne}
        onSetCover={handleContextMenuSetCover}
      />

      {showMovePanel && touchDragCard && (
        <MovePanel
          card={touchDragCard}
          language={language}
          onMove={handleMoveCard}
          onClose={handleMovePanelClose}
        />
      )}

      {showImportModal && (
        <ImportDeckModal
          importText={importText}
          importing={importing}
          language={language}
          onTextChange={setImportText}
          onSubmit={handleImportSubmit}
          onCancel={handleImportCancel}
          t={t}
        />
      )}
    </div>
  );
}
