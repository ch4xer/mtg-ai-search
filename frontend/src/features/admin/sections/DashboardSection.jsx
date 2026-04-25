import { useEffect, useState } from "react";
import { fetchAdminStats } from "../../../api/admin.js";
import StatCard from "../components/StatCard.jsx";
import { formatNumber } from "../utils.js";
import { useLanguage } from "../../../contexts/LanguageContext.jsx";

export default function DashboardSection() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const { language, t } = useLanguage();
  const dateLocale = language === "zh" ? "zh-CN" : "en-US";

  useEffect(() => {
    fetchAdminStats()
      .then((res) => res.json())
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading"><div className="loading-spinner" /></div>;
  if (!stats) return <p className="admin-empty">{t("adminStatsLoadFailed")}</p>;

  const { database: db, searches, popular_queries } = stats;
  const missingTotal = db.cards_missing_embeddings + db.abilities_missing_embeddings;

  return (
    <>
      <h2 className="admin-title">{t("adminTitleDashboard")}</h2>

      {/* Database overview cards */}
      <div className="admin-stats-grid">
        <StatCard label={t("adminStatTotalCards")} value={formatNumber(db.total_cards)} />
        <StatCard label={t("adminStatKeywordAbilities")} value={formatNumber(db.total_abilities)} />
        <StatCard
          label={t("adminStatMissingEmbeddings")}
          value={missingTotal}
          variant={missingTotal > 0 ? "warn" : "ok"}
          detail={t("adminStatMissingEmbeddingsDetail")
            .replace("{cards}", db.cards_missing_embeddings)
            .replace("{abilities}", db.abilities_missing_embeddings)}
        />
        <StatCard
          label={t("adminStatLastSync")}
          value={db.last_sync_at ? new Date(db.last_sync_at).toLocaleDateString(dateLocale) : t("adminStatNever")}
          detail={db.last_sync_at ? new Date(db.last_sync_at).toLocaleTimeString(dateLocale, { hour: "2-digit", minute: "2-digit" }) : ""}
        />
      </div>

      {/* Search stats */}
      <h3 className="admin-section-title">{t("adminSectionSearchStats")}</h3>
      <div className="admin-stats-grid">
        <StatCard label={t("adminStatSearchesToday")} value={formatNumber(searches.today.count)} detail={`${t("adminStatTokens")}: ${formatNumber(searches.today.tokens)}`} />
        <StatCard label={t("adminStatSearchesWeek")} value={formatNumber(searches.week.count)} detail={`${t("adminStatTokens")}: ${formatNumber(searches.week.tokens)}`} />
        <StatCard label={t("adminStatSearchesMonth")} value={formatNumber(searches.month.count)} detail={`${t("adminStatTokens")}: ${formatNumber(searches.month.tokens)}`} />
        <StatCard
          label={t("adminStatUserMix7d")}
          value={searches.registered_7d + searches.anonymous_7d}
          detail={t("adminStatUserMixDetail")
            .replace("{registered}", searches.registered_7d)
            .replace("{anonymous}", searches.anonymous_7d)}
        />
      </div>

      {/* Popular queries */}
      <h3 className="admin-section-title">{t("adminSectionPopularQueries")}</h3>
      {popular_queries.length === 0 ? (
        <p className="admin-empty">{t("adminPopularEmpty")}</p>
      ) : (
        <div className="admin-popular-list">
          {popular_queries.map((q, i) => (
            <div key={i} className="admin-popular-item">
              <span className="admin-popular-rank">#{i + 1}</span>
              <span className="admin-popular-query">{q.query}</span>
              <span className="admin-popular-count">{t("adminQueryCount").replace("{n}", q.count)}</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
