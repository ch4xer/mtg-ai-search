export default function StatCard({ label, value, detail, variant }) {
  return (
    <div className={`admin-stat-card ${variant === "warn" ? "warn" : ""} ${variant === "ok" ? "ok" : ""}`}>
      <div className="admin-stat-card-value">{value}</div>
      <div className="admin-stat-card-label">{label}</div>
      {detail && <div className="admin-stat-card-detail">{detail}</div>}
    </div>
  );
}
