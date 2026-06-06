import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { matchTrials } from "../api/client.js";
import LoadingState from "../components/LoadingState.jsx";
import ResultsPage from "../components/ResultsPage.jsx";
import { ErrorState, EmptyState } from "../components/ErrorState.jsx";

export default function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const patient = location.state?.patient;

  const [status, setStatus] = useState("loading"); // loading | done | error
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const runSearch = useCallback(async () => {
    setStatus("loading");
    setError("");
    try {
      const result = await matchTrials(patient);
      setData(result);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, [patient]);

  useEffect(() => {
    // No profile in router state (e.g. user navigated here directly) — bounce home.
    if (!patient) {
      navigate("/", { replace: true });
      return;
    }
    runSearch();
  }, [patient, navigate, runSearch]);

  if (!patient) return null;
  if (status === "loading") return <LoadingState />;
  if (status === "error") return <ErrorState message={error} onRetry={runSearch} />;
  if (status === "done" && (!data?.trials || data.trials.length === 0))
    return <EmptyState />;
  return <ResultsPage data={data} patient={patient} />;
}
