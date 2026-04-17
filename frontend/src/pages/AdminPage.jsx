import { useState, useEffect, useRef } from "react";
import { apiFetch } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";

function formatNumber(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

function AdminPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const [pageSize] = useState(20);
  const [taskStatus, setTaskStatus] = useState({ reseed: { status: "idle" }, reembed: { status: "idle" } });
  const [syncLogs, setSyncLogs] = useState([]);
  const { showToast } = useToast();
  const pollRef = useRef(null);
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
          // Backwards compatibility with old API format
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

  // Start polling when a task is running
  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      const data = await fetchTaskStatus();
      if (!data) return;
      const anyRunning = Object.values(data).some((t) => t.status === "running");
      if (!anyRunning) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        fetchUsers();
        fetchSyncLogs();
      }
    }, 3000);
  };

  useEffect(() => {
    fetchUsers("", 1);
    fetchSyncLogs();
    fetchTaskStatus().then((data) => {
      if (data && Object.values(data).some((t) => t.status === "running")) {
        startPolling();
      }
    });
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleSearchChange = (e) => {
    const value = e.target.value;
    setSearchQuery(value);
    // Debounce search
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

  const handleReseed = async () => {
    if (!confirm("确定要重新拉取卡牌数据吗？这将清除所有现有卡牌数据并重新下载，过程可能需要较长时间。")) return;
    try {
      const res = await apiFetch("/api/admin/reseed", { method: "POST" });
      if (res.ok) {
        showToast("已开始重新拉取卡牌数据");
        await fetchTaskStatus();
        startPolling();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "操作失败", "error");
      }
    } catch {
      showToast("操作失败", "error");
    }
  };

  const handleReseedOnly = async () => {
    if (!confirm("确定要仅重新拉取卡牌数据（不更新 embedding）吗？此操作会清除现有卡牌数据。")) return;
    try {
      const res = await apiFetch("/api/admin/reseed-only", { method: "POST" });
      if (res.ok) {
        showToast("已开始仅拉取卡牌数据");
        await fetchTaskStatus();
        startPolling();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "操作失败", "error");
      }
    } catch {
      showToast("操作失败", "error");
    }
  };

  const handleReembed = async () => {
    if (!confirm("确定要重新生成所有 embedding 吗？过程可能需要较长时间。")) return;
    try {
      const res = await apiFetch("/api/admin/reembed", { method: "POST" });
      if (res.ok) {
        showToast("已开始重新生成 embedding");
        await fetchTaskStatus();
        startPolling();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "操作失败", "error");
      }
    } catch {
      showToast("操作失败", "error");
    }
  };

  const handleSync = async () => {
    try {
      const res = await apiFetch("/api/admin/sync", { method: "POST" });
      if (res.ok) {
        showToast("已开始增量同步");
        await fetchTaskStatus();
        startPolling();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "操作失败", "error");
      }
    } catch {
      showToast("操作失败", "error");
    }
  };

  const handleToggleRole = async (userId, currentRole) => {
    const newRole = currentRole === "admin" ? "user" : "admin";
    try {
      const res = await apiFetch(`/api/admin/users/${userId}/role`, {
        method: "PUT",
        body: { role: newRole },
      });
      if (res.ok) {
        setUsers((prev) =>
          prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
        );
        showToast(`已将用户角色更改为 ${newRole}`);
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "操作失败", "error");
      }
    } catch {
      showToast("操作失败", "error");
    }
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
    } catch {
      showToast("删除失败", "error");
    }
  };

  const anyRunning = Object.values(taskStatus).some((t) => t.status === "running");

  if (loading) {
    return (
      <div className="loading">
        <div className="loading-spinner" />
        <p>加载用户列表...</p>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <h2 className="admin-title">用户管理</h2>

      {/* Search bar */}
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
                  <td>
                    <span className={`role-badge role-${u.role}`}>{u.role}</span>
                  </td>
                  <td>{new Date(u.created_at).toLocaleDateString("zh-CN")}</td>
                  <td>{u.last_active_at ? new Date(u.last_active_at).toLocaleDateString("zh-CN") : "—"}</td>
                  <td className="admin-stat-cell">{formatNumber(u.total_searches)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.searches_7d)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.searches_3h)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.total_tokens)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.tokens_7d)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.tokens_3h)}</td>
                  <td className="admin-actions-cell">
                    <button
                      className="btn-secondary"
                      onClick={() => handleToggleRole(u.id, u.role)}
                    >
                      {u.role === "admin" ? "降为用户" : "升为管理员"}
                    </button>
                    <button
                      className="btn-danger"
                      onClick={() => handleDelete(u.id, u.username)}
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="admin-pagination">
          <button
            className="admin-page-btn"
            disabled={currentPage <= 1}
            onClick={() => handlePageChange(currentPage - 1)}
          >
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
                <button
                  key={item}
                  className={`admin-page-btn ${item === currentPage ? "active" : ""}`}
                  onClick={() => handlePageChange(item)}
                >
                  {item}
                </button>
              )
            )}
          <button
            className="admin-page-btn"
            disabled={currentPage >= totalPages}
            onClick={() => handlePageChange(currentPage + 1)}
          >
            下一页 &raquo;
          </button>
        </div>
      )}

      {/* DB Maintenance */}
      <h2 className="admin-title" style={{ marginTop: "2.5rem" }}>数据库维护</h2>
      <div className="admin-db-actions">
        <div className="admin-db-card">
          <div className="admin-db-card-header">
            <h3>重新拉取卡牌数据</h3>
            <StatusBadge status={taskStatus.reseed?.status} />
          </div>
          <p className="admin-db-card-desc">
            从 Scryfall 重新下载所有卡牌数据并重新导入数据库，同时重新生成 embedding。
            此操作会清除现有卡牌数据。
          </p>
          {taskStatus.reseed?.status === "running" && (
            <div className="admin-task-progress">
              <div className="loading-spinner-small" />
              <span>{taskStatus.reseed.message}</span>
            </div>
          )}
          {taskStatus.reseed?.status === "done" && (
            <p className="admin-task-done">{taskStatus.reseed.message}</p>
          )}
          {taskStatus.reseed?.status === "error" && (
            <p className="admin-task-error">{taskStatus.reseed.message}</p>
          )}
          <button
            className="btn-primary"
            onClick={handleReseed}
            disabled={anyRunning}
          >
            拉取数据 + Embedding
          </button>
        </div>

        <div className="admin-db-card">
          <div className="admin-db-card-header">
            <h3>仅拉取卡牌数据</h3>
            <StatusBadge status={taskStatus.reseed?.status} />
          </div>
          <p className="admin-db-card-desc">
            从 Scryfall 重新下载并导入卡牌数据，但不重新生成 embedding。
            适用于仅需更新卡牌文本或图片数据的场景。
          </p>
          {taskStatus.reseed?.status === "running" && (
            <div className="admin-task-progress">
              <div className="loading-spinner-small" />
              <span>{taskStatus.reseed.message}</span>
            </div>
          )}
          {taskStatus.reseed?.status === "done" && (
            <p className="admin-task-done">{taskStatus.reseed.message}</p>
          )}
          {taskStatus.reseed?.status === "error" && (
            <p className="admin-task-error">{taskStatus.reseed.message}</p>
          )}
          <button
            className="btn-primary"
            onClick={handleReseedOnly}
            disabled={anyRunning}
          >
            仅拉取数据
          </button>
        </div>

        <div className="admin-db-card">
          <div className="admin-db-card-header">
            <h3>重新生成 Embedding</h3>
            <StatusBadge status={taskStatus.reembed?.status} />
          </div>
          <p className="admin-db-card-desc">
            清除所有现有 embedding 并重新生成。卡牌数据本身不会改变。
            适用于更换了 embedding 模型后使用。
          </p>
          {taskStatus.reembed?.status === "running" && (
            <div className="admin-task-progress">
              <div className="loading-spinner-small" />
              <span>{taskStatus.reembed.message}</span>
            </div>
          )}
          {taskStatus.reembed?.status === "done" && (
            <p className="admin-task-done">{taskStatus.reembed.message}</p>
          )}
          {taskStatus.reembed?.status === "error" && (
            <p className="admin-task-error">{taskStatus.reembed.message}</p>
          )}
          <button
            className="btn-primary"
            onClick={handleReembed}
            disabled={anyRunning}
          >
            重新生成 Embedding
          </button>
        </div>
      </div>

      {/* Sync logs */}
      <div className="admin-sync-section">
        <div className="admin-sync-header">
          <h2 className="admin-title">每日同步记录</h2>
          <button className="btn-accent" onClick={handleSync} disabled={anyRunning}>
            手动同步
          </button>
        </div>
        <p className="admin-db-card-desc" style={{ marginBottom: "1rem" }}>
          系统每天午夜自动检查 Scryfall 更新，同步新卡牌并更新已有卡牌的图片链接。
        </p>
        {syncLogs.length === 0 ? (
          <p className="admin-sync-empty">暂无同步记录</p>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>状态</th>
                  <th>新增卡牌</th>
                  <th>更新卡牌</th>
                  <th>详情</th>
                </tr>
              </thead>
              <tbody>
                {syncLogs.map((log) => (
                  <tr key={log.id}>
                    <td>{new Date(log.started_at).toLocaleString("zh-CN")}</td>
                    <td><SyncStatusBadge status={log.status} /></td>
                    <td>{log.new_cards}</td>
                    <td>{log.updated_cards}</td>
                    <td className="admin-sync-message">{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
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

export default AdminPage;
