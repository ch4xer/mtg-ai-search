import { useState, useEffect } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import Header from "./components/Header.jsx";
import Footer from "./components/Footer.jsx";
import SearchContainer from "./pages/SearchContainer.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import DecksPage from "./pages/DecksPage.jsx";
import DeckDetailPage from "./pages/DeckDetailPage.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import { AuthProvider, useAuth } from "./contexts/AuthContext.jsx";
import { ToastProvider } from "./contexts/ToastContext.jsx";
import { LanguageProvider } from "./contexts/LanguageContext.jsx";
import { useLanguage } from "./contexts/LanguageContext.jsx";

function SystemUpgradeNotice() {
  const { t } = useLanguage();

  return (
    <div className="system-upgrade" role="status" aria-live="polite">
      <div className="system-upgrade-inner">
        <div className="system-upgrade-mark" aria-hidden="true">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3l8 4v5c0 4.4-3.1 7.7-8 9-4.9-1.3-8-4.6-8-9V7l8-4z" />
            <path d="M9 12l2 2 4-5" />
          </svg>
        </div>
        <p>{t("systemMaintenanceUpgrade")}</p>
      </div>
    </div>
  );
}

function useSystemReadiness() {
  const [isUpgrading, setIsUpgrading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let intervalId;

    const checkHealth = async () => {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        const data = await res.json().catch(() => null);
        if (!cancelled) {
          setIsUpgrading(data?.status === "initializing");
        }
      } catch {
        if (!cancelled) {
          setIsUpgrading(false);
        }
      }
    };

    checkHealth();
    intervalId = window.setInterval(checkHealth, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, []);

  return isUpgrading;
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function AdminRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/" replace />;
  return children;
}

function AppContent() {
  const isUpgrading = useSystemReadiness();
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem("mtg-theme");
    if (saved) return saved;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  const [imageMode, setImageMode] = useState(() => {
    return localStorage.getItem("mtg-image-mode") || "art_crop";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.style.colorScheme = theme;
    localStorage.setItem("mtg-theme", theme);
    const favicon = document.getElementById("app-favicon");
    if (favicon) {
      favicon.href = theme === "dark" ? "/favicon-dark.svg" : "/favicon-light.svg";
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const toggleImageMode = () => {
    setImageMode((prev) => {
      const next = prev === "border_crop" ? "art_crop" : "border_crop";
      localStorage.setItem("mtg-image-mode", next);
      return next;
    });
  };

  const location = useLocation();
  const isSearchRoute =
    location.pathname === "/" ||
    location.pathname === "/discover" ||
    location.pathname === "/exact-match";

  return (
    <div className="app">
      <Header theme={theme} onToggleTheme={toggleTheme} />
      {isUpgrading && <SystemUpgradeNotice />}
      <main className="main-content">
        {/* SearchContainer stays mounted across search routes to preserve state */}
        <div style={{ display: isSearchRoute ? undefined : "none" }}>
          <SearchContainer imageMode={imageMode} onToggleImageMode={toggleImageMode} />
        </div>
        <Routes>
          <Route path="/" element={null} />
          <Route path="/tag-search" element={<Navigate to="/" replace />} />
          <Route path="/discover" element={<Navigate to="/exact-match" replace />} />
          <Route path="/exact-match" element={null} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/decks" element={<ProtectedRoute><DecksPage /></ProtectedRoute>} />
          <Route path="/decks/:id" element={<DeckDetailPage imageMode={imageMode} />} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
          <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="/admin/:section" element={<AdminRoute><AdminPage /></AdminRoute>} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <LanguageProvider>
        <ToastProvider>
          <AppContent />
        </ToastProvider>
      </LanguageProvider>
    </AuthProvider>
  );
}

export default App;
