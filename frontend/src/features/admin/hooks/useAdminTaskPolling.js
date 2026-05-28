import { useEffect, useRef, useState } from "react";
import { fetchAdminSyncLogs, fetchAdminTaskStatus } from "../../../api/admin.js";

const DEFAULT_TASK_STATUS = {
  reseed: { status: "idle" },
  seed_abilities: { status: "idle" },
  tag_sync: { status: "idle" },
  tag_embeddings: { status: "idle" },
  card_translations: { status: "idle" },
};

export function useAdminTaskPolling() {
  const [taskStatus, setTaskStatus] = useState(DEFAULT_TASK_STATUS);
  const [syncLogs, setSyncLogs] = useState([]);
  const lastTaskStatusJsonRef = useRef("");
  const pollRef = useRef(null);

  const refreshSyncLogs = async () => {
    try {
      const res = await fetchAdminSyncLogs();
      if (res.ok) setSyncLogs(await res.json());
    } catch {
      // Polling is best-effort; the next refresh will retry.
    }
  };

  const refreshTaskStatus = async () => {
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
    } catch {
      // Polling is best-effort; the next refresh will retry.
    }
    return null;
  };

  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      const data = await refreshTaskStatus();
      if (!data) return;

      const anyRunning = Object.values(data).some((task) => task.status === "running");
      if (!anyRunning) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        refreshSyncLogs();
      }
    }, 3000);
  };

  useEffect(() => {
    refreshSyncLogs();
    refreshTaskStatus().then((data) => {
      if (data && Object.values(data).some((task) => task.status === "running")) {
        startPolling();
      }
    });

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  return {
    taskStatus,
    syncLogs,
    refreshTaskStatus,
    startPolling,
  };
}
