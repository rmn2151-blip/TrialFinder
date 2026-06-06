import { useState } from "react";

export default function ExcludedTrials({ excluded }) {
  const [open, setOpen] = useState(false);
  if (!excluded || excluded.length === 0) return null;

  return (
    <section className="excluded">
      <button
        type="button"
        className="excluded__toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? "▾" : "▸"} Why we ruled out {excluded.length} other{" "}
        {excluded.length === 1 ? "trial" : "trials"}
      </button>

      {open && (
        <ul className="excluded__list">
          {excluded.map((t, i) => (
            <li key={t.nct_id || i} className="excluded__item">
              <div className="excluded__head">
                <span className="excluded__title">{t.title}</span>
                {t.nct_id && (
                  <a
                    className="excluded__nct"
                    href={t.source_url || `https://clinicaltrials.gov/study/${t.nct_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t.nct_id}
                  </a>
                )}
              </div>
              <p className="excluded__reason">{t.reason}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
