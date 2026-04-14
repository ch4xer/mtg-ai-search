import { useEffect, useState } from "react";
import { useAuth } from "../contexts/AuthContext.jsx";
import { apiFetch } from "../utils/apiFetch.js";

export function useUserDecks() {
  const [decks, setDecks] = useState([]);
  const { user } = useAuth();

  useEffect(() => {
    if (!user) {
      setDecks([]);
      return;
    }

    let cancelled = false;

    apiFetch("/api/decks")
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (!cancelled) setDecks(data);
      })
      .catch(() => {
        if (!cancelled) setDecks([]);
      });

    return () => {
      cancelled = true;
    };
  }, [user]);

  return decks;
}
