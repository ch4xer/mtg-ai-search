import { useEffect, useState } from "react";
import { useAuth } from "../contexts/AuthContext.jsx";
import { fetchUserDecks } from "../api/decks.js";

export function useUserDecks() {
  const [decks, setDecks] = useState([]);
  const { user } = useAuth();

  useEffect(() => {
    if (!user) {
      setDecks([]);
      return;
    }

    let cancelled = false;

    fetchUserDecks()
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
