import { useState } from "react";
import { useNavigate } from "react-router-dom";
import IntakeForm from "../components/IntakeForm.jsx";
import ConversationalIntake from "../components/ConversationalIntake.jsx";
import { useProfiles } from "../context/ProfileContext.jsx";

export default function Home() {
  const [showForm, setShowForm] = useState(false);
  const [mode, setMode] = useState("form"); // 'form' | 'chat'
  const [prefill, setPrefill] = useState(false);
  const navigate = useNavigate();
  const { selected } = useProfiles();

  function handleSubmit(patientData) {
    // Hand the profile to the Results route via router state, then let
    // Results.jsx fire the API call and render loading/results/error.
    navigate("/results", { state: { patient: patientData } });
  }

  function startIntake(usePrefill = false) {
    setPrefill(usePrefill);
    setShowForm(true);
    // Defer scroll until the form has mounted.
    requestAnimationFrame(() => {
      document
        .getElementById("intake")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  return (
    <div className="home">
      <section className="hero">
        <p className="hero__eyebrow">Powered by real-time trial data</p>
        <h1 className="hero__title">
          Find clinical trials that <em>actually fit you</em>
        </h1>
        <p className="hero__subtitle">
          Describe your condition in plain English. We&apos;ll match you to
          recruiting trials and explain why each one might be right for you.
        </p>
        <div className="hero__cta">
          <button className="btn btn--primary btn--lg" onClick={() => startIntake(false)}>
            Get started
          </button>
          {selected && (
            <button
              className="btn btn--ghost btn--lg"
              onClick={() => startIntake(true)}
            >
              Search for {selected.label}
            </button>
          )}
        </div>

        <ul className="hero__stats" aria-label="At a glance">
          <li>
            <strong>500,000+</strong>
            <span>trials searched</span>
          </li>
          <li>
            <strong>Updated daily</strong>
            <span>from live sources</span>
          </li>
          <li>
            <strong>Free</strong>
            <span>to use</span>
          </li>
        </ul>

        <div className="hero__badges" aria-hidden="true">
          <span className="trust-badge">Real-time trial data</span>
          <span className="trust-badge">Plain-English matches</span>
          <span className="trust-badge">Sources on every result</span>
        </div>
      </section>

      {showForm && (
        <section id="intake" className="intake-section" aria-label="Patient intake">
          <div className="mode-toggle" role="tablist" aria-label="Intake style">
            <button
              role="tab"
              aria-selected={mode === "form"}
              className={"mode-toggle__btn" + (mode === "form" ? " is-active" : "")}
              onClick={() => setMode("form")}
            >
              Form intake
            </button>
            <button
              role="tab"
              aria-selected={mode === "chat"}
              className={"mode-toggle__btn" + (mode === "chat" ? " is-active" : "")}
              onClick={() => setMode("chat")}
            >
              Chat with our assistant
            </button>
          </div>

          {mode === "form" ? (
            <IntakeForm
              onSubmit={handleSubmit}
              initial={prefill && selected ? selected : null}
            />
          ) : (
            <ConversationalIntake onComplete={handleSubmit} />
          )}
        </section>
      )}

      <p className="home__disclaimer">
        TrialFinder is an informational tool and does not provide medical
        advice. Always consult a qualified healthcare provider about treatment
        and trial decisions.
      </p>
    </div>
  );
}
