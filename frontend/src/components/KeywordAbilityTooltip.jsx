import { useCallback, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { getKeywordAbilityIconClass } from "../utils/keywordAbilityIcons.js";

const VIEWPORT_MARGIN = 12;
const CARD_GAP = 12;
const MAX_WIDTH = 320;

function KeywordAbilityTooltip({ anchorRef, abilities, language }) {
  const tooltipRef = useRef(null);
  const [position, setPosition] = useState(null);

  const updatePosition = useCallback(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;
    const rect = anchor.getBoundingClientRect();
    const width = Math.min(MAX_WIDTH, window.innerWidth - VIEWPORT_MARGIN * 2);
    const tooltipHeight = tooltipRef.current?.offsetHeight || 180;
    const fitsRight = rect.right + CARD_GAP + width <= window.innerWidth - VIEWPORT_MARGIN;
    const fitsLeft = rect.left - CARD_GAP - width >= VIEWPORT_MARGIN;
    let left;
    if (fitsRight || (!fitsLeft && window.innerWidth - rect.right >= rect.left)) {
      left = Math.min(rect.right + CARD_GAP, window.innerWidth - width - VIEWPORT_MARGIN);
    } else {
      left = Math.max(VIEWPORT_MARGIN, rect.left - width - CARD_GAP);
    }
    const top = Math.min(
      Math.max(VIEWPORT_MARGIN, rect.top),
      Math.max(VIEWPORT_MARGIN, window.innerHeight - tooltipHeight - VIEWPORT_MARGIN)
    );
    setPosition({ left, top, width });
  }, [anchorRef]);

  useLayoutEffect(() => {
    updatePosition();
    const frame = requestAnimationFrame(updatePosition);
    window.addEventListener("resize", updatePosition);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", updatePosition);
    };
  }, [abilities, language, updatePosition]);

  if (!abilities.length) return null;
  return createPortal(
    <aside
      ref={tooltipRef}
      className="keyword-ability-tooltip"
      role="tooltip"
      style={position || { visibility: "hidden" }}
    >
      <div className="keyword-ability-tooltip-list">
        {abilities.map((ability) => {
          const displayName = language === "zh" ? (ability.name_zh || ability.name) : ability.name;
          const description = language === "zh"
            ? (ability.description_zh || ability.description_en)
            : ability.description_en;
          return (
            <section key={ability.name.toLowerCase()} className="keyword-ability-tooltip-item">
              <h4>
                <span
                  className={`keyword-ability-tooltip-icon ${getKeywordAbilityIconClass(ability.name)}`}
                  aria-hidden="true"
                />
                <span>{displayName}</span>
              </h4>
              <p>{description}</p>
            </section>
          );
        })}
      </div>
    </aside>,
    document.body
  );
}

export default KeywordAbilityTooltip;
