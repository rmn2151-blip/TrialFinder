import { createContext, useCallback, useContext, useEffect, useState } from "react";
import * as apiClient from "../api/client.js";
import { useAuth } from "./AuthContext.jsx";

const ProfileContext = createContext(null);

const SELECTED_KEY = "trialfinder_selected_profile";

export function ProfileProvider({ children }) {
  const { isAuthed } = useAuth();
  const [profiles, setProfiles] = useState([]);
  const [selectedId, setSelectedId] = useState(() => {
    const raw = (() => {
      try {
        return localStorage.getItem(SELECTED_KEY);
      } catch {
        return null;
      }
    })();
    return raw ? Number(raw) : null;
  });
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!isAuthed) {
      setProfiles([]);
      return [];
    }
    setLoading(true);
    try {
      const list = await apiClient.listProfiles();
      setProfiles(list);
      // Default the selection to the first profile if none/invalid is chosen.
      setSelectedId((cur) => {
        if (cur && list.some((p) => p.id === cur)) return cur;
        return list.length ? list[0].id : null;
      });
      return list;
    } finally {
      setLoading(false);
    }
  }, [isAuthed]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Persist the selected profile so it survives reloads.
  useEffect(() => {
    try {
      if (selectedId) localStorage.setItem(SELECTED_KEY, String(selectedId));
      else localStorage.removeItem(SELECTED_KEY);
    } catch {
      /* ignore */
    }
  }, [selectedId]);

  const create = useCallback(
    async (profile) => {
      const created = await apiClient.createProfile(profile);
      await refresh();
      setSelectedId(created.id);
      return created;
    },
    [refresh]
  );

  const remove = useCallback(
    async (profileId) => {
      await apiClient.deleteProfile(profileId);
      await refresh();
    },
    [refresh]
  );

  const selected = profiles.find((p) => p.id === selectedId) || null;

  return (
    <ProfileContext.Provider
      value={{
        profiles,
        selected,
        selectedId,
        selectProfile: setSelectedId,
        refresh,
        create,
        remove,
        loading,
      }}
    >
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfiles() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfiles must be used within ProfileProvider");
  return ctx;
}
