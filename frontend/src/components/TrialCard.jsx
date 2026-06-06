import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { useProfiles } from "../context/ProfileContext.jsx";
import { addToWatchlist } from "../api/client.js";
import SiteReputation from "./SiteReputation.jsx";
import DrugIntel from "./DrugIntel.jsx";
import ClarifyEligibility from "./ClarifyEligibility.jsx";

// Best-effort drug-name extraction from a trial title — looks for known KRAS
// inhibitor names, otherwise falls back to the first capitalized word before
// "in", "Trial", or "Study".
const KNOWN_DRUGS = [
  "sotorasib", "adagrasib", "pembrolizumab", "durvalumab", "atezolizumab",
  "trastuzumab", "osimertinib", "imatinib", "rituximab", "venetoclax",
  "lorlatinib", "alectinib", "nivolumab", "ipilimumab",
];

function extractDrugName(title) {
  if (!title) return null;
  const lower = title.toLowerCase();
  for (const d of KNOWN_DRUGS) {
    if (lower.includes(d)) return d;
  }
  // Fallback: words ending in common drug suffixes
  const m = title.match(/\b([A-Z][a-z]+(?:nib|mab|tinib|cilib|rasib|olol|inib))\b/);
  return m ? m[1].toLowerCase() : null;
}

function fitTier(score) {
  if (score >= 80) return { label: "Strong fit", cls: "fit--strong" };
  if (score >= 60) return { label: "Potential fit", cls: "fit--medium" };
  return { label: "Weak fit", cls: "fit--weak" };
}

function barClass(score) {
  if (score >= 80) return "bar--strong";
  if (score >= 60) return "bar--medium";
  return "bar--weak";
}

