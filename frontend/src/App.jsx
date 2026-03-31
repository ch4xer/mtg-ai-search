import { useState, useEffect } from "react";
import { Routes, Route } from "react-router-dom";
import Header from "./components/Header.jsx";
import SearchPage from "./pages/SearchPage.jsx";

function App() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem("mtg-theme") || "dark";
  });
  const [imageMode, setImageMode] = useState(() => {
    return localStorage.getItem("mtg-image-mode") || "border_crop";
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
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
        </Routes>
      </main>
    </div>
  );
}

export default App;
