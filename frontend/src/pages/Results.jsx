import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { matchTrials } from "../api/client.js";
import { useMatch } from "../context/MatchContext.jsx";
import LoadingState from "../components/LoadingState.jsx";
import ResultsPage from "../components/ResultsPage.jsx";
import { ErrorState, EmptyState } from "../components/ErrorState.jsx";

// Consider two profiles the same only when every ranking-relevant field
// matches. Any change (biomarkers, medications, age, treatment date, etc.)
// forces a fresh search so results always reflect what the user typed.
function samePatient(a, b) {
  if (!a || !b) return false;
  const norm = (p) => ({
    condition: (p.condition || "").trim(),
    location: (p.location || "").trim(),
    treatment_history: (p.treatment_history || "").trim(),
    age: p.age ?? null,
    medications: [...(p.medications || [])].sort(),
    biomarkers: [...(p.biomarkers || [])].sort(),
    last_treatment_date: p.last_treatment_date || null,
    additional_context: (p.additional_context || "").trim(),
  });
  return JSON.stringify(norm(a)) === JSON.stringify(norm(b));
}

export default function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const { patient: cachedPatient, data: cachedData, setMatch } = useMatch();

  // Prefer the patient we just came in with. Fall back to the cached one so
  // reloading /results without a fresh submission still shows something.
  const patient = location.state?.patient || cachedPatient;

  const [status, setStatus] = useState("loading"); // loading | done | error
  const [data, setData] = useState(cachedData);
  const [error, setError] = useState("");

  const runSearch = useCallback(async () => {
    setStatus("loading");
    setError("");
    try {
      const result = await matchTrials(patient);
      setData(result);
      setMatch(patient, result);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, [patient, setMatch]);

  useEffect(() => {
    // No patient at all: send them home.
    if (!patient) {
      navigate("/", { replace: true });
      return;
    }
    // If the cache already holds the same search, use it and skip the call.
    if (samePatient(patient, cachedPatient) && cachedData) {
      setData(cachedData);
      setStatus("done");
      return;
    }
    runSearch();
    // We intentionally leave cachedPatient/cachedData out of the deps: we
    // only want to compare them on entry, not re-run when they change later.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patient, navigate, runSearch]);

  if (!patient) return null;
  if (status === "loading") return <LoadingState />;
  if (status === "error") return <ErrorState message={error} onRetry={runSearch} />;
  if (status === "done" && (!data?.trials || data.trials.length === 0))
    return <EmptyState />;
  return <ResultsPage data={data} patient={patient} />;
}
