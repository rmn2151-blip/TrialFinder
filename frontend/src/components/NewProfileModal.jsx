import { useState } from "react";
import { useProfiles } from "../context/ProfileContext.jsx";

export default function NewProfileModal({ onClose }) {
  const { create } = useProfiles();
  const [label, setLabel] = useState("");
  const [condition, setCondition] = useState("");
  const [location, setLocation] = useState("");
  const [treatmentHistory, setTreatmentHistory] = useState("");
  const [age, setAge] = useState("");
  const [biomarkers, setBiomarkers] = useState([]);
  const [bioInput, setBioInput] = useState("");
  const [lastTreatmentDate, setLastTreatmentDate] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function addBiomarker() {
    const b = bioInput.trim();
    if (b && !biomarkers.includes(b)) setBiomarkers((m) => [...m, b]);
    setBioInput("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (label.trim().length < 1) return setError("Please give this profile a name.");
    if (condition.trim().length < 3) return setError("Please enter a condition.");
    if (location.trim().length < 2) return setError("Please enter a location.");
    setBusy(true);
    try {
      const payload = {
        label: label.trim(),
        condition: condition.trim(),
        location: location.trim(),
        medications: [],
      };
      if (treatmentHistory.trim()) payload.treatment_history = treatmentHistory.trim();
      if (age !== "") payload.age = Number(age);
      if (biomarkers.length) payload.biomarkers = biomarkers;
      if (lastTreatmentDate) payload.last_treatment_date = lastTreatmentDate;
      await create(payload);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="New profile">
      <div className="modal">
        <div className="modal__head">
          <h2 className="modal__title">New patient profile</h2>
          <button className="modal__close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p className="modal__hint">
          Create a profile for yourself or someone you care for. You can save trials
          and get alerts per profile.
        </p>
        <form onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span className="field__label">Profile name</span>
            <input
              className="field__input"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Myself, Mom, Dad"
              autoFocus
            />
          </label>
          <label className="field">
            <span className="field__label">Condition</span>
            <input
              className="field__input"
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              placeholder="e.g. stage 3 non-small cell lung cancer"
            />
          </label>
          <label className="field">
            <span className="field__label">Location</span>
            <input
              className="field__input"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="City, state or ZIP"
            />
          </label>
          <label className="field">
            <span className="field__label">
              Treatment history <span className="field__opt">(optional)</span>
            </span>
            <textarea
              className="field__input field__textarea"
              value={treatmentHistory}
              onChange={(e) => setTreatmentHistory(e.target.value)}
              rows={2}
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
              min={0}
              max={120}
            />
          </label>

          <label className="field">
            <span className="field__label">
              Biomarkers <span className="field__opt">(optional)</span>
            </span>
            <input
              className="field__input"
              value={bioInput}
              onChange={(e) => setBioInput(e.target.value)}
              onBlur={addBiomarker}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === ",") {
                  e.preventDefault();
                  addBiomarker();
                }
              }}
              placeholder="e.g. KRAS G12C+, HER2 amplified"
            />
            {biomarkers.length > 0 && (
              <ul className="tag-list">
                {biomarkers.map((b) => (
                  <li key={b} className="tag">
                    {b}
                    <button
                      type="button"
                      className="tag__remove"
                      onClick={() => setBiomarkers((m) => m.filter((x) => x !== b))}
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
          </label>

          {error && (
            <p className="intake__error" role="alert">
              {error}
            </p>
          )}

          <div className="modal__actions">
            <button type="button" className="btn btn--ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn--primary" disabled={busy}>
              {busy ? "Creating…" : "Create profile"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
