import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import IntakeForm from "../components/IntakeForm.jsx";
import ConversationalIntake from "../components/ConversationalIntake.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { useProfiles } from "../context/ProfileContext.jsx";

export default function Home() {
  const [showForm, setShowForm] = useState(false);
  const [mode, setMode] = useState("form"); // 'form' | 'chat'
  // Auto-prefill from the currently selected profile whenever the user has one.
  // If they want a totally fresh search, they click "Start blank" below.
  const [useProfileData, setUseProfileData] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthed } = useAuth();
  const { selected, profiles } = useProfiles();

  const hasProfile = !!selected;
  const intakeRef = useRef(null);

  // Coming back from "Edit your search" on the results page: open the form
  // straight away, prefilled with what they searched last time.
  const editPatient = location.state?.editPatient || null;
  useEffect(() => {
    if (editPatient) {
      setShowForm(true);
      setUseProfileData(false);
      requestAnimationFrame(() => {
        intakeRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        intakeRef.current?.focus();
      });
    }
  }, [editPatient]);

  function handleSubmit(patientData) {
    navigate("/results", { state: { patient: patientData } });
  }

  function startIntake(prefill) {
    setUseProfileData(prefill);
    setShowForm(true);
    requestAnimationFrame(() => {
      intakeRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      intakeRef.current?.focus();
    });
  }

  function searchDirectly() {
    if (!selected) return;
    // Build a PatientProfile-shaped payload straight from the stored profile
    // and jump into the results page. No form step needed.
    const payload = {
      condition: selected.condition,
      location: selected.location,
      treatment_history: selected.treatment_history || "none",
      medications: selected.medications?.length ? selected.medications : ["none"],
    };
    if (selected.age != null) payload.age = selected.age;
    if (selected.biomarkers?.length) payload.biomarkers = selected.biomarkers;
    if (selected.last_treatment_date)
      payload.last_treatment_date = selected.last_treatment_date;
    if (selected.additional_context)
      payload.additional_context = selected.additional_context;
    handleSubmit(payload);
  }

  return (
    <div className="home">
      <section className="hero">
        <p className="hero__brand">
          <span className="hero__brand-mark" aria-hidden="true">✛</span>
          TrialFinder
        </p>
        <h1 className="hero__title">
          Find clinical trials that <em>actually fit you</em>
        </h1>
        <p className="hero__subtitle">
          Describe your condition in plain English. We will match you to
          recruiting trials and explain why each one might be right for you.
        </p>

        {hasProfile ? (
          <>
            <div className="hero__cta">
              <button className="btn btn--primary btn--lg" onClick={searchDirectly}>
                Search trials for {selected.label}
              </button>
              <button
                className="btn btn--ghost btn--lg"
                onClick={() => startIntake(true)}
              >
                Edit {selected.label}&apos;s details first
              </button>
            </div>
            <p className="hero__hint">
              Using saved profile: <strong>{selected.condition}</strong> in{" "}
              <strong>{selected.location}</strong>.
              {profiles.length > 1 && " Switch profiles in the header above."}
              {" "}
              <button className="btn--link" onClick={() => startIntake(false)}>
                Start a blank search instead
              </button>
            </p>
          </>
        ) : (
          <>
            <div className="hero__cta">
              <button className="btn btn--primary btn--lg" onClick={() => startIntake(false)}>
                Get started
              </button>
              {!isAuthed && (
                <Link to="/login" className="btn btn--ghost btn--lg">
                  Log in
                </Link>
              )}
            </div>
            {isAuthed && (
              <p className="hero__hint">
                Tip: create a profile from the header to save your details for
                next time.
              </p>
            )}
          </>
        )}

        <ul className="hero__stats" aria-label="At a glance">
          <li>
            <strong>64,000+</strong>
            <span>recruiting trials on ClinicalTrials.gov</span>
          </li>
          <li>
            <strong>Updated daily</strong>
            <span>from live sources</span>
          </li>
          <li>
            <strong>Free</strong>
            <span>no account needed to search</span>
          </li>
        </ul>
      </section>

      {showForm && (
        <section
          id="intake"
          ref={intakeRef}
          tabIndex={-1}
          className="intake-section"
          aria-label="Patient intake"
        >
          <div
            className="mode-toggle"
            role="tablist"
            aria-label="Intake style"
            aria-describedby="mode-toggle-hint"
          >
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
          <p id="mode-toggle-hint" className="mode-toggle__hint">
            Same questions either way — fill in a short form, or answer them one at a
            time in a conversation. Pick whichever feels easier right now.
          </p>

          {mode === "form" ? (
            <IntakeForm
              onSubmit={handleSubmit}
              initial={
                editPatient || (useProfileData && selected ? selected : null)
              }
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
