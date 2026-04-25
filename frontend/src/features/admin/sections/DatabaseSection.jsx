import { useEffect, useRef, useState } from "react";
import { fetchAdminSyncLogs, fetchAdminTaskStatus, runAdminTask } from "../../../api/admin.js";
import { useToast } from "../../../contexts/ToastContext.jsx";
import { useLanguage } from "../../../contexts/LanguageContext.jsx";
import SyncLogRow from "../components/SyncLogRow.jsx";
import SyncTaskNotice from "../components/SyncTaskNotice.jsx";
import TaskCard from "../components/TaskCard.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";

export default function DatabaseSection() {
  const [taskStatus, setTaskStatus] = useState({
    reseed: { status: "idle" },
    reembed: { status: "idle" },
    effect_chunks: { status: "idle" },
    seed_abilities: { status: "idle" },
  });
  const [syncLogs, setSyncLogs] = useState([]);
  const { showToast } = useToast();
  const { t } = useLanguage();
  const pollRef = useRef(null);

  const fetchSyncLogs = async () => {
    try {
      const res = await fetchAdminSyncLogs();
      if (res.ok) setSyncLogs(await res.json());
    } catch { /* ignore */ }
  };

  const lastTaskStatusJsonRef = useRef("");
  const fetchTaskStatus = async () => {
    try {
      const res = await fetchAdminTaskStatus();
      if (res.ok) {
        const data = await res.json();
        const serialized = JSON.stringify(data);
        if (serialized !== lastTaskStatusJsonRef.current) {
          lastTaskStatusJsonRef.current = serialized;
          setTaskStatus(data);
        }
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
      const anyRunning = Object.values(data).some((task) => task.status === "running");
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
      if (data && Object.values(data).some((task) => task.status === "running")) {
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
        showToast(err.detail || t("adminActionFailed"), "error");
      }
    } catch { showToast(t("adminActionFailed"), "error"); }
  };

  const handleReembed = async () => {
    if (!confirm(t("adminTaskReembedConfirm"))) return;
    runAction("/api/admin/reembed", t("adminTaskReembedStarted"));
  };
  const handleRebuildEffectChunks = async () => {
    if (!confirm(t("adminTaskEffectChunksConfirm"))) return;
    runAction("/api/admin/rebuild-effect-chunks", t("adminTaskEffectChunksStarted"));
  };
  const handleSeedAbilities = () => {
    if (!confirm(t("adminTaskAbilitiesForceConfirm"))) return;
    runAction("/api/admin/seed-abilities", t("adminTaskAbilitiesForceStarted"));
  };
  const handleSyncAbilities = () => runAction("/api/admin/sync-abilities", t("adminTaskAbilitiesIncrementalStarted"));
  const handleSync = () => runAction("/api/admin/sync", t("adminSyncStartedManual"));
  const handleForceSync = () => runAction("/api/admin/sync?force=true", t("adminSyncStartedForce"));
  const handleForceSyncDataOnly = () => runAction("/api/admin/sync?force=true&skip_embeddings=true", t("adminSyncStartedDataOnly"));

  const anyRunning = Object.values(taskStatus).some((task) => task.status === "running");
  const syncStatus = taskStatus.reseed;
  const isSyncRunning = syncStatus?.status === "running";

  return (
    <>
      <h2 className="admin-title">{t("adminTitleDatabase")}</h2>
      <div className="admin-db-actions">
        <TaskCard
          title={t("adminTaskReembedTitle")}
          desc={t("adminTaskReembedDesc")}
          status={taskStatus.reembed}
          disabled={anyRunning}
          onRun={handleReembed}
          btnText={t("adminTaskReembedBtn")}
        />
        <TaskCard
          title={t("adminTaskEffectChunksTitle")}
          desc={t("adminTaskEffectChunksDesc")}
          status={taskStatus.effect_chunks}
          disabled={anyRunning}
          onRun={handleRebuildEffectChunks}
          btnText={t("adminTaskEffectChunksBtn")}
        />
        <TaskCard
          title={t("adminTaskAbilitiesTitle")}
          desc={t("adminTaskAbilitiesDesc")}
          status={taskStatus.seed_abilities}
          disabled={anyRunning}
          actions={[
            { label: t("adminTaskAbilitiesIncremental"), onClick: handleSyncAbilities },
            { label: t("adminTaskAbilitiesForce"), onClick: handleSeedAbilities, variant: "secondary" },
          ]}
        />
      </div>

      {/* Sync logs */}
      <div className="admin-sync-section">
        <div className="admin-sync-header">
          <div className="admin-sync-title-group">
            <h3 className="admin-section-title">{t("adminSyncSectionTitle")}</h3>
            <StatusBadge status={syncStatus?.status} />
          </div>
          <div className="admin-sync-buttons">
            <button className="btn-secondary" onClick={handleForceSyncDataOnly} disabled={anyRunning}>
              {isSyncRunning ? t("adminSyncBtnInProgress") : t("adminSyncBtnDataOnly")}
            </button>
            <button className="btn-secondary" onClick={handleForceSync} disabled={anyRunning}>
              {isSyncRunning ? t("adminSyncBtnInProgress") : t("adminSyncBtnForce")}
            </button>
            <button className="btn-accent" onClick={handleSync} disabled={anyRunning}>
              {isSyncRunning ? t("adminSyncBtnInProgress") : t("adminSyncBtnManual")}
            </button>
          </div>
        </div>
        <SyncTaskNotice status={syncStatus} />
        <p className="admin-db-card-desc" style={{ marginBottom: "1rem" }}>
          {t("adminSyncDescription")}
        </p>
        {syncLogs.length === 0 ? (
          <p className="admin-empty">{t("adminSyncLogsEmpty")}</p>
        ) : (
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th style={{ width: "40px" }}></th>
                  <th>{t("adminColTime")}</th>
                  <th>{t("adminColStatus")}</th>
                  <th>{t("adminColNewCards")}</th>
                  <th>{t("adminColUpdatedCards")}</th>
                  <th>{t("adminColDetail")}</th>
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
