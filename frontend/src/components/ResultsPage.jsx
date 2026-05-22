import { useMemo, useState } from "react";
import TrialCard from "./TrialCard.jsx";

// Approximate distance pulled from the location string ("… — 2.1 miles away").
function distanceOf(trial) {
  const m = /([\d.]+)\s*miles?/i.exec(trial.location || "");
  return m ? parseFloat(m[1]) : Number.POSITIVE_INFINITY;
}

// Higher phase number = later stage; used for the "phase" sort.
function phaseRank(trial) {
  const p = (trial.phase || "").toUpperCase();
  if (p.includes("IV") || p.includes("4")) return 4;
  if (p.includes("III") || p.includes("3")) return 3;
  if (p.includes("II") || p.includes("2")) return 2;
  if (p.includes("I") || p.includes("1")) return 1;
  return 0;
}

const SORTS = {
  fit: { label: "Best fit", fn: (a, b) => b.fit_score - a.fit_score },
  distance: { label: "Nearest", fn: (a, b) => distanceOf(a) - distanceOf(b) },
  phase: { label: "Latest phase", fn: (a, b) => phaseRank(b) - phaseRank(a) },
};

export default function ResultsPage({ data }) {
  const [sortKey, setSortKey] = useState("fit");

  const sorted = useMemo(() => {
    return [...(data.trials || [])].sort(SORTS[sortKey].fn);
  }, [data.trials, sortKey]);

  const count = data.trials?.length || 0;

  return (
    <div className="results">
      <header className="results__header">
        <div>
          <p className="results__eyebrow">Results for</p>
          <h1 className="results__condition">
            {data.condition_searched || "your search"}
          </h1>
          <p className="results__context">
            {data.search_context ||
              `${count} ${count === 1 ? "trial" : "trials"} found`}
          </p>
        </div>

        <div className="results__sort">
          <label htmlFor="sort" className="results__sort-label">
            Sort by
          </label>
          <select
            id="sort"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value)}
            className="results__sort-select"
          >
            {Object.entries(SORTS).map(([key, { label }]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className="results__list">
        {sorted.map((trial) => (
          <TrialCard key={trial.nct_id || trial.rank} trial={trial} />
        ))}
      </div>

      <footer className="results__disclaimer">
        <p>{data.disclaimer}</p>
      </footer>
    </div>
  );
}
