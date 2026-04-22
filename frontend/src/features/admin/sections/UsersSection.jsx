import { useEffect, useRef, useState } from "react";
import { deleteAdminUser, fetchAdminUsers, updateAdminUserRole } from "../../../api/admin.js";
import { useToast } from "../../../contexts/ToastContext.jsx";
import { formatNumber } from "../utils.js";

export default function UsersSection() {
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
      const res = await fetchAdminUsers(params);
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
      const res = await updateAdminUserRole(userId, newRole);
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
      const res = await deleteAdminUser(userId);
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
