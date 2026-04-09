import { useState, useEffect } from "react";
import { apiFetch } from "../utils/apiFetch.js";
import { useToast } from "../contexts/ToastContext.jsx";

function AdminPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  const fetchUsers = async () => {
    try {
      const res = await apiFetch("/api/admin/users");
      if (res.ok) setUsers(await res.json());
    } catch {
      showToast("加载用户列表失败", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

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
        showToast(`用户「${username}」已删除`);
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || "删除失败", "error");
      }
    } catch {
      showToast("删除失败", "error");
    }
  };

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
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>角色</th>
              <th>注册时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td>
                  <span className={`role-badge role-${u.role}`}>{u.role}</span>
                </td>
                <td>{new Date(u.created_at).toLocaleDateString("zh-CN")}</td>
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
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default AdminPage;
