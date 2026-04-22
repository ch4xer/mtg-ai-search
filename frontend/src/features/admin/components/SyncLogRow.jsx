import { useState } from "react";
import { SyncStatusBadge } from "./StatusBadge.jsx";

export default function SyncLogRow({ log }) {
  const [expanded, setExpanded] = useState(false);
  const hasLongMessage = log.message && log.message.length > 50;

  return (
    <>
      <tr className="admin-sync-row" onClick={() => hasLongMessage && setExpanded(!expanded)}>
        <td>
          {hasLongMessage && (
            <button className="admin-expand-btn" onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                {expanded ? <path d="M18 15l-6-6-6 6" /> : <path d="M6 9l6 6 6-6" />}
              </svg>
            </button>
          )}
        </td>
        <td>{new Date(log.started_at).toLocaleString("zh-CN")}</td>
        <td><SyncStatusBadge status={log.status} /></td>
        <td>{log.new_cards}</td>
        <td>{log.updated_cards}</td>
        <td className="admin-sync-message">
          {hasLongMessage ? (expanded ? log.message : log.message.slice(0, 50) + "...") : (log.message || "—")}
        </td>
      </tr>
      {expanded && hasLongMessage && (
        <tr className="admin-sync-row-expanded">
          <td colSpan="6">
            <div className="admin-sync-full-message">{log.message}</div>
          </td>
        </tr>
      )}
    </>
  );
}
