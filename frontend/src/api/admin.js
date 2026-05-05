import { apiFetch, getAccessToken } from "../utils/apiFetch.js";

export function fetchAdminStats() {
  return apiFetch("/api/admin/stats");
}

export function fetchAdminUsers(params) {
  return apiFetch(`/api/admin/users?${params}`);
}

export function updateAdminUserRole(userId, role) {
  return apiFetch(`/api/admin/users/${userId}/role`, { method: "PUT", body: { role } });
}

export function deleteAdminUser(userId) {
  return apiFetch(`/api/admin/users/${userId}`, { method: "DELETE" });
}

export function fetchAdminSyncLogs() {
  return apiFetch("/api/admin/sync-logs");
}

export function fetchAdminTaskStatus() {
  return apiFetch("/api/admin/task-status");
}

export function runAdminTask(url) {
  return apiFetch(url, { method: "POST" });
}

export function fetchAdminSettings() {
  return apiFetch("/api/admin/settings");
}

export function updateAdminSettings(body) {
  return apiFetch("/api/admin/settings", { method: "PUT", body });
}

export function downloadAdminCardExport() {
  const token = getAccessToken();
  return fetch("/api/admin/export/cards", {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}
