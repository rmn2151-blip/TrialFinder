import { useState } from "react";

const COMMON_CONDITIONS = [
  "Lung Cancer",
  "Breast Cancer",
  "Leukemia",
  "Crohn's Disease",
  "Multiple Sclerosis",
  "Type 2 Diabetes",
  "Parkinson's Disease",
  "Rheumatoid Arthritis",
];

const STEPS = [
  "Condition",
  "Treatments",
  "Location & age",
  "Medications",
  "Biomarkers",
];

export default function IntakeForm({ onSubmit, initial = null }) {
  const [step, setStep] = useState(0);

  const [condition, setCondition] = useState(initial?.condition || "");
  const [treatmentHistory, setTreatmentHistory] = useState(
    initial?.treatment_history || ""
  );
  const [location, setLocation] = useState(initial?.location || "");
  const [age, setAge] = useState(initial?.age != null ? String(initial.age) : "");
  const [medications, setMedications] = useState(initial?.medications || []);
  const [medInput, setMedInput] = useState("");
  const [additionalContext, setAdditionalContext] = useState(
    initial?.additional_context || ""
  );
  const [biomarkers, setBiomarkers] = useState(initial?.biomarkers || []);
  const [bioInput, setBioInput] = useState("");
  const [lastTreatmentDate, setLastTreatmentDate] = useState(
    initial?.last_treatment_date || ""
  );
  const [error, setError] = useState("");

  const isLastStep = step === STEPS.length - 1;
  const progress = ((step + 1) / STEPS.length) * 100;

  function validateStep() {
    if (step === 0 && condition.trim().length < 3) {
      return "Please enter a condition (at least 3 characters).";
    }
    if (step === 2 && location.trim().length < 2) {
      return "Please enter a city, state, or ZIP code.";
    }
    if (step === 2 && age !== "" && (Number(age) < 0 || Number(age) > 120)) {
      return "Please enter a valid age between 0 and 120.";
    }
    return "";
  }

  function next() {
    const msg = validateStep();
    if (msg) {
      setError(msg);
      return;
    }
    setError("");
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }

  function back() {
    setError("");
    setStep((s) => Math.max(s - 1, 0));
  }

  function addMedication() {
    const med = medInput.trim();
    if (med && !medications.includes(med)) {
      setMedications((m) => [...m, med]);
    }
    setMedInput("");
  }

  function removeMedication(med) {
    setMedications((m) => m.filter((x) => x !== med));
  }

  function handleMedKeyDown(e) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addMedication();
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    const msg = validateStep();
    if (msg) {
      setError(msg);
      return;
    }
    // Build payload matching backend PatientProfile. Omit empty optionals.
    const payload = {
      condition: condition.trim(),
      location: location.trim(),
      medications,
    };
    if (treatmentHistory.trim()) payload.treatment_history = treatmentHistory.trim();
    if (age !== "") payload.age = Number(age);
    if (additionalContext.trim())
      payload.additional_context = additionalContext.trim();
    if (biomarkers.length) payload.biomarkers = biomarkers;
    if (lastTreatmentDate) payload.last_treatment_date = lastTreatmentDate;

    onSubmit(payload);
  }

  function addBiomarker() {
    const b = bioInput.trim();
    if (b && !biomarkers.includes(b)) setBiomarkers((m) => [...m, b]);
    setBioInput("");
  }

  function handleBioKeyDown(e) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addBiomarker();
    }
  }

  return (
    <form className="intake" onSubmit={handleSubmit} noValidate>
      <div className="intake__progress" role="group" aria-label="Form progress">
        <div className="intake__progress-track">
          <div
            className="intake__progress-fill"
            style={{ width: `${progress}%` }}
          />
        </div>
        <ol className="intake__steps">
          {STEPS.map((label, i) => (
            <li
              key={label}
              className={
                "intake__step" +
                (i === step ? " is-active" : "") +
                (i < step ? " is-done" : "")
              }
              aria-current={i === step ? "step" : undefined}
            >
              <span className="intake__step-num">{i + 1}</span>
              <span className="intake__step-label">{label}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Step 1 — Condition */}
      {step === 0 && (
        <fieldset className="intake__panel">
          <legend className="intake__legend">
            What condition are you looking for trials for?
          </legend>
          <label className="field">
            <span className="field__label">Condition or diagnosis</span>
            <input
              type="text"
              className="field__input"
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              placeholder="e.g. stage 3 non-small cell lung cancer"
              autoFocus
              maxLength={500}
            />
          </label>
          <div className="chips" role="group" aria-label="Common conditions">
            {COMMON_CONDITIONS.map((c) => (
              <button
                type="button"
                key={c}
                className={
                  "chip" + (condition === c ? " chip--selected" : "")
                }
                onClick={() => setCondition(c)}
              >
                {c}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      {/* Step 2 — Treatment history */}
      {step === 1 && (
        <fieldset className="intake__panel">
          <legend className="intake__legend">
            What treatments have you already tried?
          </legend>
          <label className="field">
            <span className="field__label">
              Treatment history <span className="field__opt">(optional)</span>
            </span>
            <textarea
              className="field__input field__textarea"
              value={treatmentHistory}
              onChange={(e) => setTreatmentHistory(e.target.value)}
              placeholder="e.g. carboplatin + paclitaxel, 6 cycles, then a PD-1 inhibitor"
              rows={5}
              maxLength={1000}
            />
            <span className="field__hint">
              Listing prior treatments helps us match trials that accept your
              treatment stage.
            </span>
          </label>
        </fieldset>
      )}

      {/* Step 3 — Location + age */}
      {step === 2 && (
        <fieldset className="intake__panel">
          <legend className="intake__legend">Where are you located?</legend>
          <label className="field">
            <span className="field__label">City, state, or ZIP code</span>
            <input
              type="text"
              className="field__input"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. New York, NY or 10065"
              maxLength={200}
            />
          </label>
          <label className="field field--narrow">
            <span className="field__label">
              Age <span className="field__opt">(optional)</span>
            </span>
            <input
              type="number"
              className="field__input"
              value={age}
              onChange={(e) => setAge(e.target.value)}
              placeholder="58"
              min={0}
              max={120}
            />
          </label>
        </fieldset>
      )}

      {/* Step 4 — Medications + additional context */}
      {step === 3 && (
        <fieldset className="intake__panel">
          <legend className="intake__legend">
            What medications are you currently taking?
          </legend>
          <label className="field">
            <span className="field__label">
              Current medications{" "}
              <span className="field__opt">(optional)</span>
            </span>
            <div className="tag-input">
              <input
                type="text"
                className="field__input"
                value={medInput}
                onChange={(e) => setMedInput(e.target.value)}
                onKeyDown={handleMedKeyDown}
                onBlur={addMedication}
                placeholder="Type a medication and press Enter"
                aria-describedby="med-hint"
              />
            </div>
            <span id="med-hint" className="field__hint">
              We use these to flag possible interactions or exclusion criteria.
            </span>
            {medications.length > 0 && (
              <ul className="tag-list" aria-label="Added medications">
                {medications.map((med) => (
                  <li key={med} className="tag">
                    {med}
                    <button
                      type="button"
                      className="tag__remove"
                      onClick={() => removeMedication(med)}
                      aria-label={`Remove ${med}`}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </label>

          <label className="field">
            <span className="field__label">
              Tell us more <span className="field__opt">(optional)</span>
            </span>
            <textarea
              className="field__input field__textarea"
              value={additionalContext}
              onChange={(e) => setAdditionalContext(e.target.value)}
              placeholder="ECOG status, insurance, or anything else relevant"
              rows={4}
              maxLength={2000}
            />
          </label>
        </fieldset>
      )}

      {/* Step 5 — Biomarkers + last treatment date */}
      {step === 4 && (
        <fieldset className="intake__panel">
          <legend className="intake__legend">
            Any biomarker results or recent treatment?
          </legend>
          <label className="field">
            <span className="field__label">
              Biomarkers <span className="field__opt">(optional)</span>
            </span>
            <input
              type="text"
              className="field__input"
              value={bioInput}
              onChange={(e) => setBioInput(e.target.value)}
              onKeyDown={handleBioKeyDown}
              onBlur={addBiomarker}
              placeholder="e.g. KRAS G12C+, HER2 amplified, BRCA1 mutation"
            />
            <span className="field__hint">
              Add one at a time. Biomarker matches are the #1 reason cancer
              trials accept or reject patients — sharing them dramatically
              improves match quality.
            </span>
            {biomarkers.length > 0 && (
              <ul className="tag-list" aria-label="Added biomarkers">
                {biomarkers.map((b) => (
                  <li key={b} className="tag">
                    {b}
                    <button
                      type="button"
                      className="tag__remove"
                      onClick={() =>
                        setBiomarkers((m) => m.filter((x) => x !== b))
                      }
                      aria-label={`Remove ${b}`}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </label>

          <label className="field field--narrow">
            <span className="field__label">
              Last treatment date <span className="field__opt">(optional)</span>
            </span>
            <input
              type="date"
              className="field__input"
              value={lastTreatmentDate}
              onChange={(e) => setLastTreatmentDate(e.target.value)}
            />
            <span className="field__hint">
              We use this to compute washout-period eligibility per trial.
            </span>
          </label>
        </fieldset>
      )}

      {error && (
        <p className="intake__error" role="alert">
          {error}
        </p>
      )}

      <div className="intake__nav">
        {step > 0 ? (
          <button type="button" className="btn btn--ghost" onClick={back}>
            Back
          </button>
        ) : (
          <span />
        )}

        {!isLastStep ? (
          <button type="button" className="btn btn--primary" onClick={next}>
            Continue
          </button>
        ) : (
          <button type="submit" className="btn btn--primary">
            Find trials
          </button>
        )}
      </div>
    </form>
  );
}
