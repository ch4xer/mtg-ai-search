import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { fetchCardFunctionTags } from "../api/cards.js";
import { useLanguage } from "../contexts/LanguageContext.jsx";

const MAIN_WIDTH = 210;
const SUBMENU_WIDTH = 320;
const VIEWPORT_GAP = 8;

function CardActionMenu({ card, position, onClose, onSearch }) {
  const { t } = useLanguage();
  const mainRef = useRef(null);
  const submenuRef = useRef(null);
  const [submenuOpen, setSubmenuOpen] = useState(false);
  const [tags, setTags] = useState([]);
  const [selectedTags, setSelectedTags] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const loadedRef = useRef(false);

  const submenuPosition = useMemo(() => {
    const fitsRight = position.left + MAIN_WIDTH + 6 + SUBMENU_WIDTH <= window.innerWidth - VIEWPORT_GAP;
    const left = fitsRight
      ? position.left + MAIN_WIDTH + 6
      : Math.max(VIEWPORT_GAP, position.left - SUBMENU_WIDTH - 6);
    return {
      left,
      top: Math.max(VIEWPORT_GAP, Math.min(position.top, window.innerHeight - 430)),
    };
  }, [position]);

  useEffect(() => {
    const focusFrame = requestAnimationFrame(() => mainRef.current?.querySelector("button")?.focus());
    const closeForEvent = (event) => {
      if (event.type === "keydown") {
        if (event.key !== "Escape") return;
        if (submenuOpen) {
          setSubmenuOpen(false);
          requestAnimationFrame(() => mainRef.current?.querySelector("button")?.focus());
          return;
        }
      }
      if (
        event.type === "pointerdown"
        && (mainRef.current?.contains(event.target) || submenuRef.current?.contains(event.target))
      ) return;
      onClose();
    };
    const closeForOutsideScroll = (event) => {
      if (submenuRef.current?.contains(event.target)) return;
      onClose();
    };
    document.addEventListener("pointerdown", closeForEvent);
    document.addEventListener("keydown", closeForEvent);
    window.addEventListener("scroll", closeForOutsideScroll, true);
    window.addEventListener("resize", onClose);
    return () => {
      cancelAnimationFrame(focusFrame);
      document.removeEventListener("pointerdown", closeForEvent);
      document.removeEventListener("keydown", closeForEvent);
      window.removeEventListener("scroll", closeForOutsideScroll, true);
      window.removeEventListener("resize", onClose);
    };
  }, [onClose, submenuOpen]);

  const openSubmenu = async () => {
    setSubmenuOpen(true);
    if (loadedRef.current || loading) return;
    loadedRef.current = true;
    setLoading(true);
    setError("");
    try {
      const body = await fetchCardFunctionTags(card.id);
      const availableTags = body.tags || [];
      setTags(availableTags);
      if (!availableTags.length) setError(t("noFunctionTagsForCard"));
    } catch (requestError) {
      loadedRef.current = false;
      setError(requestError.message || t("similarTagsLoadFailed"));
    } finally {
      setLoading(false);
    }
  };

  const toggleTag = (tag) => {
    setSelectedTags((previous) => {
      const next = new Set(previous);
      if (next.has(tag)) next.delete(tag);
      else next.add(tag);
      return next;
    });
  };

  const submit = () => {
    if (!selectedTags.size) return;
    onSearch(card, [...selectedTags]);
    onClose();
  };

  return createPortal(
    <>
      <div
        ref={mainRef}
        className="card-action-menu"
        role="menu"
        style={{ left: position.left, top: position.top }}
      >
        <button
          type="button"
          role="menuitem"
          aria-haspopup="menu"
          aria-expanded={submenuOpen}
          onMouseEnter={openSubmenu}
          onClick={openSubmenu}
        >
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-4-4" />
            <path d="M8 11h6M11 8v6" />
          </svg>
          <span>{t("findSimilarCards")}</span>
          <svg className="card-action-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m9 18 6-6-6-6" />
          </svg>
        </button>
      </div>

      {submenuOpen && (
        <div
          ref={submenuRef}
          className="card-tag-submenu"
          role="menu"
          aria-label={t("chooseSimilarTags")}
          style={{ left: submenuPosition.left, top: submenuPosition.top }}
          onWheel={(event) => event.stopPropagation()}
        >
          <div className="card-tag-submenu-header">
            <div>
              <button type="button" onClick={() => setSubmenuOpen(false)} aria-label={t("backToCardActions")}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6" /></svg>
              </button>
              <strong>{t("chooseSimilarTags")}</strong>
            </div>
            <span title={card.name}>{card.name}</span>
          </div>

          <div className="card-tag-options">
            {loading && <div className="card-tag-menu-status"><span className="loading-spinner" />{t("loadingTags")}</div>}
            {!loading && error && (
              <div className="card-tag-menu-status card-tag-menu-error">
                <span>{error}</span>
                {tags.length === 0 && loadedRef.current === false && (
                  <button type="button" onClick={openSubmenu}>{t("retry")}</button>
                )}
              </div>
            )}
            {!loading && !error && tags.map((item) => (
              <label key={item.tag} className="card-tag-option" role="menuitemcheckbox" aria-checked={selectedTags.has(item.tag)}>
                <input
                  type="checkbox"
                  checked={selectedTags.has(item.tag)}
                  onChange={() => toggleTag(item.tag)}
                />
                <span>
                  <strong>{item.label || item.tag}</strong>
                  {item.label && item.label !== item.tag && <small>{item.tag}</small>}
                </span>
              </label>
            ))}
          </div>

          <div className="card-tag-submenu-footer">
            <div className="card-tag-selection-tools">
              <span>{t("tagsSelected").replace("{count}", selectedTags.size)}</span>
              {tags.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedTags(selectedTags.size === tags.length ? new Set() : new Set(tags.map((item) => item.tag)))}
                >
                  {selectedTags.size === tags.length ? t("clearTagSelection") : t("selectAllTags")}
                </button>
              )}
            </div>
            <button type="button" className="card-tag-search-btn" onClick={submit} disabled={!selectedTags.size}>
              {t("searchSelectedTags")}
            </button>
          </div>
        </div>
      )}
    </>,
    document.body,
  );
}

export default CardActionMenu;
