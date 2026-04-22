export function StatusBadge({ status }) {
  if (!status || status === "idle") return null;
  const labels = { running: "运行中", done: "已完成", error: "失败" };
  return <span className={`admin-task-badge admin-task-badge-${status}`}>{labels[status]}</span>;
}

export function SyncStatusBadge({ status }) {
  const labels = { running: "运行中", done: "完成", error: "失败", skipped: "跳过" };
  const className = status === "skipped" ? "idle" : status;
  return <span className={`admin-task-badge admin-task-badge-${className}`}>{labels[status] || status}</span>;
}
