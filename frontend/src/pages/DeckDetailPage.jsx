import { useState, useEffect, useMemo, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext.jsx";
import { useToast } from "../contexts/ToastContext.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";
import { FORMATS, getFormatLabel } from "../utils/formats.js";
import { getImageUri } from "../utils/cardImage.js";
import {
    buildDeckAnalysis,
    DOUBLE_FACED_LAYOUTS,
    getQuantityIncreaseGuards,
    getPreviewData,
    splitDeckBoards,
    validateDeck,
} from "../features/decks/deckModel.js";
import {
    addDeckCard,
    analyzeDeck,
    deleteDeck,
    fetchDeckImagesDownload,
    fetchDeckImagesStream,
    fetchDeckPdfDownload,
    fetchDeckPdfStream,
    fetchDeckTextExport,
    fetchSharedDeck,
    fetchSharedDeckCards,
    importDecklist,
    patchDeckCard,
    removeDeckCard,
    updateDeck,
} from "../api/decks.js";
import { fetchCardPrints, normalizePrints } from "../api/cards.js";
import DeckAnalysisPanel from "../features/decks/components/DeckAnalysisPanel.jsx";
import DeckBoard from "../features/decks/components/DeckBoard.jsx";
import DeckContextMenu from "../features/decks/components/DeckContextMenu.jsx";
import DeckPreviewPanel from "../features/decks/components/DeckPreviewPanel.jsx";
import ArtPickerModal from "../features/decks/components/ArtPickerModal.jsx";
import ImportDeckModal from "../features/decks/components/ImportDeckModal.jsx";
import MobileDeckSheet from "../features/decks/components/MobileDeckSheet.jsx";
import MovePanel from "../features/decks/components/MovePanel.jsx";


/* ── Main Component ── */

function DeckDetailPage({ imageMode }) {
    const { id } = useParams();
    const navigate = useNavigate();
    const { user } = useAuth();
    const { showToast } = useToast();
    const { t, language } = useLanguage();
    const [deck, setDeck] = useState(null);
    const [cards, setCards] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(false);
    const [editName, setEditName] = useState("");
    const [exporting, setExporting] = useState(false);
    const [exportProgress, setExportProgress] = useState(null);
    const [exportingImages, setExportingImages] = useState(false);
    const [exportImagesProgress, setExportImagesProgress] = useState(null);
    const [importing, setImporting] = useState(false);
    const [showImportModal, setShowImportModal] = useState(false);
    const [importText, setImportText] = useState("");
    const [importNotFound, setImportNotFound] = useState([]);
    const [selectedCard, setSelectedCard] = useState(null);
    const [previewFlipped, setPreviewFlipped] = useState(false);
    const [showMobileSheet, setShowMobileSheet] = useState(false);
    const [showExportMenu, setShowExportMenu] = useState(false);
    const [showArtPicker, setShowArtPicker] = useState(false);
    const [artPrints, setArtPrints] = useState([]);
    const [loadingPrints, setLoadingPrints] = useState(false);
    const [analyzing, setAnalyzing] = useState(false);

    const hoverTimerRef = useRef(null);
    const previewLockedRef = useRef(false);
    const importAbortControllerRef = useRef(null);
    const draggedCardRef = useRef(null);
    const longPressTimerRef = useRef(null);

    const [dragOverBoard, setDragOverBoard] = useState(null);
    const [touchDragCard, setTouchDragCard] = useState(null); // 卡牌被长按选中待移动
    const [showMovePanel, setShowMovePanel] = useState(false); // 显示底部移动面板
    const [contextMenu, setContextMenu] = useState(null); // { x, y, item }

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

    // ── Data fetching ──

    const fetchDeck = async () => {
        try {
            const [deckRes, cardsRes] = await Promise.all([
                fetchSharedDeck(id),
                fetchSharedDeckCards(id),
            ]);
            if (deckRes.status === 404) {
                showToast(t('deckNotFound'), "error");
                navigate("/");
                return;
            }
            if (deckRes.ok && cardsRes.ok) {
                const deckData = await deckRes.json();
                setDeck(deckData);
                setEditName(deckData.name);
                setCards(await cardsRes.json());
            }
        } catch {
            showToast(t('loadFailed'), "error");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchDeck(); }, [id]);

    // Close export dropdown when clicking outside
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (showExportMenu && !e.target.closest('.export-dropdown')) {
                setShowExportMenu(false);
            }
        };
        document.addEventListener('click', handleClickOutside);
        return () => document.removeEventListener('click', handleClickOutside);
    }, [showExportMenu]);

    // ── Derived deck data ──

    const { mainCards, sideCards, mainboardGroups, sideboardGroups } = useMemo(
        () => splitDeckBoards(cards, language),
        [cards, language]
    );

    const analysisCards = mainCards;

    // Mainboard groups for analysis
    const groupedCards = mainboardGroups;

    // ── Deck analysis ──

    const deckAnalysis = useMemo(() => buildDeckAnalysis(analysisCards, language), [analysisCards, language]);

    // Auto-select first card
    useEffect(() => {
        if (cards.length > 0 && !selectedCard) {
            setSelectedCard(cards[0]);
        }
    }, [cards]);

    // ── Handlers ──

    const handleRename = async () => {
        if (!editName.trim() || editName.trim() === deck.name) {
            setEditing(false);
            return;
        }
        const res = await updateDeck(id, { name: editName.trim() });
        if (res.ok) {
            const updated = await res.json();
            setDeck((prev) => ({ ...prev, name: updated.name }));
            showToast(t('deckRenamed'));
        }
        setEditing(false);
    };

    const handleFormatChange = async (e) => {
        const newFormat = e.target.value;
        if (newFormat === deck.format) return;
        const res = await updateDeck(id, { name: deck.name, format: newFormat });
        if (res.ok) {
            const updated = await res.json();
            setDeck((prev) => ({ ...prev, format: updated.format }));
            showToast(language === 'zh' ? `赛制已切换为「${getFormatLabel(updated.format, language)}」` : `Format changed to "${getFormatLabel(updated.format, language)}"`);
        }
    };

    const handleDelete = async () => {
        if (!confirm(language === 'zh' ? "确定要删除这个卡组吗？" : "Are you sure you want to delete this deck?")) return;
        const res = await deleteDeck(id);
        if (res.ok) {
            showToast(t('deckDeleted'));
            navigate("/decks");
        }
    };

    const handleQuantityChange = async (cardId, delta, board = "mainboard") => {
        const card = cards.find((c) => c.card_id === cardId && c.board === board);
        if (!card) return;
        const newQty = card.quantity + delta;
        if (newQty <= 0) {
            await handleRemoveCard(cardId, board);
            return;
        }
        if (delta > 0) {
            const guard = getQuantityIncreaseGuards(cards, deck?.format, language)[`${cardId}:${board}`];
            if (guard?.canIncrease === false) {
                showToast(guard.reason, "error");
                return;
            }
        }
        const res = await addDeckCard(id, { card_id: cardId, quantity: delta, board });
        if (res.ok) {
            setCards((prev) =>
                prev.map((c) => (c.card_id === cardId && c.board === board ? { ...c, quantity: newQty } : c))
            );
            if (selectedCard?.card_id === cardId && selectedCard?.board === board) {
                setSelectedCard((prev) => ({ ...prev, quantity: newQty }));
            }
        }
    };

    const handleRemoveCard = async (cardId, board) => {
        const res = await removeDeckCard(id, cardId, board);
        if (res.ok) {
            setCards((prev) => prev.filter((c) => !(c.card_id === cardId && c.board === board)));
            if (selectedCard?.card_id === cardId && selectedCard?.board === board) setSelectedCard(null);
            showToast(t('cardRemoved'));
        }
    };

    // Move card between boards (mainboard <-> sideboard)
    // quantity: 'all' for drag, 1 for single card move
    const handleMoveCard = async (cardId, fromBoard, toBoard, quantity = 'all') => {
        const card = cards.find((c) => c.card_id === cardId && c.board === fromBoard);
        if (!card || fromBoard === toBoard) return;

        const moveCount = quantity === 'all' ? card.quantity : 1;

        // Check if target board already has this card
        const targetCard = cards.find((c) => c.card_id === cardId && c.board === toBoard);

        // Update source card quantity (or remove if moving all)
        if (quantity === 'all') {
            // Remove from source board
            const removeRes = await removeDeckCard(id, cardId, fromBoard);
            if (!removeRes.ok) {
                showToast(language === 'zh' ? '移动失败' : 'Failed to move card', "error");
                return;
            }
        } else {
            // Reduce quantity by 1
            const newSourceQty = card.quantity - moveCount;
            if (newSourceQty <= 0) {
                const removeRes = await removeDeckCard(id, cardId, fromBoard);
                if (!removeRes.ok) {
                    showToast(language === 'zh' ? '移动失败' : 'Failed to move card', "error");
                    return;
                }
            } else {
                const updateRes = await addDeckCard(id, { card_id: cardId, quantity: -moveCount, board: fromBoard });
                if (!updateRes.ok) {
                    showToast(language === 'zh' ? '移动失败' : 'Failed to move card', "error");
                    return;
                }
            }
        }

        // Add to target board
        const addRes = await addDeckCard(id, { card_id: cardId, quantity: moveCount, board: toBoard });
        if (!addRes.ok) {
            showToast(language === 'zh' ? '移动失败' : 'Failed to move card', "error");
            // Restore source card
            await addDeckCard(id, { card_id: cardId, quantity: moveCount, board: fromBoard });
            return;
        }

        // Update local state
        setCards((prev) => {
            let newState = prev;

            // Update source card
            if (quantity === 'all' || card.quantity - moveCount <= 0) {
                newState = newState.filter((c) => !(c.card_id === cardId && c.board === fromBoard));
            } else {
                newState = newState.map((c) =>
                    c.card_id === cardId && c.board === fromBoard
                        ? { ...c, quantity: c.quantity - moveCount }
                        : c
                );
            }

            // Update target card (add or update)
            if (targetCard) {
                newState = newState.map((c) =>
                    c.card_id === cardId && c.board === toBoard
                        ? { ...c, quantity: c.quantity + moveCount }
                        : c
                );
            } else {
                newState = [...newState, {
                    ...card,
                    board: toBoard,
                    quantity: moveCount,
                }];
            }

            return newState;
        });

        // Update selected card if needed
        if (selectedCard?.card_id === cardId && selectedCard?.board === fromBoard) {
            if (quantity === 'all' || card.quantity - moveCount <= 0) {
                setSelectedCard(null);
            } else {
                setSelectedCard((prev) => ({ ...prev, quantity: prev.quantity - moveCount }));
            }
        }

        const actionText = quantity === 'all'
            ? (language === 'zh' ? '已全部移动到' : 'Moved all to')
            : (language === 'zh' ? '已移动1张到' : 'Moved 1 to');
        showToast(`${actionText}${toBoard === 'sideboard' ? (language === 'zh' ? '备牌' : 'sideboard') : (language === 'zh' ? '主卡组' : 'mainboard')}`);
    };

    // Drag handlers
    const handleDragStart = (e, item) => {
        if (!isOwner) {
            e.preventDefault();
            return;
        }
        draggedCardRef.current = item;
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', JSON.stringify({ cardId: item.card_id, board: item.board }));
        // Add dragging class after a small delay to allow the drag image to be captured
        setTimeout(() => {
            e.target.classList.add('dragging');
        }, 0);
    };

    const handleDragEnd = (e) => {
        e.target.classList.remove('dragging');
        draggedCardRef.current = null;
        setDragOverBoard(null);
    };

    const handleDragOver = (e, board) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        setDragOverBoard(board);
    };

    const handleDragLeave = (e) => {
        // Only clear if we're leaving the entire drop zone
        if (!e.currentTarget.contains(e.relatedTarget)) {
            setDragOverBoard(null);
        }
    };

    const handleDrop = (e, toBoard) => {
        e.preventDefault();
        setDragOverBoard(null);

        try {
            const data = JSON.parse(e.dataTransfer.getData('text/plain'));
            const { cardId, board: fromBoard } = data;
            handleMoveCard(cardId, fromBoard, toBoard, 'all');
        } catch {
            // Invalid drag data
        }
    };

    // ── Touch drag handlers for mobile ──

    const handleTouchStart = (e, item) => {
        if (!isOwner) return;
        // Long press to show move panel
        longPressTimerRef.current = setTimeout(() => {
            setTouchDragCard(item);
            setShowMovePanel(true);
            // Haptic feedback if available
            if (navigator.vibrate) navigator.vibrate(50);
            // Prevent click event
            e.preventDefault();
        }, 400); // 400ms long press
    };

    const handleTouchMove = (e) => {
        // Cancel long press if user moves before timer completes
        if (longPressTimerRef.current) {
            clearTimeout(longPressTimerRef.current);
            longPressTimerRef.current = null;
        }
    };

    const handleTouchEnd = () => {
        // Cancel long press timer if touch ends before timer completes
        if (longPressTimerRef.current) {
            clearTimeout(longPressTimerRef.current);
            longPressTimerRef.current = null;
        }
    };

    const handleMovePanelClose = () => {
        setShowMovePanel(false);
        setTouchDragCard(null);
    };

    // ── Context menu handlers (right-click) ──

    const handleContextMenu = (e, item) => {
        if (!isOwner) return;
        e.preventDefault();
        e.stopPropagation();
        setContextMenu({
            x: e.clientX,
            y: e.clientY,
            item,
        });
    };

    const handleContextMenuClose = () => {
        setContextMenu(null);
    };

    const handleContextMenuMoveOne = (toBoard) => {
        if (contextMenu?.item) {
            handleMoveCard(contextMenu.item.card_id, contextMenu.item.board, toBoard, 1);
        }
        handleContextMenuClose();
    };

    // Close context menu on click outside
    useEffect(() => {
        const handleClickOutside = () => setContextMenu(null);
        if (contextMenu) {
            document.addEventListener('click', handleClickOutside);
            return () => document.removeEventListener('click', handleClickOutside);
        }
    }, [contextMenu]);

    const handleExport = async () => {
        setShowExportMenu(false);
        setExporting(true);
        setExportProgress({ phase: "download", current: 0, total: 0 });
        try {
            const res = await fetchDeckPdfStream(id);
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                showToast(err.detail || t('exportFailed'), "error");
                return;
            }
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let exportId = null;
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split("\n\n");
                buffer = parts.pop();
                for (const part of parts) {
                    const line = part.trim();
                    if (!line.startsWith("data: ")) continue;
                    const data = JSON.parse(line.slice(6));
                    if (data.type === "progress") setExportProgress(data);
                    else if (data.type === "complete") exportId = data.export_id;
                }
            }
            if (exportId) {
                const pdfRes = await fetchDeckPdfDownload(id, exportId);
                if (!pdfRes.ok) { showToast(language === 'zh' ? "下载 PDF 失败" : "Failed to download PDF", "error"); return; }
                const blob = await pdfRes.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${deck?.name || "deck"}_cards.pdf`;
                a.click();
                URL.revokeObjectURL(url);
                showToast(t('exportSuccess'));
            }
        } catch { showToast(t('exportFailed'), "error"); }
        finally { setExporting(false); setExportProgress(null); }
    };

    const handleExportImages = async () => {
        setShowExportMenu(false);
        setExportingImages(true);
        setExportImagesProgress({ phase: "download", current: 0, total: 0 });
        try {
            const res = await fetchDeckImagesStream(id);
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                showToast(err.detail || t('exportFailed'), "error");
                return;
            }
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let exportId = null;
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split("\n\n");
                buffer = parts.pop();
                for (const part of parts) {
                    const line = part.trim();
                    if (!line.startsWith("data: ")) continue;
                    const data = JSON.parse(line.slice(6));
                    if (data.type === "progress") setExportImagesProgress(data);
                    else if (data.type === "complete") exportId = data.export_id;
                }
            }
            if (exportId) {
                const zipRes = await fetchDeckImagesDownload(id, exportId);
                if (!zipRes.ok) { showToast(language === 'zh' ? "下载 ZIP 失败" : "Failed to download ZIP", "error"); return; }
                const blob = await zipRes.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${deck?.name || "deck"}_images.zip`;
                a.click();
                URL.revokeObjectURL(url);
                showToast(t('exportImagesSuccess'));
            }
        } catch { showToast(t('exportFailed'), "error"); }
        finally { setExportingImages(false); setExportImagesProgress(null); }
    };

    const handleAnalyze = async () => {
        if (analyzing) return;
        if (!cards.length) {
            showToast(t('analysisEmptyDeck'), "error");
            return;
        }
        setAnalyzing(true);
        try {
            const res = await analyzeDeck(id);
            if (!res.ok) {
                const detail = (await res.json().catch(() => ({}))).detail;
                showToast(detail || t('analysisFailed'), "error");
                return;
            }
            const analysis = await res.json();
            setDeck((prev) => (prev ? { ...prev, analysis, updated_at: prev.updated_at } : prev));
        } catch {
            showToast(t('analysisFailed'), "error");
        } finally {
            setAnalyzing(false);
        }
    };

    const formatRelativeTime = (isoString) => {
        if (!isoString) return "";
        const diff = Date.now() - new Date(isoString).getTime();
        const minutes = Math.floor(diff / 60000);
        if (minutes < 1) return t('justNow');
        if (minutes < 60) return t('minutesAgo').replace('{n}', minutes);
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return t('hoursAgo').replace('{n}', hours);
        const days = Math.floor(hours / 24);
        return t('daysAgo').replace('{n}', days);
    };

    const handleShareDeck = async () => {
        try {
            await navigator.clipboard.writeText(window.location.href);
            showToast(t('shareLinkCopied'));
        } catch {
            showToast(window.location.href, "info");
        }
    };

    const handleExportText = async () => {
        try {
            const res = await fetchDeckTextExport(id);
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                showToast(errData.detail || t('copyFailed'), "error");
                return;
            }
            const text = await res.text();

            // Try clipboard API first, fallback to execCommand
            try {
                await navigator.clipboard.writeText(text);
                showToast(t('decklistCopied'));
            } catch {
                // Fallback for older browsers or restricted contexts
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                showToast(t('decklistCopied'));
            }
        } catch {
            showToast(t('copyFailed'), "error");
        }
    };

    const handleImportSubmit = async () => {
        if (!importText.trim()) return;
        setImporting(true);
        // Create AbortController for this request
        importAbortControllerRef.current = new AbortController();
        try {
            const res = await importDecklist(id, importText, importAbortControllerRef.current.signal);
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                showToast(errData.detail || (language === 'zh' ? "导入失败" : "Import failed"), "error");
                return;
            }
            const data = await res.json();
            const addedCount = data.added.reduce((s, c) => s + c.quantity, 0);
            const notFoundCount = data.not_found.length;
            const resolvedCards = data.added.filter(c => c.resolved_from);

            let msg = language === 'zh'
                ? `成功导入 ${addedCount} 张卡牌`
                : `Successfully imported ${addedCount} cards`;
            if (notFoundCount > 0) {
                msg += language === 'zh' ? `，${notFoundCount} 张未找到` : `, ${notFoundCount} not found`;
            }
            if (resolvedCards.length > 0) {
                const resolvedInfo = resolvedCards.map(c => `"${c.resolved_from}" → "${c.name}"`).join(", ");
                msg += language === 'zh' ? `（通过 Scryfall 解析：${resolvedInfo}）` : ` (resolved via Scryfall: ${resolvedInfo})`;
            }
            showToast(msg, notFoundCount > 0 ? "warning" : "success");

            if (notFoundCount > 0) setImportNotFound(data.not_found);
            setShowImportModal(false);
            setImportText("");
            await fetchDeck();
        } catch (e) {
            if (e.name === 'AbortError') {
                showToast(language === 'zh' ? '导入已取消' : 'Import cancelled', "info");
            } else {
                showToast(language === 'zh' ? "导入失败" : "Import failed", "error");
            }
        } finally {
            setImporting(false);
            importAbortControllerRef.current = null;
        }
    };

    const handleImportCancel = () => {
        if (importAbortControllerRef.current) {
            importAbortControllerRef.current.abort();
        }
        setShowImportModal(false);
        setImportText("");
    };

    // ── Art picker handlers ──

    const handleOpenArtPicker = async () => {
        if (!selectedCard) return;
        if (artPrints.length > 0) {
            setShowArtPicker(!showArtPicker);
            return;
        }
        const oracleId = selectedCard.card_id;
        if (!oracleId) return;
        setLoadingPrints(true);
        setShowArtPicker(true);
        try {
            const res = await fetchCardPrints(oracleId);
            if (!res.ok) return;
            const data = await res.json();
            setArtPrints(normalizePrints(data));
        } catch {
            showToast(t('fetchVersionsFailed'), "error");
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
            const res = await patchDeckCard(id, selectedCard.card_id, { print_id: print.id, image_url: imageUrl, display_url: displayUrl, board: selectedCard.board });
            if (res.ok) {
                setCards((prev) =>
                    prev.map((c) =>
                        c.card_id === selectedCard.card_id && c.board === selectedCard.board
                            ? {
                                ...c,
                                print_id: print.id,
                                image_url: imageUrl,
                                display_url: displayUrl,
                                card: { ...c.card, rarity: print.rarity || c.card.rarity, card_faces: print.card_faces || c.card.card_faces },
                            }
                            : c
                    )
                );
                setSelectedCard((prev) => ({
                    ...prev,
                    print_id: print.id,
                    image_url: imageUrl,
                    display_url: displayUrl,
                    card: { ...prev.card, rarity: print.rarity || prev.card.rarity, card_faces: print.card_faces || prev.card.card_faces },
                }));
                showToast(t('artChanged'));
            } else {
                showToast(t('artChangeFailed'), "error");
            }
        } catch {
            showToast(t('artChangeFailed'), "error");
        }
        setShowArtPicker(false);
    };

    const handleResetArt = async () => {
        if (!selectedCard) return;
        try {
            const res = await patchDeckCard(id, selectedCard.card_id, { print_id: null, image_url: null, display_url: null, board: selectedCard.board });
            if (res.ok) {
                setCards((prev) =>
                    prev.map((c) =>
                        c.card_id === selectedCard.card_id && c.board === selectedCard.board
                            ? { ...c, print_id: null, image_url: null, display_url: null }
                            : c
                    )
                );
                setSelectedCard((prev) => ({ ...prev, print_id: null, image_url: null, display_url: null }));
                showToast(t('artResetSuccess'));
            }
        } catch {
            showToast(t('artChangeFailed'), "error");
        }
        setShowArtPicker(false);
    };

    // Reset art picker when selected card changes
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
                const selectedPrint = prints.find((p) => p.id === selectedCard.print_id && p.card_faces?.length >= 2);
                const fallbackPrint = prints.find((p) => p.card_faces?.length >= 2);
                const faces = (selectedPrint || fallbackPrint)?.card_faces;
                if (cancelled || !faces?.length) return;

                setCards((prev) =>
                    prev.map((c) =>
                        c.card_id === selectedCard.card_id && c.board === selectedCard.board
                            ? { ...c, card: { ...c.card, card_faces: faces } }
                            : c
                    )
                );
                setSelectedCard((prev) => (
                    prev && prev.card_id === selectedCard.card_id && prev.board === selectedCard.board
                        ? { ...prev, card: { ...prev.card, card_faces: faces } }
                        : prev
                ));
            } catch {
                // Ignore; the preview will keep using the card data already loaded.
            }
        };

        hydrateFaces();
        return () => { cancelled = true; };
    }, [selectedCard?.card_id, selectedCard?.board, selectedCard?.print_id, selectedCard?.card?.card_faces, selectedCard?.card?.layout]);

    // Lock body scroll while the mobile bottom sheet is open
    useEffect(() => {
        if (!showMobileSheet) return;

        // 仅在移动端宽度（<= 768px）下锁定滚动
        const isMobile = window.innerWidth <= 768;
        if (!isMobile) return;

        const prev = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        return () => { document.body.style.overflow = prev; };
    }, [showMobileSheet]);

    // ── Render ──

    const isOwner = !!(user && deck && user.id === deck.user_id);

    if (loading) {
        return (
            <div className="loading">
                <div className="loading-spinner" />
                <p>{t('loadingDeck')}</p>
            </div>
        );
    }
    if (!deck) return null;

    const mainboardCount = mainCards.reduce((sum, card) => sum + card.quantity, 0);
    const sideboardCount = sideCards.reduce((sum, card) => sum + card.quantity, 0);
    const selectedPreview = getPreviewData(selectedCard, previewFlipped);
    const deckValidation = validateDeck(cards, deck.format, language);
    const quantityIncreaseGuards = getQuantityIncreaseGuards(cards, deck.format, language);

    return (
        <div className="deck-detail">
            {/* Header */}
            <div className="deck-detail-header">
                {!isOwner ? (
                    <button className="btn-secondary btn-back" onClick={() => navigate("/")}>
                        <svg className="btn-back-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M19 12H5M12 19l-7-7 7-7" />
                        </svg>
                        <span className="btn-back-text">&larr; {t('backToHome')}</span>
                    </button>
                ) : (
                    <button className="btn-secondary btn-back" onClick={() => navigate("/decks")}>
                        <svg className="btn-back-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M19 12H5M12 19l-7-7 7-7" />
                        </svg>
                        <span className="btn-back-text">&larr; {t('backToDecks')}</span>
                    </button>
                )}
                <div className="deck-detail-title">
                    {isOwner && editing ? (
                        <form onSubmit={(e) => { e.preventDefault(); handleRename(); }} className="deck-rename-form">
                            <input value={editName} onChange={(e) => setEditName(e.target.value)} autoFocus onBlur={handleRename} />
                        </form>
                    ) : (
                        <h2
                            onClick={isOwner ? () => setEditing(true) : undefined}
                            title={isOwner ? t('clickToRename') : undefined}
                            style={isOwner ? undefined : { cursor: "default" }}
                        >{deck.name}</h2>
                    )}
                    {!isOwner ? (
                        <span className="deck-format-badge">{getFormatLabel(deck.format || "undefined", language)}</span>
                    ) : (
                        <select
                            className={`deck-format-select format-${deck.format || "undefined"}`}
                            value={deck.format || "undefined"}
                            onChange={handleFormatChange}
                            title={t('switchFormat')}
                        >
                            {FORMATS.map((f) => <option key={f.key} value={f.key}>{language === 'zh' ? f.labelZh : f.labelEn}</option>)}
                        </select>
                    )}
                </div>
                <div className="deck-detail-actions">
                    {isOwner && (
                        <button className="btn-secondary" onClick={handleShareDeck} title={t('share')}>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="18" cy="5" r="3" />
                                <circle cx="6" cy="12" r="3" />
                                <circle cx="18" cy="19" r="3" />
                                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                            </svg>
                            <span className="btn-label">{t('share')}</span>
                        </button>
                    )}
                    {isOwner && (
                        <button className="btn-secondary" onClick={() => setShowImportModal(true)} title={t('importDecklist')}>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                <polyline points="14 2 14 8 20 8" />
                                <line x1="12" y1="18" x2="12" y2="12" />
                                <line x1="9" y1="15" x2="15" y2="15" />
                            </svg>
                            <span className="btn-label">{t('importDecklist')}</span>
                        </button>
                    )}
                    <button className="btn-secondary" onClick={handleExportText} disabled={cards.length === 0} title={t('copyDecklist')}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                        </svg>
                        <span className="btn-label">{t('copyDecklist')}</span>
                    </button>
                    <div className="export-dropdown">
                        <button
                            className="btn-accent"
                            onClick={() => setShowExportMenu(!showExportMenu)}
                            disabled={(exporting || exportingImages) || cards.length === 0}
                            title={t('exportDeck')}
                        >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                <polyline points="7 10 12 15 17 10" />
                                <line x1="12" y1="15" x2="12" y2="3" />
                            </svg>
                            <span className="btn-label">{exporting || exportingImages ? `${t('downloadProgress')}...` : t('exportDeck')}</span>
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: '4px' }}>
                                <polyline points="6 9 12 15 18 9" />
                            </svg>
                        </button>
                        {showExportMenu && (
                            <div className="export-dropdown-menu">
                                <button onClick={handleExport} disabled={exporting}>
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <rect x="2" y="3" width="20" height="18" rx="2" ry="2" />
                                        <line x1="2" y1="7" x2="22" y2="7" />
                                        <line x1="2" y1="17" x2="22" y2="17" />
                                    </svg>
                                    {t('exportPdf')}
                                </button>
                                <button onClick={handleExportImages} disabled={exportingImages}>
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                                        <circle cx="8.5" cy="8.5" r="1.5" />
                                        <polyline points="21 15 16 10 5 21" />
                                    </svg>
                                    {t('exportImages')}
                                </button>
                            </div>
                        )}
                    </div>
                    {isOwner && (
                        <button className="btn-danger" onClick={handleDelete} title={t('deleteDeck')}>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="3 6 5 6 21 6" />
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                                <line x1="10" y1="11" x2="10" y2="17" />
                                <line x1="14" y1="11" x2="14" y2="17" />
                            </svg>
                            <span className="btn-label">{t('deleteDeck')}</span>
                        </button>
                    )}
                </div>
            </div>

            {exportProgress && (
                <div className="export-progress">
                    <div className="export-progress-bar">
                        <div className="export-progress-fill" style={{ width: `${exportProgress.total > 0 ? (exportProgress.current / exportProgress.total) * 100 : 0}%` }} />
                    </div>
                    <span className="export-progress-text">
                        {exportProgress.phase === "download"
                            ? `${t('downloadProgress')} ${exportProgress.current}/${exportProgress.total}`
                            : t('generatingPdf')}
                    </span>
                </div>
            )}

            {exportImagesProgress && (
                <div className="export-progress">
                    <div className="export-progress-bar">
                        <div className="export-progress-fill" style={{ width: `${exportImagesProgress.total > 0 ? (exportImagesProgress.current / exportImagesProgress.total) * 100 : 0}%` }} />
                    </div>
                    <span className="export-progress-text">
                        {exportImagesProgress.phase === "download"
                            ? `${t('downloadProgress')} ${exportImagesProgress.current}/${exportImagesProgress.total}`
                            : t('generatingZip')}
                    </span>
                </div>
            )}

            {importNotFound.length > 0 && (
                <div className="import-not-found">
                    <div className="import-not-found-header">
                        <span>{language === 'zh' ? `以下 ${importNotFound.length} 张卡牌未在数据库中找到：` : `The following ${importNotFound.length} cards were not found in the database:`}</span>
                        <button className="import-not-found-close" onClick={() => setImportNotFound([])}>&times;</button>
                    </div>
                    <ul>
                        {importNotFound.map((name, i) => (
                            <li key={i}>
                                <a
                                    className="import-not-found-link"
                                    href={`https://scryfall.com/search?q=${encodeURIComponent(name)}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    title={language === 'zh' ? '在 Scryfall 中搜索' : 'Search on Scryfall'}
                                >
                                    {name}
                                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                                        <polyline points="15 3 21 3 21 9" />
                                        <line x1="10" y1="14" x2="21" y2="3" />
                                    </svg>
                                </a>
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {cards.length === 0 ? (
                <div className="no-results"><p>{t('deckEmpty')}</p></div>
            ) : (
                <div className="deck-body">
                    <DeckPreviewPanel
                        selectedCard={selectedCard}
                        selectedPreview={selectedPreview}
                        deck={deck}
                        language={language}
                        isOwner={isOwner}
                        previewFlipped={previewFlipped}
                        onFlip={() => setPreviewFlipped((v) => !v)}
                        onOpenArtPicker={handleOpenArtPicker}
                        onMouseEnter={() => { previewLockedRef.current = true; cancelPendingSelect(); }}
                        onMouseLeave={() => { previewLockedRef.current = false; }}
                        t={t}
                    />

                    <DeckBoard
                        mainboardGroups={mainboardGroups}
                        sideboardGroups={sideboardGroups}
                        mainboardCount={mainboardCount}
                        sideboardCount={sideboardCount}
                        selectedCard={selectedCard}
                        cardIssuesById={deckValidation.cardIssuesById}
                        quantityIncreaseGuards={quantityIncreaseGuards}
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
                            onPreviewCancel: cancelPendingSelect,
                            onSelectCard: (item) => { setSelectedCard(item); setShowMobileSheet(true); },
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
                        formatRelativeTime={formatRelativeTime}
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
                    onClose={() => setShowArtPicker(false)}
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
                    onFlip={() => setPreviewFlipped((v) => !v)}
                    onClose={() => setShowMobileSheet(false)}
                    onOpenArtPicker={handleOpenArtPicker}
                    t={t}
                />
            )}

            <DeckContextMenu
                contextMenu={contextMenu}
                language={language}
                onMoveOne={handleContextMenuMoveOne}
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

export default DeckDetailPage;
