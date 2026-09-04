import { useCallback, useEffect, useRef, useState } from "react";
import CardItem from "./CardItem.jsx";
import { useKeywordAbilities } from "../hooks/useKeywordAbilities.js";

const TOOLTIP_SCROLL_COOLDOWN_MS = 180;

function CardGrid({ cards, imageMode, decks, onFindSimilar }) {
  const hasKeywords = cards.some((card) => card.keywords?.length > 0);
  const abilityCatalog = useKeywordAbilities(hasKeywords);
  const [activeTooltipKey, setActiveTooltipKey] = useState(null);
  const suppressTooltipUntilRef = useRef(0);

  const dismissTooltipForViewportChange = useCallback(() => {
    suppressTooltipUntilRef.current = Date.now() + TOOLTIP_SCROLL_COOLDOWN_MS;
    setActiveTooltipKey(null);
  }, []);

  useEffect(() => {
    const passiveCapture = { capture: true, passive: true };
    window.addEventListener("scroll", dismissTooltipForViewportChange, passiveCapture);
    window.addEventListener("wheel", dismissTooltipForViewportChange, passiveCapture);
    window.addEventListener("touchmove", dismissTooltipForViewportChange, passiveCapture);
    window.addEventListener("resize", dismissTooltipForViewportChange);
    return () => {
      window.removeEventListener("scroll", dismissTooltipForViewportChange, passiveCapture);
      window.removeEventListener("wheel", dismissTooltipForViewportChange, passiveCapture);
      window.removeEventListener("touchmove", dismissTooltipForViewportChange, passiveCapture);
      window.removeEventListener("resize", dismissTooltipForViewportChange);
    };
  }, [dismissTooltipForViewportChange]);

  const activateTooltip = useCallback((key) => {
    if (Date.now() < suppressTooltipUntilRef.current) return;
    setActiveTooltipKey((current) => current === key ? current : key);
  }, []);

  const deactivateTooltip = useCallback((key) => {
    setActiveTooltipKey((current) => current === key ? null : current);
  }, []);

  return (
    <div className="card-grid">
      {cards.map((card, index) => {
        const cardKey = `${card.id || card.name}-${card.print_id || "default"}-${index}`;
        return (
          <CardItem
            key={cardKey}
            card={card}
            imageMode={imageMode}
            decks={decks}
            abilityCatalog={abilityCatalog}
            tooltipActive={activeTooltipKey === cardKey}
            onTooltipActivate={() => activateTooltip(cardKey)}
            onTooltipDeactivate={() => deactivateTooltip(cardKey)}
            onFindSimilar={onFindSimilar}
          />
        );
      })}
    </div>
  );
}

export default CardGrid;
