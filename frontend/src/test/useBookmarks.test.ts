import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useBookmarks } from "../hooks/useBookmarks";
import type { Filters, Period } from "../types";

const period: Period = { year: 2025, quarter: null };
const filters: Filters = {
  market_id: [],
  ta: [],
  product: [],
  comparator: "BUD",
  scale: "M",
  year: 2025,
  granularity: "year",
};

beforeEach(() => {
  localStorage.clear();
});

describe("useBookmarks", () => {
  it("starts with an empty list when localStorage is empty", () => {
    const { result } = renderHook(() => useBookmarks());
    expect(result.current.bookmarks).toEqual([]);
  });

  it("adds a bookmark", () => {
    const { result } = renderHook(() => useBookmarks());
    act(() => result.current.addBookmark("Test BM", period, filters, 0));
    expect(result.current.bookmarks).toHaveLength(1);
    expect(result.current.bookmarks[0].label).toBe("Test BM");
  });

  it("persists bookmarks to localStorage", () => {
    const { result } = renderHook(() => useBookmarks());
    act(() => result.current.addBookmark("Persisted", period, filters, 1));
    const stored = JSON.parse(localStorage.getItem("jarvis_bookmarks")!);
    expect(stored).toHaveLength(1);
    expect(stored[0].label).toBe("Persisted");
  });

  it("loads bookmarks from localStorage on init", () => {
    const existing = [
      { id: "bm_1", label: "Saved", period, filters, activeView: 0, createdAt: "2025-01-01T00:00:00Z" },
    ];
    localStorage.setItem("jarvis_bookmarks", JSON.stringify(existing));
    const { result } = renderHook(() => useBookmarks());
    expect(result.current.bookmarks).toHaveLength(1);
    expect(result.current.bookmarks[0].label).toBe("Saved");
  });

  it("prepends new bookmarks (most recent first)", () => {
    const { result } = renderHook(() => useBookmarks());
    act(() => result.current.addBookmark("First", period, filters, 0));
    act(() => result.current.addBookmark("Second", period, filters, 0));
    expect(result.current.bookmarks[0].label).toBe("Second");
    expect(result.current.bookmarks[1].label).toBe("First");
  });

  it("caps bookmarks at 20", () => {
    const { result } = renderHook(() => useBookmarks());
    for (let i = 0; i < 25; i++) {
      act(() => result.current.addBookmark(`BM ${i}`, period, filters, 0));
    }
    expect(result.current.bookmarks).toHaveLength(20);
  });

  it("removes a bookmark by id", () => {
    const { result } = renderHook(() => useBookmarks());
    act(() => result.current.addBookmark("ToRemove", period, filters, 0));
    const id = result.current.bookmarks[0].id;
    act(() => result.current.removeBookmark(id));
    expect(result.current.bookmarks).toHaveLength(0);
  });

  it("handles corrupt localStorage gracefully", () => {
    localStorage.setItem("jarvis_bookmarks", "not-json!!!");
    const { result } = renderHook(() => useBookmarks());
    expect(result.current.bookmarks).toEqual([]);
  });
});
