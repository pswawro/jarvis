import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSavedDimensions } from "../hooks/useSavedDimensions";

beforeEach(() => {
  localStorage.clear();
});

describe("useSavedDimensions", () => {
  it("starts empty when localStorage is empty", () => {
    const { result } = renderHook(() => useSavedDimensions());
    expect(result.current.saved).toEqual([]);
  });

  it("saves a dimension config", () => {
    const { result } = renderHook(() => useSavedDimensions());
    act(() => result.current.save("Revenue by Brand", ["ta", "brand"]));
    expect(result.current.saved).toHaveLength(1);
    expect(result.current.saved[0].label).toBe("Revenue by Brand");
    expect(result.current.saved[0].levels).toEqual(["ta", "brand"]);
  });

  it("persists to localStorage", () => {
    const { result } = renderHook(() => useSavedDimensions());
    act(() => result.current.save("Geo view", ["market", "region"]));
    const stored = JSON.parse(localStorage.getItem("jarvis_saved_dimensions")!);
    expect(stored).toHaveLength(1);
    expect(stored[0].label).toBe("Geo view");
  });

  it("generates a unique id for each saved dimension", () => {
    const { result } = renderHook(() => useSavedDimensions());
    act(() => result.current.save("A", ["ta"]));
    act(() => result.current.save("B", ["brand"]));
    const ids = result.current.saved.map((s) => s.id);
    expect(ids[0]).not.toBe(ids[1]);
  });

  it("loads from localStorage on init", () => {
    const existing = [
      { id: "abc", label: "Existing", levels: ["unit"], createdAt: "2025-01-01T00:00:00Z" },
    ];
    localStorage.setItem("jarvis_saved_dimensions", JSON.stringify(existing));
    const { result } = renderHook(() => useSavedDimensions());
    expect(result.current.saved).toHaveLength(1);
    expect(result.current.saved[0].label).toBe("Existing");
  });

  it("removes a saved dimension by id", () => {
    const { result } = renderHook(() => useSavedDimensions());
    act(() => result.current.save("Temp", ["ta"]));
    const id = result.current.saved[0].id;
    act(() => result.current.remove(id));
    expect(result.current.saved).toHaveLength(0);
  });

  it("appends new items (not prepends)", () => {
    const { result } = renderHook(() => useSavedDimensions());
    act(() => result.current.save("First", ["ta"]));
    act(() => result.current.save("Second", ["brand"]));
    expect(result.current.saved[0].label).toBe("First");
    expect(result.current.saved[1].label).toBe("Second");
  });

  it("handles corrupt localStorage gracefully", () => {
    localStorage.setItem("jarvis_saved_dimensions", "{broken");
    const { result } = renderHook(() => useSavedDimensions());
    expect(result.current.saved).toEqual([]);
  });
});
