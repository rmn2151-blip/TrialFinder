import { useState } from "react";

function fitTier(score) {
  if (score >= 80) return { label: "Strong fit", cls: "fit--strong" };
  if (score >= 60) return { label: "Potential fit", cls: "fit--medium" };
  return { label: "Weak fit", cls: "fit--weak" };
}

export default function TrialCard({ trial }) {
  const [showEligibility, setShowEligibility] = useState(false);
  const tier = fitTier(trial.fit_score);
  const ctgovUrl =
    trial.source_url ||
    (trial.nct_id
      ? `https://clinicaltrials.gov/study/${trial.nct_id}`
      : null);

  return (
    <article className="trial-card">
      <div className="trial-card__head">
        <span className="trial-card__rank" aria-label={`Rank ${trial.rank}`}>
          #{trial.rank}
        </span>
        <div
          className={`fit ${tier.cls}`}
          title={`Fit score ${trial.fit_score} of 100`}
        >
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
              (/recruit|enrolling/i.test(trial.status)
                ? " pill--recruiting"
                : "")
            }
          >
            {trial.status}
          </span>
        )}
        {trial.intervention_type && (
          <span className="pill pill--muted">{trial.intervention_type}</span>
        )}
      </div>

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
            <p className="trial-card__eligibility-body">
              {trial.eligibility_summary}
            </p>
          )}
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
            View on ClinicalTrials.gov
            {trial.nct_id ? ` (${trial.nct_id})` : ""} ↗
          </a>
        ) : (
          <span className="trial-card__nosrc">No source link available</span>
        )}
      </div>
    </article>
  );
}
