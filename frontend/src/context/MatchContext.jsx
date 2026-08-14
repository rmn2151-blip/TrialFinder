import { createContext, useCallback, useContext, useState } from "react";

const MatchContext = createContext(null);

// Holds the most recent search: the patient we searched with and the trial
// results we got back. Kept in memory so users can visit other pages (like
// the education pages) and return to the same result set without a re-fetch.
export function MatchProvider({ children }) {
  const [patient, setPatient] = useState(null);
  const [data, setData] = useState(null);

  const setMatch = useCallback((nextPatient, nextData) => {
    setPatient(nextPatient);
    setData(nextData);
  }, []);

  const clearMatch = useCallback(() => {
    setPatient(null);
    setData(null);
  }, []);

  return (
    <MatchContext.Provider value={{ patient, data, setMatch, clearMatch }}>
      {children}
    </MatchContext.Provider>
  );
}

export function useMatch() {
  const ctx = useContext(MatchContext);
  if (!ctx) throw new Error("useMatch must be used within MatchProvider");
  return ctx;
}
