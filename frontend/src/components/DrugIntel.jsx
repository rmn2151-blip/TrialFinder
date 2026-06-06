import { useState } from "react";
import { getDrugIntel } from "../api/client.js";

export default function DrugIntel({ drug }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  if (!drug) return null;

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && data === null && status !== "loading") {
      setStatus("loading");
      try {
        const intel = await getDrugIntel(drug);
        setData(intel);
        setStatus("done");
      } catch (err) {
        setError(err.message);
        setStatus("error");
      }
    }
  }

  return (
    <div className="reputation">
      <button
        type="button"
        className="disclosure"
        aria-expanded={open}
        onClick={toggle}
      >
        {open ? "Hide" : "Show"} drug intel: {drug}
      </button>

      {open && (
        <div className="reputation__body">
          {status === "loading" && (
            <p className="reputation__loading">Pulling phase results, conference signals, and FDA designations…</p>
          )}
          {status === "error" && (
            <p className="intake__error" role="alert">{error}</p>
          )}
          {status === "done" && data && (
            <>
              {data.summary && <p className="reputation__paragraph">{data.summary}</p>}

              {data.fda_designations && data.fda_designations.length > 0 && (
                <section>
                  <h5 className="reputation__h">FDA designations</h5>
                  <ul className="biomarker__chips">
                    {data.fda_designations.map((d, i) => (
                      <li key={i} className="biomarker__chip" title={d.date || ""}>
                        {d.url ? (
                          <a href={d.url} target="_blank" rel="noopener noreferrer" style={{color: "inherit", textDecoration: "none"}}>
                            {d.label}{d.date ? ` · ${d.date}` : ""}
                          </a>
                        ) : (
                          <>{d.label}{d.date ? ` · ${d.date}` : ""}</>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {data.phase_results && data.phase_results.length > 0 && (
                <section>
                  <h5 className="reputation__h">Phase results so far</h5>
                  <ul className="reputation__list">
                    {data.phase_results.map((p, i) => (
                      <li key={i}>
                        <strong>{p.phase}:</strong> {p.summary}
                        {p.url && (
                          <>
                            {" "}
                            <a href={p.url} target="_blank" rel="noopener noreferrer">↗</a>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {data.conference_signals && data.conference_signals.length > 0 && (
                <section>
                  <h5 className="reputation__h">Conference signals</h5>
                  <ul className="reputation__list">
                    {data.conference_signals.map((s, i) => (
                      <li key={i}>
                        <strong>{s.conference}:</strong> {s.finding}
                        {s.url && (
                          <>
                            {" "}
                            <a href={s.url} target="_blank" rel="noopener noreferrer">↗</a>
                          </>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {data.side_effect_signals && (
                <section>
                  <h5 className="reputation__h">Side effect signals</h5>
                  <p className="reputation__paragraph">{data.side_effect_signals}</p>
                </section>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
