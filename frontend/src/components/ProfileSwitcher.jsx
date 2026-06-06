import { useState } from "react";
import { useProfiles } from "../context/ProfileContext.jsx";
import NewProfileModal from "./NewProfileModal.jsx";

export default function ProfileSwitcher() {
  const { profiles, selectedId, selectProfile } = useProfiles();
  const [showModal, setShowModal] = useState(false);

  function handleChange(e) {
    if (e.target.value === "__new__") {
      setShowModal(true);
      return;
    }
    selectProfile(Number(e.target.value));
  }

  return (
    <div className="profile-switcher">
      <label htmlFor="profile-select" className="profile-switcher__label">
        Profile
      </label>
      <select
        id="profile-select"
        className="profile-switcher__select"
        value={selectedId || ""}
        onChange={handleChange}
      >
        {profiles.length === 0 && (
          <option value="" disabled>
            No profiles yet
          </option>
        )}
        {profiles.map((p) => (
          <option key={p.id} value={p.id}>
            {p.label} — {p.condition.slice(0, 32)}
            {p.condition.length > 32 ? "…" : ""}
          </option>
        ))}
        <option value="__new__">+ New profile…</option>
      </select>

      {showModal && <NewProfileModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
