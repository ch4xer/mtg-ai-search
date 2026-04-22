const COLOR_HEX = { W: "#d5c67a", U: "#0e68ab", B: "#3d3a3a", R: "#d3202a", G: "#00733e" };
const COLORS = ["W", "U", "B", "R", "G"];

function AnalysisTextCard({ deck, language, isOwner, analyzing, onAnalyze, formatRelativeTime, t }) {
  return (
    <div className={`analysis-card analyze-card ${deck?.analysis ? "has-analysis" : ""}`}>
      {deck?.analysis ? (
        <>
          {isOwner && (
            <div className="analyze-header">
              <button className="analyze-btn analyze-btn-compact" onClick={onAnalyze} disabled={analyzing}>
                {analyzing ? (
                  <><span className="analyze-spinner" aria-hidden="true" /> {t("analyzing")}</>
                ) : (
                  <><span className="analyze-sparkle" aria-hidden="true">✦</span> {t("reanalyzeDeck")}</>
                )}
              </button>
              <div className="analyze-meta">
                <span>{t("analysisLastUpdated")} {formatRelativeTime(deck.analysis.updated_at)}</span>
                {new Date(deck.updated_at).getTime() > new Date(deck.analysis.updated_at).getTime() && (
                  <span className="analyze-stale" title={t("analysisDeckChanged")}>● {t("analysisDeckChanged")}</span>
                )}
              </div>
            </div>
          )}
          {analyzing ? (
            <div className="analyze-skeleton">
              <div className="analyze-skeleton-block" />
              <div className="analyze-skeleton-block" />
              <div className="analyze-skeleton-block" />
            </div>
          ) : (() => {
            const block = deck.analysis[language] || deck.analysis.zh || deck.analysis.en;
            if (!block) return null;
            return (
              <>
                <p className="analyze-summary">{block.summary}</p>
                <h4 className="analyze-subtitle">{t("analysisPlaystyle")}</h4>
                <p className="analyze-text">{block.playstyle}</p>
                <h4 className="analyze-subtitle">{t("analysisWeaknesses")}</h4>
                <p className="analyze-text">{block.weaknesses}</p>
              </>
            );
          })()}
        </>
      ) : !isOwner ? (
        <p className="analyze-text" style={{ textAlign: "center", color: "var(--text-muted)" }}>
          {t("noAnalysisYet")}
        </p>
      ) : (
        <button className="analyze-btn analyze-btn-primary" onClick={onAnalyze} disabled={analyzing}>
          {analyzing ? (
            <><span className="analyze-spinner" aria-hidden="true" /> {t("analyzing")}</>
          ) : (
            <><span className="analyze-sparkle" aria-hidden="true">✦</span> {t("analyzeDeck")}</>
          )}
        </button>
      )}
    </div>
  );
}

function ManaCurve({ deckAnalysis, t }) {
  return (
    <div className="analysis-card">
      <h3 className="analysis-title">{t("manaCurve")}</h3>
      <div className="analysis-mana-curve">
        {deckAnalysis.cmcBuckets.map((count, i) => (
          <div key={i} className="mana-curve-col">
            <span className="mana-curve-value">{count || ""}</span>
            <div className="mana-curve-bar-wrapper">
              <div className="mana-curve-bar" style={{ height: `${(count / deckAnalysis.cmcMax) * 100}%` }} />
            </div>
            <span className="mana-curve-label">{i < 7 ? i : "7+"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ColorDistribution({ deckAnalysis, t }) {
  const total = deckAnalysis.totalColorCards;
  let cumulative = 0;
  const conicGradient = COLORS
    .map((color) => {
      const pct = (deckAnalysis.colorCounts[color] / total) * 100;
      const start = cumulative;
      cumulative += pct;
      return { color, pct, start, hex: COLOR_HEX[color] };
    })
    .filter((slice) => slice.pct > 0)
    .map((slice) => `${slice.hex} ${slice.start}% ${slice.start + slice.pct}%`)
    .join(", ");

  return (
    <div className="analysis-card">
      <h3 className="analysis-title">{t("colorDistribution")}</h3>
      <div className="analysis-pie-container">
        <div className="analysis-pie" style={{ background: conicGradient ? `conic-gradient(${conicGradient})` : "var(--bg-secondary)" }} />
        <div className="analysis-pie-legend">
          {COLORS.map((color) => {
            const count = deckAnalysis.colorCounts[color];
            if (count === 0) return null;
            return (
              <div key={color} className="pie-legend-item">
                <span className={`analysis-color-dot mana-${color}`} />
                <span className="pie-legend-label">{deckAnalysis.colorLabels[color]}</span>
                <span className="pie-legend-value">{count}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CardTypeDistribution({ groupedCards, deckAnalysis, t }) {
  return (
    <div className="analysis-card">
      <h3 className="analysis-title">{t("cardTypes")}</h3>
      <div className="analysis-bars">
        {groupedCards.map((group) => (
          <div key={group.type} className="analysis-bar-row">
            <span className="analysis-bar-label">{group.label}</span>
            <div className="analysis-bar-track">
              <div className="analysis-bar-fill type-bar" style={{ width: `${(group.count / deckAnalysis.totalAnalyzedCards) * 100}%` }} />
            </div>
            <span className="analysis-bar-value">{group.count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RarityDistribution({ deckAnalysis, t }) {
  return (
    <div className="analysis-card">
      <h3 className="analysis-title">{t("rarityDistribution")}</h3>
      <div className="analysis-bars">
        {deckAnalysis.rarityOrder.map((rarity) => {
          const count = deckAnalysis.rarityCounts[rarity] || 0;
          return (
            <div key={rarity} className="analysis-bar-row">
              <span className="analysis-bar-label">{deckAnalysis.rarityLabels[rarity]}</span>
              <div className="analysis-bar-track">
                <div className={`analysis-bar-fill rarity-bar-${rarity}`} style={{ width: `${(count / deckAnalysis.totalRarityCards) * 100}%` }} />
              </div>
              <span className="analysis-bar-value">{count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function DeckAnalysisPanel({ deck, deckAnalysis, groupedCards, language, isOwner, analyzing, onAnalyze, formatRelativeTime, t }) {
  if (!deckAnalysis) return null;

  return (
    <aside className="deck-analysis">
      <AnalysisTextCard
        deck={deck}
        language={language}
        isOwner={isOwner}
        analyzing={analyzing}
        onAnalyze={onAnalyze}
        formatRelativeTime={formatRelativeTime}
        t={t}
      />
      <ManaCurve deckAnalysis={deckAnalysis} t={t} />
      <ColorDistribution deckAnalysis={deckAnalysis} t={t} />
      <CardTypeDistribution groupedCards={groupedCards} deckAnalysis={deckAnalysis} t={t} />
      <RarityDistribution deckAnalysis={deckAnalysis} t={t} />
    </aside>
  );
}
