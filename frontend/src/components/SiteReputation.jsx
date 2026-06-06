import { useState } from "react";
import { getReputation } from "../api/client.js";

export default function SiteReputation({ sponsor, pi }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | loading | done | error
  const [error, setError] = useState("");

  if (!sponsor) return null;

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && data === null && status !== "loading") {
      setStatus("loading");
      try {
        const rep = await getReputation(sponsor, pi);
        setData(rep);
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
        {open ? "Hide" : "Show"} site reputation for {sponsor}
      </button>

      {open && (
        <div className="reputation__body">
          {status === "loading" && (
            <p className="reputation__loading">Looking up {sponsor}…</p>
          )}

          {status === "error" && (
            <p className="intake__error" role="alert">
              {error}
            </p>
          )}

          {status === "done" && data && (
            <>
              {/* Warnings shown first — they're the most important signal */}
              {data.warnings && data.warnings.length > 0 && (
                <ul className="warnings" aria-label="Serious warnings">
                  {data.warnings.map((w, i) => (
                    <li
                      key={i}
                      className={
                        "warning" +
                        (w.severity === "warning" ? " warning--severe" : "")
                      }
                    >
                      <span aria-hidden="true">⚠</span>
                      <div>
                        <strong>{w.label}</strong>
                        {w.date && <span className="warning__date"> · {w.date}</span>}
                        {w.url && (
                          <>
                            {" "}
                            <a href={w.url} target="_blank" rel="noopener noreferrer">
                              source ↗
                            </a>
                          </>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              {data.summary && (
                <p className="reputation__summary">{data.summary}</p>
              )}
              {data.hospital_reputation && (
                <p className="reputation__paragraph">{data.hospital_reputation}</p>
              )}

              {data.publications && data.publications.length > 0 && (
                <section>
                  <h5 className="reputation__h">Selected publications</h5>
                  <ul className="reputation__list">
                    {data.publications.map((p, i) => (
                      <li key={i}>
                        {p.url ? (
                          <a href={p.url} target="_blank" rel="noopener noreferrer">
                            {p.title}
                          </a>
                        ) : (
                          p.title
                        )}
                        {p.year && <span className="reputation__year"> · {p.year}</span>}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {data.recent_press && data.recent_press.length > 0 && (
                <section>
                  <h5 className="reputation__h">Recent press</h5>
                  <ul className="reputation__list">
                    {data.recent_press.map((n, i) => (
                      <li key={i}>
                        {n.url ? (
                          <a href={n.url} target="_blank" rel="noopener noreferrer">
                            {n.title}
                          </a>
                        ) : (
                          n.title
                        )}
                        {n.date && <span className="reputation__year"> · {n.date}</span>}
                        {n.snippet && (
                          <div className="reputation__snippet">{n.snippet}</div>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {data.sources && data.sources.length > 0 && (
                <p className="reputation__sources">
                  <span className="citations__label">Sources:</span>{" "}
                  {data.sources.map((s, i) => (
                    <a
                      key={i}
                      className="citations__link"
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {s.label}
                    </a>
                  ))}
                </p>
              )}

              {data.cached && (
                <p className="reputation__cached">Cached result · refreshed hourly.</p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
