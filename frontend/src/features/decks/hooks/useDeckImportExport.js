import { useEffect, useRef, useState } from "react";
import {
  fetchDeckImagesStream,
  fetchDeckPdfStream,
  fetchDeckTextExport,
  getDeckImagesDownloadUrl,
  getDeckPdfDownloadUrl,
  importDecklist,
} from "../../../api/decks.js";

function parseSseChunk(buffer, onEvent) {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() || "";
  for (const part of parts) {
    const line = part.trim();
    if (!line.startsWith("data: ")) continue;
    onEvent(JSON.parse(line.slice(6)));
  }
  return rest;
}

async function streamExport(fetcher, onProgress) {
  const res = await fetcher();
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Export failed");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let exportId = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = parseSseChunk(buffer, (data) => {
      if (data.type === "progress") onProgress(data);
      if (data.type === "complete") exportId = data.export_id;
      if (data.type === "error") throw new Error(data.message || "Export failed");
    });
  }

  return exportId;
}

export function getExportProgressLabel(progress, t) {
  if (!progress) return "";
  if (progress.phase === "download") return `${progress.current}/${progress.total}`;
  if (progress.phase === "file") return t("downloadingShort");
  return t("generatingShort");
}

export function useDeckImportExport({ id, cards, fetchDeck, language, showToast, t }) {
  const [exporting, setExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(null);
  const [exportingImages, setExportingImages] = useState(false);
  const [exportImagesProgress, setExportImagesProgress] = useState(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [importing, setImporting] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importText, setImportText] = useState("");
  const [importNotFound, setImportNotFound] = useState([]);
  const [exportButtonWidth, setExportButtonWidth] = useState(null);

  const importAbortControllerRef = useRef(null);
  const copyDecklistButtonRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showExportMenu && !event.target.closest(".export-dropdown")) {
        setShowExportMenu(false);
      }
    };
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, [showExportMenu]);

  useEffect(() => {
    const button = copyDecklistButtonRef.current;
    if (!button) return undefined;

    const updateWidth = () => {
      const computed = window.getComputedStyle(button);
      const fontSize = Number.parseFloat(computed.fontSize) || 16;
      setExportButtonWidth((button.offsetWidth || 0) + fontSize);
    };

    updateWidth();
    let observer = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver(updateWidth);
      observer.observe(button);
    }
    window.addEventListener("resize", updateWidth);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", updateWidth);
    };
  }, [language]);

  const handleExport = async () => {
    setShowExportMenu(false);
    setExporting(true);
    setExportProgress({ phase: "download", current: 0, total: 0 });
    try {
      const exportId = await streamExport(() => fetchDeckPdfStream(id), setExportProgress);
      if (exportId) {
        setExportProgress({ phase: "file", current: 0, total: 0 });
        const anchor = document.createElement("a");
        anchor.href = getDeckPdfDownloadUrl(id, exportId);
        anchor.click();
        showToast(t("exportSuccess"));
      }
    } catch (error) {
      showToast(error.message || t("exportFailed"), "error");
    } finally {
      setExporting(false);
      setExportProgress(null);
    }
  };

  const handleExportImages = async () => {
    setShowExportMenu(false);
    setExportingImages(true);
    setExportImagesProgress({ phase: "download", current: 0, total: 0 });
    try {
      const exportId = await streamExport(() => fetchDeckImagesStream(id), setExportImagesProgress);
      if (exportId) {
        setExportImagesProgress({ phase: "file", current: 0, total: 0 });
        const anchor = document.createElement("a");
        anchor.href = getDeckImagesDownloadUrl(id, exportId);
        anchor.click();
        showToast(t("exportImagesSuccess"));
      }
    } catch (error) {
      showToast(error.message || t("exportFailed"), "error");
    } finally {
      setExportingImages(false);
      setExportImagesProgress(null);
    }
  };

  const handleShareDeck = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      showToast(t("shareLinkCopied"));
    } catch {
      showToast(window.location.href, "info");
    }
  };

  const handleExportText = async () => {
    try {
      const res = await fetchDeckTextExport(id);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        showToast(errData.detail || t("copyFailed"), "error");
        return;
      }
      const text = await res.text();
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      showToast(t("decklistCopied"));
    } catch {
      showToast(t("copyFailed"), "error");
    }
  };

  const handleImportSubmit = async () => {
    if (!importText.trim()) return;
    setImporting(true);
    importAbortControllerRef.current = new AbortController();
    try {
      const res = await importDecklist(id, importText, importAbortControllerRef.current.signal);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        showToast(errData.detail || (language === "zh" ? "导入失败" : "Import failed"), "error");
        return;
      }
      const data = await res.json();
      const addedCount = data.added.reduce((sum, card) => sum + card.quantity, 0);
      const notFoundCount = data.not_found.length;
      const resolvedCards = data.added.filter((card) => card.resolved_from);

      let message = language === "zh"
        ? `成功导入 ${addedCount} 张卡牌`
        : `Successfully imported ${addedCount} cards`;
      if (notFoundCount > 0) {
        message += language === "zh" ? `，${notFoundCount} 张未找到` : `, ${notFoundCount} not found`;
      }
      if (resolvedCards.length > 0) {
        const resolvedInfo = resolvedCards.map((card) => `"${card.resolved_from}" → "${card.name}"`).join(", ");
        message += language === "zh"
          ? `（通过 Scryfall 解析：${resolvedInfo}）`
          : ` (resolved via Scryfall: ${resolvedInfo})`;
      }
      showToast(message, notFoundCount > 0 ? "warning" : "success");

      if (notFoundCount > 0) setImportNotFound(data.not_found);
      setShowImportModal(false);
      setImportText("");
      await fetchDeck();
    } catch (error) {
      if (error.name === "AbortError") {
        showToast(language === "zh" ? "导入已取消" : "Import cancelled", "info");
      } else {
        showToast(language === "zh" ? "导入失败" : "Import failed", "error");
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

  const exportBusy = exporting || exportingImages;
  const exportButtonLabel = exporting
    ? getExportProgressLabel(exportProgress, t)
    : exportingImages
      ? getExportProgressLabel(exportImagesProgress, t)
      : t("exportDeck");
  const exportButtonStyle = exportButtonWidth
    ? { width: `${Math.max(exportButtonWidth, 176)}px` }
    : { minWidth: "176px" };

  return {
    exporting,
    exportProgress,
    exportingImages,
    exportImagesProgress,
    showExportMenu,
    setShowExportMenu,
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
    handleExport,
    handleExportImages,
    handleShareDeck,
    handleExportText,
    handleImportSubmit,
    handleImportCancel,
  };
}
