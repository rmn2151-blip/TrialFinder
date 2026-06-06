import { useState } from "react";
import { clarifyEligibility } from "../api/client.js";

export default function ClarifyEligibility({ patient, trial }) {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState([]); // [{question, answer}]
  const [current, setCurrent] = useState(null); // {question, remaining}
  const [verdict, setVerdict] = useState(null);
  const [input, setInput] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function start() {
    setOpen(true);
    if (current || verdict) return;
    setBusy(true);
    try {
      const result = await clarifyEligibility({ patient, trial, history: [] });
      if (result.verdict === "ask") {
        setCurrent({ question: result.question, remaining: result.remaining });
      } else {
        setVerdict(result);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitAnswer(e) {
    e.preventDefault();
    if (!input.trim() || busy) return;
    setError("");
    const newHistory = [...history, { question: current.question, answer: input.trim() }];
    setHistory(newHistory);
    setInput("");
    setCurrent(null);
    setBusy(true);
    try {
      const result = await clarifyEligibility({ patient, trial, history: newHistory });
      if (result.verdict === "ask") {
        setCurrent({ question: result.question, remaining: result.remaining });
      } else {
        setVerdict(result);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="clarify">
      {!open ? (
        <button type="button" className="disclosure" onClick={start}>
          Help us check your eligibility →
        </button>
      ) : (
        <div className="clarify__body">
          <h5 className="reputation__h">Eligibility check</h5>

          <ul className="clarify__history">
            {history.map((qa, i) => (
              <li key={i}>
                <p className="clarify__q">{qa.question}</p>
                <p className="clarify__a">↳ {qa.answer}</p>
              </li>
            ))}
          </ul>

          {error && <p className="intake__error">{error}</p>}

          {verdict ? (
            <div
              className={
                "clarify__verdict " +
                (verdict.verdict === "eligible"
                  ? "is-eligible"
                  : verdict.verdict === "ineligible"
                  ? "is-ineligible"
                  : "is-stop")
              }
            >
              <strong>
                {verdict.verdict === "eligible"
                  ? "✓ Likely eligible"
                  : verdict.verdict === "ineligible"
                  ? "✗ Likely not eligible"
                  : "↻ Confirm with the study team"}
              </strong>
              {verdict.reason && <p>{verdict.reason}</p>}
            </div>
          ) : current ? (
            <form className="clarify__form" onSubmit={submitAnswer}>
              <p className="clarify__q">
                {current.question}{" "}
                <span className="clarify__remaining">
                  ({current.remaining} question{current.remaining === 1 ? "" : "s"} left)
                </span>
              </p>
              <div className="clarify__input">
                <input
                  className="field__input"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Your answer…"
                  disabled={busy}
                  autoFocus
                />
                <button type="submit" className="btn btn--primary btn--sm" disabled={busy || !input.trim()}>
                  {busy ? "…" : "Send"}
                </button>
              </div>
            </form>
          ) : busy ? (
            <p className="reputation__loading">Thinking…</p>
          ) : null}
        </div>
      )}
    </div>
  );
}
