import { formatElapsed } from "../utils.js";

export default function SyncTaskNotice({ status }) {
  if (!status || status.status === "idle") return null;
  const isRunning = status.status === "running";
  const isError = status.status === "error";
  return (
    <div className={`admin-sync-status admin-sync-status-${status.status}`}>
      <div className="admin-sync-status-main">
        {isRunning && <div className="loading-spinner-small" />}
        <div>
          <div className="admin-sync-status-title">
            {isRunning ? "数据同步进行中" : isError ? "数据同步失败" : "数据同步已完成"}
          </div>
          <div className="admin-sync-status-message">
            {status.message || (isRunning ? "正在处理..." : "任务已结束")}
          </div>
        </div>
      </div>
      {isRunning && (
        <span className="admin-sync-status-time">
          已运行 {formatElapsed(status.elapsed_seconds || 0)}
        </span>
      )}
    </div>
  );
}
