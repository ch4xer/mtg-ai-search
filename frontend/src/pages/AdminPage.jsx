import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiFetch } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";

function formatNumber(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

const NAV_ITEMS = [
  { key: "dashboard", label: "数据概览", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" },
  { key: "users", label: "用户管理", icon: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197" },
  { key: "database", label: "数据库维护", icon: "M4 7v10c0 2 8 2 8 2s8 0 8-2V7M4 7c0 2 8 2 8 2s8 0 8-2M4 7c0-2 8-2 8-2s8 0 8 2" },
  { key: "settings", label: "系统设置", icon: "M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" },
];

function AdminPage() {
  const { section } = useParams();
  const navigate = useNavigate();
  const validSections = ["dashboard", "users", "database", "settings"];
  const activeSection = validSections.includes(section) ? section : "dashboard";

  const handleSectionChange = (newSection) => {
    navigate(`/admin/${newSection}`);
  };

  return (
    <div className="admin-layout">
      <aside className="admin-sidebar">
        <nav className="admin-sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              className={`admin-sidebar-item ${activeSection === item.key ? "active" : ""}`}
              onClick={() => handleSectionChange(item.key)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d={item.icon} />
              </svg>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>
      <main className="admin-content">
        {activeSection === "dashboard" && <DashboardSection />}
        {activeSection === "users" && <UsersSection />}
        {activeSection === "database" && <DatabaseSection />}
        {activeSection === "settings" && <SettingsSection />}
      </main>
    </div>
  );
}


/* ── Dashboard Section ─────────────────────────────────────────── */

function DashboardSection() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/admin/stats")
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

function StatCard({ label, value, detail, variant }) {
  return (
    <div className={`admin-stat-card ${variant === "warn" ? "warn" : ""} ${variant === "ok" ? "ok" : ""}`}>
      <div className="admin-stat-card-value">{value}</div>
      <div className="admin-stat-card-label">{label}</div>
      {detail && <div className="admin-stat-card-detail">{detail}</div>}
    </div>
  );
}


/* ── Users Section ─────────────────────────────────────────────── */

function UsersSection() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const [pageSize] = useState(20);
  const { showToast } = useToast();
  const searchTimerRef = useRef(null);

  const totalPages = Math.max(1, Math.ceil(totalUsers / pageSize));

  const fetchUsers = async (query = searchQuery, page = currentPage) => {
    try {
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (query.trim()) params.set("q", query.trim());
      const res = await apiFetch(`/api/admin/users?${params}`);
      if (res.ok) {
        const data = await res.json();
        if (data.users) {
          setUsers(data.users);
          setTotalUsers(data.total);
        } else if (Array.isArray(data)) {
          setUsers(data);
          setTotalUsers(data.length);
        }
      }
    } catch {
      showToast("加载用户列表失败", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchUsers("", 1); }, []);

  const handleSearchChange = (e) => {
    const value = e.target.value;
    setSearchQuery(value);
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      setCurrentPage(1);
      fetchUsers(value, 1);
    }, 300);
  };

  const handlePageChange = (page) => {
    setCurrentPage(page);
    fetchUsers(searchQuery, page);
  };

  const handleToggleRole = async (userId, currentRole) => {
    const newRole = currentRole === "admin" ? "user" : "admin";
    try {
      const res = await apiFetch(`/api/admin/users/${userId}/role`, {
        method: "PUT",
        body: { role: newRole },
      });
      if (res.ok) {
        setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u)));
        showToast(`已将用户角色更改为 ${newRole}`);
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "操作失败", "error");
      }
    } catch { showToast("操作失败", "error"); }
  };

  const handleDelete = async (userId, username) => {
    if (!confirm(`确定要删除用户「${username}」吗？该用户的所有卡组也将被删除。`)) return;
    try {
      const res = await apiFetch(`/api/admin/users/${userId}`, { method: "DELETE" });
      if (res.ok) {
        setUsers((prev) => prev.filter((u) => u.id !== userId));
        setTotalUsers((prev) => prev - 1);
        showToast(`用户「${username}」已删除`);
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "删除失败", "error");
      }
    } catch { showToast("删除失败", "error"); }
  };

  if (loading) return <div className="loading"><div className="loading-spinner" /></div>;

  return (
    <>
      <h2 className="admin-title">用户管理</h2>

      <div className="admin-search-bar">
        <input
          type="text"
          className="admin-search-input"
          placeholder="搜索用户名或邮箱..."
          value={searchQuery}
          onChange={handleSearchChange}
        />
        <span className="admin-user-count">共 {totalUsers} 个用户</span>
      </div>

      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>角色</th>
              <th>注册时间</th>
              <th>最近活动</th>
              <th className="admin-stat-group" colSpan="3">搜索次数</th>
              <th className="admin-stat-group" colSpan="3">Token 消耗</th>
              <th>操作</th>
            </tr>
            <tr className="admin-subheader">
              <th colSpan="4"></th>
              <th className="admin-stat-col">总计</th>
              <th className="admin-stat-col">7天</th>
              <th className="admin-stat-col">3小时</th>
              <th className="admin-stat-col">总计</th>
              <th className="admin-stat-col">7天</th>
              <th className="admin-stat-col">3小时</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 ? (
              <tr>
                <td colSpan="11" style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                  {searchQuery ? "没有找到匹配的用户" : "暂无用户"}
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td><span className={`role-badge role-${u.role}`}>{u.role}</span></td>
                  <td>{new Date(u.created_at).toLocaleDateString("zh-CN")}</td>
                  <td>{u.last_active_at ? new Date(u.last_active_at).toLocaleDateString("zh-CN") : "—"}</td>
                  <td className="admin-stat-cell">{formatNumber(u.total_searches)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.searches_7d)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.searches_3h)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.total_tokens)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.tokens_7d)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.tokens_3h)}</td>
                  <td className="admin-actions-cell">
                    <button className="btn-secondary" onClick={() => handleToggleRole(u.id, u.role)}>
                      {u.role === "admin" ? "降为用户" : "升为管理员"}
                    </button>
                    <button className="btn-danger" onClick={() => handleDelete(u.id, u.username)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="admin-pagination">
          <button className="admin-page-btn" disabled={currentPage <= 1} onClick={() => handlePageChange(currentPage - 1)}>
            &laquo; 上一页
          </button>
          {Array.from({ length: totalPages }, (_, i) => i + 1)
            .filter((p) => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 2)
            .reduce((acc, p, i, arr) => {
              if (i > 0 && p - arr[i - 1] > 1) acc.push("...");
              acc.push(p);
              return acc;
            }, [])
            .map((item, idx) =>
              item === "..." ? (
                <span key={`ellipsis-${idx}`} className="admin-page-ellipsis">...</span>
              ) : (
                <button key={item} className={`admin-page-btn ${item === currentPage ? "active" : ""}`} onClick={() => handlePageChange(item)}>
                  {item}
                </button>
              )
            )}
          <button className="admin-page-btn" disabled={currentPage >= totalPages} onClick={() => handlePageChange(currentPage + 1)}>
            下一页 &raquo;
          </button>
        </div>
      )}
    </>
  );
}


