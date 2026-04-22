import { useEffect, useState } from "react";
import { fetchAdminStats } from "../../../api/admin.js";
import StatCard from "../components/StatCard.jsx";
import { formatNumber } from "../utils.js";

export default function DashboardSection() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAdminStats()
      .then((res) => res.json())
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading"><div className="loading-spinner" /></div>;
  if (!stats) return <p className="admin-empty">加载统计数据失败</p>;

  const { database: db, searches, popular_queries } = stats;

  return (
    <>
      <h2 className="admin-title">数据概览</h2>

      {/* Database overview cards */}
      <div className="admin-stats-grid">
        <StatCard label="卡牌总数" value={formatNumber(db.total_cards)} />
        <StatCard label="关键词异能" value={formatNumber(db.total_abilities)} />
        <StatCard
          label="缺少 Embedding"
          value={db.cards_missing_embeddings + db.abilities_missing_embeddings}
          variant={db.cards_missing_embeddings + db.abilities_missing_embeddings > 0 ? "warn" : "ok"}
          detail={`卡牌 ${db.cards_missing_embeddings} / 异能 ${db.abilities_missing_embeddings}`}
        />
        <StatCard
          label="最后同步"
          value={db.last_sync_at ? new Date(db.last_sync_at).toLocaleDateString("zh-CN") : "从未"}
          detail={db.last_sync_at ? new Date(db.last_sync_at).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }) : ""}
        />
      </div>

      {/* Search stats */}
      <h3 className="admin-section-title">搜索统计</h3>
      <div className="admin-stats-grid">
        <StatCard label="今日搜索" value={formatNumber(searches.today.count)} detail={`Token: ${formatNumber(searches.today.tokens)}`} />
        <StatCard label="近 7 天" value={formatNumber(searches.week.count)} detail={`Token: ${formatNumber(searches.week.tokens)}`} />
        <StatCard label="近 30 天" value={formatNumber(searches.month.count)} detail={`Token: ${formatNumber(searches.month.tokens)}`} />
        <StatCard
          label="7 天用户分布"
          value={searches.registered_7d + searches.anonymous_7d}
          detail={`登录 ${searches.registered_7d} / 匿名 ${searches.anonymous_7d}`}
        />
      </div>

      {/* Popular queries */}
      <h3 className="admin-section-title">热门搜索（近 7 天）</h3>
      {popular_queries.length === 0 ? (
        <p className="admin-empty">暂无搜索记录</p>
      ) : (
        <div className="admin-popular-list">
          {popular_queries.map((q, i) => (
            <div key={i} className="admin-popular-item">
              <span className="admin-popular-rank">#{i + 1}</span>
              <span className="admin-popular-query">{q.query}</span>
              <span className="admin-popular-count">{q.count} 次</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
