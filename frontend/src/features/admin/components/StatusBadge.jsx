import { useLanguage } from "../../../contexts/LanguageContext.jsx";

const STATUS_KEY = {
  running: "adminStatusRunning",
  done: "adminStatusDone",
  error: "adminStatusError",
  skipped: "adminStatusSkipped",
};

export function StatusBadge({ status }) {
  const { t } = useLanguage();
  if (!status || status === "idle") return null;
  const labelKey = STATUS_KEY[status];
  return <span className={`admin-task-badge admin-task-badge-${status}`}>{labelKey ? t(labelKey) : status}</span>;
}

export function SyncStatusBadge({ status }) {
  const { t } = useLanguage();
  const className = status === "skipped" ? "idle" : status;
  const labelKey = STATUS_KEY[status];
  return <span className={`admin-task-badge admin-task-badge-${className}`}>{labelKey ? t(labelKey) : status}</span>;
}