/* ── Database Section ──────────────────────────────────────────── */

function DatabaseSection() {
  const [taskStatus, setTaskStatus] = useState({
    reseed: { status: "idle" },
    reembed: { status: "idle" },
    seed_abilities: { status: "idle" },
  });
  const [syncLogs, setSyncLogs] = useState([]);
  const { showToast } = useToast();
  const pollRef = useRef(null);

  const fetchSyncLogs = async () => {
    try {
      const res = await apiFetch("/api/admin/sync-logs");
      if (res.ok) setSyncLogs(await res.json());
    } catch { /* ignore */ }
  };

  const fetchTaskStatus = async () => {
    try {
      const res = await apiFetch("/api/admin/task-status");
      if (res.ok) {
        const data = await res.json();
        setTaskStatus(data);
        return data;
      }
    } catch { /* ignore */ }
    return null;
  };

  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      const data = await fetchTaskStatus();
      if (!data) return;
      const anyRunning = Object.values(data).some((t) => t.status === "running");
      if (!anyRunning) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        fetchSyncLogs();
      }
    }, 3000);
  };

  useEffect(() => {
    fetchSyncLogs();
    fetchTaskStatus().then((data) => {
      if (data && Object.values(data).some((t) => t.status === "running")) {
        startPolling();
      }
    });
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const runAction = async (url, successMsg) => {
    try {
      const res = await apiFetch(url, { method: "POST" });
      if (res.ok) {
        showToast(successMsg);
        await fetchTaskStatus();
        startPolling();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "操作失败", "error");
      }
    } catch { showToast("操作失败", "error"); }
  };

  const handleReembed = async () => {
    if (!confirm("确定要重新生成所有 embedding 吗？过程可能需要较长时间。")) return;
    runAction("/api/admin/reembed", "已开始重新生成 embedding");
  };
  const handleSeedAbilities = () => {
    if (!confirm("强制重新生成异能数据库：清空 keyword_abilities 表，从规则 702 + Scryfall catalog 重新导入，并调用 LLM 为未覆盖的关键词生成描述。耗时较长。")) return;
    runAction("/api/admin/seed-abilities", "已开始强制重建异能数据库");
  };
  const handleSyncAbilities = () => runAction("/api/admin/sync-abilities", "已开始增量更新异能数据库");
  const handleSync = () => runAction("/api/admin/sync", "已开始增量同步");
  const handleForceSync = () => runAction("/api/admin/sync?force=true", "已开始强制刷新（更新数据 + Embedding）");
  const handleForceSyncDataOnly = () => runAction("/api/admin/sync?force=true&skip_embeddings=true", "已开始仅更新数据");

  const anyRunning = Object.values(taskStatus).some((t) => t.status === "running");

  return (
    <>
      <h2 className="admin-title">数据库维护</h2>
      <div className="admin-db-actions">
        <TaskCard
          title="重新生成 Embedding"
          desc="清除所有现有 embedding 并重新生成。卡牌数据本身不会改变。适用于更换了 embedding 模型后使用。"
          status={taskStatus.reembed}
          disabled={anyRunning}
          onRun={handleReembed}
          btnText="重新生成 Embedding"
        />
        <TaskCard
          title="强制重新生成异能数据库"
          desc="清空关键词表，从官方规则 702 节重新导入，并针对 Scryfall catalog 中未覆盖的关键词抽取 10 张示例卡，用 LLM 生成一句话描述，最后统一生成 embedding。耗时较长。"
          status={taskStatus.seed_abilities}
          disabled={anyRunning}
          onRun={handleSeedAbilities}
          btnText="强制重建"
        />
        <TaskCard
          title="增量更新异能数据库"
          desc="只扫描 Scryfall catalog 中现有关键词表还没收录的条目，用 LLM 生成描述并补充 embedding。已有条目不会被改动，耗时远短于强制重建。"
          status={taskStatus.seed_abilities}
          disabled={anyRunning}
          onRun={handleSyncAbilities}
          btnText="增量更新"
        />
      </div>

      {/* Sync logs */}
      <div className="admin-sync-section">
        <div className="admin-sync-header">
          <h3 className="admin-section-title">每日同步记录</h3>
          <div className="admin-sync-buttons">
            <button className="btn-secondary" onClick={handleForceSyncDataOnly} disabled={anyRunning}>仅更新数据</button>
            <button className="btn-secondary" onClick={handleForceSync} disabled={anyRunning}>强制刷新</button>
            <button className="btn-accent" onClick={handleSync} disabled={anyRunning}>手动同步</button>
          </div>
        </div>
        <p className="admin-db-card-desc" style={{ marginBottom: "1rem" }}>
          「手动同步」检查 Scryfall 是否有更新，如有则增量同步。「强制刷新」绕过检查，更新所有数据并生成 embedding。「仅更新数据」绕过检查，更新印刷版本数据（flavor_text、图片等），不重新生成 embedding。
        </p>
        {syncLogs.length === 0 ? (
          <p className="admin-empty">暂无同步记录</p>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th style={{ width: "40px" }}></th>
                  <th>时间</th>
                  <th>状态</th>
                  <th>新增卡牌</th>
                  <th>更新卡牌</th>
                  <th>详情</th>
                </tr>
              </thead>
              <tbody>
                {syncLogs.map((log) => (
                  <SyncLogRow key={log.id} log={log} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

/* ── Settings Section ─────────────────────────────────────────── */

function SettingsSection() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [anonLimit, setAnonLimit] = useState("");
  const [userLimit, setUserLimit] = useState("");
  const { showToast } = useToast();

  useEffect(() => {
    apiFetch("/api/admin/settings")
      .then((res) => res.json())
      .then((data) => {
        setSettings(data);
        setAnonLimit(String(data.anon_hourly_limit));
        setUserLimit(String(data.user_hourly_limit));
      })
      .catch(() => showToast("加载设置失败", "error"))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    const anon = parseInt(anonLimit, 10);
    const user = parseInt(userLimit, 10);
    if (isNaN(anon) || anon < 0 || isNaN(user) || user < 0) {
      showToast("请输入有效的非负整数", "error");
      return;
    }
    setSaving(true);
    try {
      const res = await apiFetch("/api/admin/settings", {
        method: "PUT",
        body: { anon_hourly_limit: anon, user_hourly_limit: user },
      });
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
        showToast("设置已保存");
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "保存失败", "error");
      }
    } catch {
      showToast("保存失败", "error");
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = settings && (
    String(settings.anon_hourly_limit) !== anonLimit ||
    String(settings.user_hourly_limit) !== userLimit
  );

  if (loading) return <div className="loading"><div className="loading-spinner" /></div>;

  return (
    <>
      <h2 className="admin-title">系统设置</h2>

      <div className="admin-settings-card">
        <h3 className="admin-settings-card-title">搜索频率限制</h3>
        <p className="admin-db-card-desc">
          限制用户每小时的 AI 搜索次数。管理员不受此限制。设置为 0 表示禁止搜索。
        </p>

        <div className="admin-settings-form">
          <div className="admin-settings-field">
            <label className="admin-settings-label">匿名用户（每小时）</label>
            <div className="admin-settings-input-row">
              <input
                type="number"
                className="admin-settings-input"
                value={anonLimit}
                onChange={(e) => setAnonLimit(e.target.value)}
                min="0"
                step="1"
              />
              <span className="admin-settings-unit">次/小时</span>
            </div>
            <span className="admin-settings-hint">按 IP 地址限制未登录用户的搜索频率</span>
          </div>

          <div className="admin-settings-field">
            <label className="admin-settings-label">注册用户（每小时）</label>
            <div className="admin-settings-input-row">
              <input
                type="number"
                className="admin-settings-input"
                value={userLimit}
                onChange={(e) => setUserLimit(e.target.value)}
                min="0"
                step="1"
              />
              <span className="admin-settings-unit">次/小时</span>
            </div>
            <span className="admin-settings-hint">按用户账号限制已登录用户的搜索频率</span>
          </div>
        </div>

        <div className="admin-settings-actions">
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving || !hasChanges}
          >
            {saving ? "保存中..." : "保存设置"}
          </button>
        </div>
      </div>
    </>
  );
}


function TaskCard({ title, desc, status, disabled, onRun, btnText }) {
  return (
    <div className="admin-db-card">
      <div className="admin-db-card-header">
        <h3>{title}</h3>
        <StatusBadge status={status?.status} />
      </div>
      <p className="admin-db-card-desc">{desc}</p>
      {status?.status === "running" && (
        <div className="admin-task-progress">
          <div className="loading-spinner-small" />
          <span>{status.message}</span>
        </div>
      )}
      {status?.status === "done" && <p className="admin-task-done">{status.message}</p>}
      {status?.status === "error" && <p className="admin-task-error">{status.message}</p>}
      <button className="btn-primary" onClick={onRun} disabled={disabled}>{btnText}</button>
    </div>
  );
}

function StatusBadge({ status }) {
  if (!status || status === "idle") return null;
  const labels = { running: "运行中", done: "已完成", error: "失败" };
  return <span className={`admin-task-badge admin-task-badge-${status}`}>{labels[status]}</span>;
}

function SyncStatusBadge({ status }) {
  const labels = { running: "运行中", done: "完成", error: "失败", skipped: "跳过" };
  const className = status === "skipped" ? "idle" : status;
  return <span className={`admin-task-badge admin-task-badge-${className}`}>{labels[status] || status}</span>;
}

function SyncLogRow({ log }) {
  const [expanded, setExpanded] = useState(false);
  const hasLongMessage = log.message && log.message.length > 50;

  return (
    <>
      <tr className="admin-sync-row" onClick={() => hasLongMessage && setExpanded(!expanded)}>
        <td>
          {hasLongMessage && (
            <button className="admin-expand-btn" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                {expanded ? (
                  <path d="M18 15l-6-6-6 6" />
                ) : (
                  <path d="M6 9l6 6 6-6" />
                )}
              </svg>
            </button>
          )}
        </td>
        <td>{new Date(log.started_at).toLocaleString("zh-CN")}</td>
        <td><SyncStatusBadge status={log.status} /></td>
        <td>{log.new_cards}</td>
        <td>{log.updated_cards}</td>
        <td className="admin-sync-message">
          {hasLongMessage ? (
            expanded ? log.message : log.message.slice(0, 50) + "..."
          ) : (
            log.message || "—"
          )}
        </td>
      </tr>
      {expanded && hasLongMessage && (
        <tr className="admin-sync-row-expanded">
          <td colSpan="6">
            <div className="admin-sync-full-message">{log.message}</div>
          </td>
        </tr>
      )}
    </>
  );
}

export default AdminPage;
