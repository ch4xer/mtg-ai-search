import { formatElapsed } from "../utils.js";
import { useLanguage } from "../../../contexts/LanguageContext.jsx";

export default function SyncTaskNotice({ status }) {
  const { t } = useLanguage();
  if (!status || status.status === "idle") return null;
  const isRunning = status.status === "running";
  const isError = status.status === "error";
  const titleKey = isRunning ? "adminSyncNoticeRunning" : isError ? "adminSyncNoticeError" : "adminSyncNoticeDone";
  const fallbackMsg = isRunning ? t("adminSyncNoticeMsgRunning") : t("adminSyncNoticeMsgFinished");
  return (
    <div className={`admin-sync-status admin-sync-status-${status.status}`}>
      <div className="admin-sync-status-main">
        {isRunning && <div className="loading-spinner-small" />}
        <div>
          <div className="admin-sync-status-title">{t(titleKey)}</div>
          <div className="admin-sync-status-message">{status.message || fallbackMsg}</div>
        </div>
      </div>
      {isRunning && (
        <span className="admin-sync-status-time">
          {t("adminSyncNoticeElapsed").replace("{elapsed}", formatElapsed(status.elapsed_seconds || 0))}
        </span>
      )}
    </div>
  );
}
