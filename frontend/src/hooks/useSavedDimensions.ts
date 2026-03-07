import { useState, useCallback } from "react";
import type { LevelId, SavedDimension } from "../types";

const STORAGE_KEY = "jarvis_saved_dimensions";

function loadFromStorage(): SavedDimension[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveToStorage(items: SavedDimension[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

export function useSavedDimensions() {
  const [saved, setSaved] = useState<SavedDimension[]>(loadFromStorage);

  const save = useCallback((label: string, levels: LevelId[]) => {
    setSaved((prev) => {
      const next = [
        ...prev,
        {
          id: crypto.randomUUID(),
          label,
          levels,
          createdAt: new Date().toISOString(),
        },
      ];
      saveToStorage(next);
      return next;
    });
  }, []);

  const remove = useCallback((id: string) => {
    setSaved((prev) => {
      const next = prev.filter((s) => s.id !== id);
      saveToStorage(next);
      return next;
    });
  }, []);

  return { saved, save, remove };
}
