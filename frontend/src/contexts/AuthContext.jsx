import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { setTokens, clearTokens, getAccessToken, getRefreshToken } from "../utils/apiFetch.js";

const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    const saved = localStorage.getItem("mtg-user");
    if (token && saved) {
      try {
        setUser(JSON.parse(saved));
      } catch {
        clearTokens();
        localStorage.removeItem("mtg-user");
      }
    }
    setLoading(false);
  }, []);

  const saveUser = (userData) => {
    setUser(userData);
    localStorage.setItem("mtg-user", JSON.stringify(userData));
  };

  const login = useCallback(async (username, password) => {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Login failed");
    }
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    saveUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(async (username, password) => {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Registration failed");
    }
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    saveUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    localStorage.removeItem("mtg-user");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
