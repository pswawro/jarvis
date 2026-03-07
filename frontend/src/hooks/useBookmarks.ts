import { useState, useCallback } from "react";
import type { BookmarkState, Period, Filters } from "../types";

const STORAGE_KEY = "jarvis_bookmarks";

function loadBookmarks(): BookmarkState[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveBookmarks(bookmarks: BookmarkState[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(bookmarks));
}

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState<BookmarkState[]>(loadBookmarks);

  const addBookmark = useCallback((label: string, period: Period, filters: Filters, activeView: number) => {
    const bm: BookmarkState = {
      id: `bm_${Date.now()}`,
      label,
      period,
      filters,
      activeView,
      createdAt: new Date().toISOString(),
    };
    setBookmarks((prev) => {
      const next = [bm, ...prev].slice(0, 20);
      saveBookmarks(next);
      return next;
    });
  }, []);

  const removeBookmark = useCallback((id: string) => {
    setBookmarks((prev) => {
      const next = prev.filter((b) => b.id !== id);
      saveBookmarks(next);
      return next;
    });
  }, []);

  return { bookmarks, addBookmark, removeBookmark };
}
