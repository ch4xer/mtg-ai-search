import { useState } from "react";
import { downloadAdminCardExport, runAdminTask } from "../../../api/admin.js";
import { useToast } from "../../../contexts/ToastContext.jsx";
import { useLanguage } from "../../../contexts/LanguageContext.jsx";
import SyncLogRow from "../components/SyncLogRow.jsx";
import SyncTaskNotice from "../components/SyncTaskNotice.jsx";
import TaskCard from "../components/TaskCard.jsx";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { useAdminTaskPolling } from "../hooks/useAdminTaskPolling.js";

export default function DatabaseSection() {
  const [exportingCards, setExportingCards] = useState(false);
  const { showToast } = useToast();
  const { t } = useLanguage();
  const { taskStatus, syncLogs, refreshTaskStatus, startPolling } = useAdminTaskPolling();

  const runAction = async (url, successMsg) => {
    try {
      const res = await runAdminTask(url);
      if (res.ok) {
        showToast(successMsg);
        await refreshTaskStatus();
        startPolling();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t("adminActionFailed"), "error");
      }
    } catch { showToast(t("adminActionFailed"), "error"); }
  };

  const handleSyncAbilities = () => runAction("/api/admin/sync-abilities", t("adminTaskAbilitiesIncrementalStarted"));
  const handleSyncFunctionTags = () => runAction("/api/admin/sync-function-tags", t("adminTaskFunctionTagsStarted"));
  const handleTagEmbeddings = () => runAction("/api/admin/tag-embeddings", t("adminTaskTagEmbeddingsStarted"));
  const handleCardTranslations = () => runAction("/api/admin/sync-card-translations", t("adminTaskCardTranslationsStarted"));
  const handleSync = () => runAction("/api/admin/sync", t("adminSyncStartedManual"));
  const handleForceSync = () => runAction("/api/admin/sync?force=true", t("adminSyncStartedForce"));
  const handleExportCards = async () => {
    setExportingCards(true);
    try {
      const res = await downloadAdminCardExport();
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast(err.detail || t("adminCardExportFailed"), "error");
        return;
      }
      const blob = await res.blob();
      const disposition = res.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^"]+)"?/i);
      const filename = match?.[1] || "mtg-card-data.zip";
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showToast(t("adminCardExportStarted"));
    } catch {
      showToast(t("adminCardExportFailed"), "error");
    } finally {
      setExportingCards(false);
    }
  };

  const anyRunning = Object.values(taskStatus).some((task) => task.status === "running");
  const syncStatus = taskStatus.reseed;
  const isSyncRunning = syncStatus?.status === "running";

  return (
    <>
      <h2 className="admin-title">{t("adminTitleDatabase")}</h2>
      <div className="admin-db-actions">
        <TaskCard
          title={t("adminTaskAbilitiesTitle")}
          desc={t("adminTaskAbilitiesDesc")}
          status={taskStatus.seed_abilities}
          disabled={anyRunning}
          onRun={handleSyncAbilities}
          btnText={t("adminTaskAbilitiesIncremental")}
        />
        <TaskCard
          title={t("adminTaskFunctionTagsTitle")}
          desc={t("adminTaskFunctionTagsDesc")}
          status={taskStatus.tag_sync}
          disabled={anyRunning}
          onRun={handleSyncFunctionTags}
          btnText={t("adminTaskFunctionTagsBtn")}
        />
        <TaskCard
          title={t("adminTaskTagEmbeddingsTitle")}
          desc={t("adminTaskTagEmbeddingsDesc")}
          status={taskStatus.tag_embeddings}
          disabled={anyRunning}
          onRun={handleTagEmbeddings}
          btnText={t("adminTaskTagEmbeddingsBtn")}
        />
        <TaskCard
          title={t("adminTaskCardTranslationsTitle")}
          desc={t("adminTaskCardTranslationsDesc")}
          status={taskStatus.card_translations}
          disabled={anyRunning}
          onRun={handleCardTranslations}
          btnText={t("adminTaskCardTranslationsBtn")}
        />
        <TaskCard
          title={t("adminCardExportTitle")}
          desc={t("adminCardExportDesc")}
          status={{ status: exportingCards ? "running" : "idle", message: t("adminCardExportRunning") }}
          disabled={exportingCards}
          onRun={handleExportCards}
          btnText={exportingCards ? t("adminCardExportRunning") : t("adminCardExportBtn")}
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
