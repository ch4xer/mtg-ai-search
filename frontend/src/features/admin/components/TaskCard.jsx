import { StatusBadge } from "./StatusBadge.jsx";

export default function TaskCard({ title, desc, status, disabled, onRun, btnText, actions = null }) {
  return (
    <div className="admin-db-card">
      <div className="admin-db-card-header">
        <h3>{title}</h3>
        <StatusBadge status={status?.status} />
      </div>
      <p className="admin-db-card-desc">{desc}</p>
      {status?.status === "running" && (
        <div className="admin-task-progress">
          <div className="loading-spinner-small" />
          <span>{status.message}</span>
        </div>
      )}
      {status?.status === "done" && <p className="admin-task-done">{status.message}</p>}
      {status?.status === "error" && <p className="admin-task-error">{status.message}</p>}
      {actions?.length ? (
        <div className="admin-db-card-actions">
          {actions.map((action) => (
            <button
              key={action.label}
              className={action.variant === "secondary" ? "btn-secondary" : "btn-primary"}
              onClick={action.onClick}
              disabled={disabled || action.disabled}
            >
              {action.label}
            </button>
          ))}
        </div>
      ) : (
        <button className="btn-primary" onClick={onRun} disabled={disabled}>{btnText}</button>
      )}
    </div>
  );
}
