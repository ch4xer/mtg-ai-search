import { useEffect, useRef, useState } from "react";
import { deleteAdminUser, fetchAdminUsers, updateAdminUserRole } from "../../../api/admin.js";
import { useToast } from "../../../contexts/ToastContext.jsx";
import { useLanguage } from "../../../contexts/LanguageContext.jsx";
import { formatNumber } from "../utils.js";

export default function UsersSection() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalUsers, setTotalUsers] = useState(0);
  const [pageSize] = useState(20);
  const { showToast } = useToast();
  const { language, t } = useLanguage();
  const dateLocale = language === "zh" ? "zh-CN" : "en-US";
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
      showToast(t("adminUsersLoadFailed"), "error");
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
        showToast(t("adminRoleChanged").replace("{role}", newRole));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t("adminActionFailed"), "error");
      }
    } catch { showToast(t("adminActionFailed"), "error"); }
  };

  const handleDelete = async (userId, username) => {
    if (!confirm(t("adminConfirmDeleteUser").replace("{username}", username))) return;
    try {
      const res = await deleteAdminUser(userId);
      if (res.ok) {
        setUsers((prev) => prev.filter((u) => u.id !== userId));
        setTotalUsers((prev) => prev - 1);
        showToast(t("adminUserDeleted").replace("{username}", username));
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t("adminDeleteFailed"), "error");
      }
    } catch { showToast(t("adminDeleteFailed"), "error"); }
  };

  if (loading) return <div className="loading"><div className="loading-spinner" /></div>;

  return (
    <>
      <h2 className="admin-title">{t("adminTitleUsers")}</h2>

      <div className="admin-search-bar">
        <input
          type="text"
          className="admin-search-input"
          placeholder={t("adminSearchUsersPlaceholder")}
          value={searchQuery}
          onChange={handleSearchChange}
        />
        <span className="admin-user-count">{t("adminUsersTotal").replace("{n}", totalUsers)}</span>
      </div>

      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>{t("adminColUsername")}</th>
              <th>{t("adminColRole")}</th>
              <th>{t("adminColRegistered")}</th>
              <th>{t("adminColLastActive")}</th>
              <th className="admin-stat-group" colSpan="3">{t("adminColSearches")}</th>
              <th className="admin-stat-group" colSpan="3">{t("adminColTokens")}</th>
              <th>{t("adminColActions")}</th>
            </tr>
            <tr className="admin-subheader">
              <th colSpan="4"></th>
              <th className="admin-stat-col">{t("adminSubTotal")}</th>
              <th className="admin-stat-col">{t("adminSub7d")}</th>
              <th className="admin-stat-col">{t("adminSub3h")}</th>
              <th className="admin-stat-col">{t("adminSubTotal")}</th>
              <th className="admin-stat-col">{t("adminSub7d")}</th>
              <th className="admin-stat-col">{t("adminSub3h")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 ? (
              <tr>
                <td colSpan="11" style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)" }}>
                  {searchQuery ? t("adminUsersNoMatch") : t("adminUsersEmpty")}
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td><span className={`role-badge role-${u.role}`}>{u.role}</span></td>
                  <td>{new Date(u.created_at).toLocaleDateString(dateLocale)}</td>
                  <td>{u.last_active_at ? new Date(u.last_active_at).toLocaleDateString(dateLocale) : "—"}</td>
                  <td className="admin-stat-cell">{formatNumber(u.total_searches)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.searches_7d)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.searches_3h)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.total_tokens)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.tokens_7d)}</td>
                  <td className="admin-stat-cell">{formatNumber(u.tokens_3h)}</td>
                  <td className="admin-actions-cell">
                    <button className="btn-secondary" onClick={() => handleToggleRole(u.id, u.role)}>
                      {u.role === "admin" ? t("adminDemoteToUser") : t("adminPromoteToAdmin")}
                    </button>
                    <button className="btn-danger" onClick={() => handleDelete(u.id, u.username)}>
                      {t("adminDeleteUserBtn")}
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
            {t("adminPaginationPrev")}
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
            {t("adminPaginationNext")}
          </button>
        </div>
      )}
    </>
  );
}