export default function TrialCard({ trial, patient }) {
  const [showEligibility, setShowEligibility] = useState(false);
  const [saveState, setSaveState] = useState("idle"); // idle | saving | saved | error
  const [saveMsg, setSaveMsg] = useState("");

  const { isAuthed } = useAuth();
  const { selected } = useProfiles();
  const navigate = useNavigate();

  const tier = fitTier(trial.fit_score);
  const ctgovUrl =
    trial.source_url ||
    (trial.nct_id ? `https://clinicaltrials.gov/study/${trial.nct_id}` : null);

  async function handleSave() {
    if (!isAuthed) {
      navigate("/login", { state: { from: "/results" } });
      return;
    }
    if (!selected) {
      setSaveState("error");
      setSaveMsg("Create or select a profile first.");
      return;
    }
    if (!trial.nct_id) {
      setSaveState("error");
      setSaveMsg("This trial has no NCT ID to track.");
      return;
    }
    setSaveState("saving");
    try {
      await addToWatchlist({
        profile_id: selected.id,
        nct_id: trial.nct_id,
        title: trial.title,
        source_url: ctgovUrl,
      });
      setSaveState("saved");
      setSaveMsg(`Saved to ${selected.label}'s watchlist`);
    } catch (err) {
      setSaveState("error");
      setSaveMsg(err.message);
    }
  }

  return (
    <article className="trial-card">
      <div className="trial-card__head">
        <span className="trial-card__rank" aria-label={`Rank ${trial.rank}`}>
          #{trial.rank}
        </span>
        <div className={`fit ${tier.cls}`} title={`Fit score ${trial.fit_score} of 100`}>
          <span className="fit__score">{trial.fit_score}</span>
          <span className="fit__label">{tier.label}</span>
        </div>
      </div>

      <h3 className="trial-card__title">{trial.title}</h3>

      <div className="trial-card__pills">
        {trial.phase && <span className="pill">{trial.phase}</span>}
        {trial.status && (
          <span
            className={
              "pill" +
              (/recruit|enrolling/i.test(trial.status) ? " pill--recruiting" : "")
            }
          >
            {trial.status}
          </span>
        )}
        {trial.intervention_type && (
          <span className="pill pill--muted">{trial.intervention_type}</span>
        )}
        {/* Washout availability */}
        {(() => {
          if (trial.washout_weeks === 0)
            return <span className="pill pill--available">✓ Available now</span>;
          if (trial.earliest_enrollable_date) {
            const dt = new Date(trial.earliest_enrollable_date);
            const isPast = dt.getTime() <= Date.now();
            return isPast ? (
              <span className="pill pill--available">✓ Available now</span>
            ) : (
              <span className="pill pill--soon">
                Available {dt.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
              </span>
            );
          }
          if (trial.washout_weeks && trial.washout_weeks > 0)
            return (
              <span className="pill pill--soon">
                {trial.washout_weeks}-week washout
              </span>
            );
          return null;
        })()}
      </div>

      {/* Biomarker match callout — clinically the strongest signal */}
      {trial.biomarker_match && (
        <div className="biomarker">
          <span className="biomarker__icon" aria-hidden="true">🧬</span>
          <div>
            <h4 className="biomarker__title">Biomarker fit</h4>
            <p>{trial.biomarker_match}</p>
            {trial.matched_biomarkers && trial.matched_biomarkers.length > 0 && (
              <ul className="biomarker__chips">
                {trial.matched_biomarkers.map((b, i) => (
                  <li key={i} className="biomarker__chip">{b}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      <div className="trial-card__why">
        <h4 className="trial-card__why-title">Why this fits you</h4>
        <p>{trial.why_this_fits}</p>
      </div>

      {trial.plain_english && (
        <div className="trial-card__plain">
          <h4 className="trial-card__sub">What they&apos;re testing</h4>
          <p>{trial.plain_english}</p>
        </div>
      )}

      {/* Confidence breakdown — per-axis sub-scores with sources */}
      {trial.score_breakdown && trial.score_breakdown.length > 0 && (
        <div className="breakdown">
          <h4 className="trial-card__sub">Confidence breakdown</h4>
          <ul className="breakdown__list">
            {trial.score_breakdown.map((c, i) => (
              <li key={i} className="breakdown__item">
                <div className="breakdown__row">
                  <span className="breakdown__label">
                    {c.source_url ? (
                      <a href={c.source_url} target="_blank" rel="noopener noreferrer">
                        {c.label}
                      </a>
                    ) : (
                      c.label
                    )}
                  </span>
                  <span className="breakdown__score">{c.score}</span>
                </div>
                <div className="bar">
                  <div
                    className={`bar__fill ${barClass(c.score)}`}
                    style={{ width: `${c.score}%` }}
                  />
                </div>
                {c.reason && <p className="breakdown__reason">{c.reason}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <dl className="trial-card__meta">
        {trial.location && (
          <div>
            <dt>Location</dt>
            <dd>{trial.location}</dd>
          </div>
        )}
        {trial.sponsor && (
          <div>
            <dt>Sponsor</dt>
            <dd>{trial.sponsor}</dd>
          </div>
        )}
      </dl>

      {trial.warning_flags && trial.warning_flags.length > 0 && (
        <ul className="trial-card__flags" aria-label="Things to be aware of">
          {trial.warning_flags.map((flag, i) => (
            <li key={i} className="flag">
              <span aria-hidden="true">⚠</span> {flag}
            </li>
          ))}
        </ul>
      )}

      {trial.eligibility_summary && (
        <div className="trial-card__eligibility">
          <button
            type="button"
            className="disclosure"
            aria-expanded={showEligibility}
            onClick={() => setShowEligibility((v) => !v)}
          >
            {showEligibility ? "Hide" : "Show"} eligibility summary
          </button>
          {showEligibility && (
            <p className="trial-card__eligibility-body">{trial.eligibility_summary}</p>
          )}
        </div>
      )}

      {/* Clarify eligibility — shown when ambiguity is implied */}
      {patient && (trial.fit_score < 80 || /uncertain|unclear/i.test(trial.status || "")) && (
        <ClarifyEligibility patient={patient} trial={trial} />
      )}

      {/* Site / PI reputation — lazy-loaded on expand */}
      {trial.sponsor && <SiteReputation sponsor={trial.sponsor} pi={trial.principal_investigator} />}

      {/* Drug intel — derive the drug name from the trial title or interventions */}
      {(() => {
        const drug = trial.drug_name || extractDrugName(trial.title);
        return drug ? <DrugIntel drug={drug} /> : null;
      })()}

      {/* Citations */}
      {trial.citations && trial.citations.length > 0 && (
        <div className="citations">
          <span className="citations__label">Sources:</span>
          {trial.citations.map((c, i) => (
            <a
              key={i}
              className="citations__link"
              href={c.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              {c.label}
            </a>
          ))}
        </div>
      )}

      <div className="trial-card__foot">
        {ctgovUrl ? (
          <a
            className="btn btn--link"
            href={ctgovUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            View on ClinicalTrials.gov{trial.nct_id ? ` (${trial.nct_id})` : ""} ↗
          </a>
        ) : (
          <span className="trial-card__nosrc">No source link available</span>
        )}

        <button
          className={
            "btn btn--sm " +
            (saveState === "saved" ? "btn--ghost is-saved" : "btn--primary")
          }
          onClick={handleSave}
          disabled={saveState === "saving" || saveState === "saved"}
        >
          {saveState === "saved"
            ? "✓ Saved"
            : saveState === "saving"
            ? "Saving…"
            : isAuthed
            ? "Save to watchlist"
            : "Log in to save"}
        </button>
      </div>

      {saveMsg && (
        <p
          className={
            "trial-card__savemsg" + (saveState === "error" ? " is-error" : "")
          }
          role="status"
        >
          {saveMsg}
        </p>
      )}
    </article>
  );
}
