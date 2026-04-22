import { useEffect, useRef, useState } from "react";
import { fetchAdminSyncLogs, fetchAdminTaskStatus, runAdminTask } from "../../../api/admin.js";
import { useToast } from "../../../contexts/ToastContext.jsx";
import SyncLogRow from "../components/SyncLogRow.jsx";
import SyncTaskNotice from "../components/SyncTaskNotice.jsx";
import TaskCard from "../components/TaskCard.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";

export default function DatabaseSection() {
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
      const res = await fetchAdminSyncLogs();
      if (res.ok) setSyncLogs(await res.json());
    } catch { /* ignore */ }
  };

  const fetchTaskStatus = async () => {
    try {
      const res = await fetchAdminTaskStatus();
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
      const res = await runAdminTask(url);
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
  const syncStatus = taskStatus.reseed;
  const isSyncRunning = syncStatus?.status === "running";

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
          <div className="admin-sync-title-group">
            <h3 className="admin-section-title">每日同步记录</h3>
            <StatusBadge status={syncStatus?.status} />
          </div>
          <div className="admin-sync-buttons">
            <button className="btn-secondary" onClick={handleForceSyncDataOnly} disabled={anyRunning}>
              {isSyncRunning ? "同步中..." : "仅更新数据"}
            </button>
            <button className="btn-secondary" onClick={handleForceSync} disabled={anyRunning}>
              {isSyncRunning ? "同步中..." : "强制刷新"}
            </button>
            <button className="btn-accent" onClick={handleSync} disabled={anyRunning}>
              {isSyncRunning ? "同步中..." : "手动同步"}
            </button>
          </div>
        </div>
        <SyncTaskNotice status={syncStatus} />
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
