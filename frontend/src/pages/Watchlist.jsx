import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { useProfiles } from "../context/ProfileContext.jsx";
import {
  getWatchlist,
  removeFromWatchlist,
  updateWatchlistStatus,
} from "../api/client.js";

const ENROLLMENT_STATUSES = [
  ["interested", "Interested"],
  ["contacted", "Contacted"],
  ["waiting", "Waiting"],
  ["screened", "Screened"],
  ["enrolled", "Enrolled"],
  ["withdrawn", "Withdrawn"],
  ["declined", "Declined"],
];

function daysBetween(a, b) {
  if (!a || !b) return null;
  const ms = new Date(b).getTime() - new Date(a).getTime();
  if (isNaN(ms) || ms < 0) return null;
  return Math.round(ms / (1000 * 60 * 60 * 24));
}

function fmtDate(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return null;
  }
}

export default function Watchlist() {
  const { isAuthed, loading: authLoading } = useAuth();
  const { selected, profiles } = useProfiles();
  const navigate = useNavigate();

  const [trials, setTrials] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!selected) {
      setTrials([]);
      setStatus("done");
      return;
    }
    setStatus("loading");
    try {
      const data = await getWatchlist(selected.id);
      setTrials(data.trials || []);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }, [selected]);

  useEffect(() => {
    if (!authLoading && !isAuthed) {
      navigate("/login", { state: { from: "/watchlist" }, replace: true });
      return;
    }
    if (isAuthed) load();
  }, [authLoading, isAuthed, load, navigate]);

  async function handleRemove(id) {
    await removeFromWatchlist(id);
    setTrials((t) => t.filter((x) => x.id !== id));
  }

  async function handleStatusChange(id, newStatus) {
    try {
      const updated = await updateWatchlistStatus(id, newStatus);
      setTrials((ts) => ts.map((t) => (t.id === id ? updated : t)));
    } catch (err) {
      setError(err.message);
    }
  }

  // Personal "fast vs slow" stat — days between contacted and screened.
  const responseStats = (() => {
    const deltas = trials
      .filter((t) => t.enrollment_status && ["screened", "enrolled"].includes(t.enrollment_status))
      .map((t) => daysBetween(t.created_at, t.enrollment_changed_at))
      .filter((d) => d !== null);
    if (!deltas.length) return null;
    const avg = Math.round(deltas.reduce((a, b) => a + b, 0) / deltas.length);
    return { count: deltas.length, avg };
  })();

  if (authLoading || !isAuthed) return null;

  if (profiles.length === 0) {
    return (
      <div className="state-card">
        <h2 className="state-card__title">No profiles yet</h2>
        <p className="state-card__body">
          Create a patient profile to start saving trials. Use the “Profile” menu
          at the top, or run a search and create one along the way.
        </p>
        <div className="state-card__actions">
          <Link to="/" className="btn btn--primary">
            Find trials
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="watchlist">
      <header className="results__header">
        <div>
          <p className="results__eyebrow">Watchlist</p>
          <h1 className="results__condition">{selected?.label}</h1>
          <p className="results__context">
            {selected?.condition} · {trials.length}{" "}
            {trials.length === 1 ? "trial" : "trials"} saved
          </p>
        </div>
        <Link to="/" className="btn btn--ghost btn--sm">
          Find more trials
        </Link>
      </header>

      {status === "loading" && <p className="watchlist__note">Loading…</p>}
      {status === "error" && (
        <p className="intake__error" role="alert">
          {error}
        </p>
      )}

      {status === "done" && trials.length === 0 && (
        <div className="state-card">
          <h2 className="state-card__title">Nothing saved yet</h2>
          <p className="state-card__body">
            Run a search and click “Save to watchlist” on any trial. We&apos;ll
            email you when a saved trial&apos;s status, phase, sites, or completion
            date changes.
          </p>
          <div className="state-card__actions">
            <Link to="/" className="btn btn--primary">
              Find trials
            </Link>
          </div>
        </div>
      )}

      {responseStats && (
        <p className="watchlist__stats">
          Across your contacted trials, the average wait from save to first
          screening was <strong>{responseStats.avg} days</strong>{" "}
          ({responseStats.count} {responseStats.count === 1 ? "trial" : "trials"}).
        </p>
      )}

      {trials.length > 0 && (
        <ul className="watchlist__list">
          {trials.map((t) => (
            <li key={t.id} className="watch-row">
              <div className="watch-row__main">
                <a
                  className="watch-row__title"
                  href={t.source_url || `https://clinicaltrials.gov/study/${t.nct_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t.title}
                </a>
                <div className="watch-row__meta">
                  <span className="pill pill--muted">{t.nct_id}</span>
                  {t.last_status && (
                    <span
                      className={
                        "pill" +
                        (/recruit|enrolling/i.test(t.last_status)
                          ? " pill--recruiting"
                          : "")
                      }
                    >
                      {t.last_status}
                    </span>
                  )}
                  {t.last_phase && <span className="pill">{t.last_phase}</span>}
                  {fmtDate(t.last_change_at) && (
                    <span className="watch-row__changed">
                      Updated {fmtDate(t.last_change_at)}
                    </span>
                  )}
                </div>

                {/* Enrollment status dropdown */}
                <div className="watch-row__enrollment">
                  <label htmlFor={`enr-${t.id}`} className="watch-row__enr-label">
                    Your status:
                  </label>
                  <select
                    id={`enr-${t.id}`}
                    className="watch-row__enr-select"
                    value={t.enrollment_status || "interested"}
                    onChange={(e) => handleStatusChange(t.id, e.target.value)}
                  >
                    {ENROLLMENT_STATUSES.map(([v, label]) => (
                      <option key={v} value={v}>
                        {label}
                      </option>
                    ))}
                  </select>
                  {fmtDate(t.enrollment_changed_at) && (
                    <span className="watch-row__changed">
                      since {fmtDate(t.enrollment_changed_at)}
                    </span>
                  )}
                </div>

                {/* Results summary when the trial has completed and we've pulled it */}
                {t.results_summary && (
                  <div className="watch-row__results">
                    <span className="reputation__h">Results posted</span>
                    {t.results_headline && (
                      <p className="watch-row__results-headline">{t.results_headline}</p>
                    )}
                    <p>{t.results_summary}</p>
                    {t.results_journal_url && (
                      <a
                        href={t.results_journal_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn--link"
                      >
                        Read the paper ↗
                      </a>
                    )}
                  </div>
                )}
              </div>
              <button
                className="btn btn--ghost btn--sm"
                onClick={() => handleRemove(t.id)}
                aria-label={`Remove ${t.title} from watchlist`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <footer className="results__disclaimer">
        <p>
          We monitor saved trials daily via ClinicalTrials.gov and email you when
          something changes. This is informational only, not medical advice.
        </p>
      </footer>
    </div>
  );
}
