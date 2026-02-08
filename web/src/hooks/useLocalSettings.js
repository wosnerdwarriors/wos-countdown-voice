import { useEffect, useState } from "react";

const SETTINGS_KEY = "wos-rally-local-settings-v1";

export function useLocalSettings() {
  const [beepLevel, setBeepLevel] = useState(70); // 0–100
  const [ttsLevel, setTtsLevel] = useState(80); // 0–100
  const [selectedIds, setSelectedIds] = useState([]);

  // Load on mount.
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(SETTINGS_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (typeof parsed.beepLevel === "number") setBeepLevel(parsed.beepLevel);
      if (typeof parsed.ttsLevel === "number") setTtsLevel(parsed.ttsLevel);
      if (Array.isArray(parsed.selectedIds)) setSelectedIds(parsed.selectedIds);
    } catch (e) {
      console.warn("Failed to read local settings", e);
    }
  }, []);

  // Persist on change.
  useEffect(() => {
    try {
      const data = {
        beepLevel,
        ttsLevel,
        selectedIds,
      };
      window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(data));
    } catch (e) {
      console.warn("Failed to write local settings", e);
    }
  }, [beepLevel, ttsLevel, selectedIds]);

  return {
    beepLevel,
    setBeepLevel,
    ttsLevel,
    setTtsLevel,
    selectedIds,
    setSelectedIds,
  };
}
