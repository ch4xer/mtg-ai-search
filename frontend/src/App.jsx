import { useState, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Header from "./components/Header.jsx";
import Footer from "./components/Footer.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import DecksPage from "./pages/DecksPage.jsx";
import DeckDetailPage from "./pages/DeckDetailPage.jsx";
import AdminPage from "./pages/AdminPage.jsx";
import DiscoverPage from "./pages/DiscoverPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import { AuthProvider, useAuth } from "./contexts/AuthContext.jsx";
import { ToastProvider } from "./contexts/ToastContext.jsx";
import { LanguageProvider } from "./contexts/LanguageContext.jsx";

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

  return (
    <div className="app">
      <Header theme={theme} onToggleTheme={toggleTheme} />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<SearchPage imageMode={imageMode} onToggleImageMode={toggleImageMode} />} />
          <Route path="/discover" element={<DiscoverPage imageMode={imageMode} onToggleImageMode={toggleImageMode} />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/decks" element={<ProtectedRoute><DecksPage /></ProtectedRoute>} />
          <Route path="/decks/:id" element={<ProtectedRoute><DeckDetailPage imageMode={imageMode} /></ProtectedRoute>} />
          <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
          <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />
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