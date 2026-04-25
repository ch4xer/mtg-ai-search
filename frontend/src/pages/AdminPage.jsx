import { useParams, useNavigate } from "react-router-dom";
import DashboardSection from "../features/admin/sections/DashboardSection.jsx";
import UsersSection from "../features/admin/sections/UsersSection.jsx";
import DatabaseSection from "../features/admin/sections/DatabaseSection.jsx";
import SettingsSection from "../features/admin/sections/SettingsSection.jsx";
import { useLanguage } from "../contexts/LanguageContext.jsx";

const NAV_ITEMS = [
  { key: "dashboard", labelKey: "adminNavDashboard", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" },
  { key: "users", labelKey: "adminNavUsers", icon: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197" },
  { key: "database", labelKey: "adminNavDatabase", icon: "M4 7v10c0 2 8 2 8 2s8 0 8-2V7M4 7c0 2 8 2 8 2s8 0 8-2M4 7c0-2 8-2 8-2s8 0 8 2" },
  { key: "settings", labelKey: "adminNavSettings", icon: "M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" },
];

function AdminPage() {
  const { section } = useParams();
  const navigate = useNavigate();
  const { t } = useLanguage();
  const validSections = ["dashboard", "users", "database", "settings"];
  const activeSection = validSections.includes(section) ? section : "dashboard";

  const handleSectionChange = (newSection) => {
    navigate(`/admin/${newSection}`);
  };

  return (
    <div className="admin-layout">
      <aside className="admin-sidebar">
        <nav className="admin-sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              className={`admin-sidebar-item ${activeSection === item.key ? "active" : ""}`}
              onClick={() => handleSectionChange(item.key)}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d={item.icon} />
              </svg>
              <span>{t(item.labelKey)}</span>
            </button>
          ))}
        </nav>
      </aside>
      <main className="admin-content">
        {activeSection === "dashboard" && <DashboardSection />}
        {activeSection === "users" && <UsersSection />}
        {activeSection === "database" && <DatabaseSection />}
        {activeSection === "settings" && <SettingsSection />}
      </main>
    </div>
  );
}

export default AdminPage;
