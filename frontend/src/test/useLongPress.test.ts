import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLongPress } from "../hooks/useLongPress";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

function fakeTouchEvent(): React.TouchEvent {
  return { preventDefault: vi.fn() } as unknown as React.TouchEvent;
}

describe("useLongPress", () => {
  it("calls callback after delay", () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useLongPress(cb, 500));

    act(() => result.current.onTouchStart(fakeTouchEvent()));
    expect(cb).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(500));
    expect(cb).toHaveBeenCalledOnce();
  });

  it("sets didLongPress to true after long press fires", () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useLongPress(cb, 500));

    expect(result.current.didLongPress.current).toBe(false);
    act(() => result.current.onTouchStart(fakeTouchEvent()));
    act(() => vi.advanceTimersByTime(500));
    expect(result.current.didLongPress.current).toBe(true);
  });

  it("cancels on touch end before delay", () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useLongPress(cb, 500));

    act(() => result.current.onTouchStart(fakeTouchEvent()));
    act(() => vi.advanceTimersByTime(200));
    act(() => result.current.onTouchEnd(fakeTouchEvent()));
    act(() => vi.advanceTimersByTime(500));
    expect(cb).not.toHaveBeenCalled();
  });

  it("cancels on touch move", () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useLongPress(cb, 500));

    act(() => result.current.onTouchStart(fakeTouchEvent()));
    act(() => result.current.onTouchMove(fakeTouchEvent()));
    act(() => vi.advanceTimersByTime(600));
    expect(cb).not.toHaveBeenCalled();
  });

  it("uses custom delay", () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useLongPress(cb, 200));

    act(() => result.current.onTouchStart(fakeTouchEvent()));
    act(() => vi.advanceTimersByTime(200));
    expect(cb).toHaveBeenCalledOnce();
  });

  it("resets didLongPress on new touch start", () => {
    const cb = vi.fn();
    const { result } = renderHook(() => useLongPress(cb, 500));

    // First long press
    act(() => result.current.onTouchStart(fakeTouchEvent()));
    act(() => vi.advanceTimersByTime(500));
    expect(result.current.didLongPress.current).toBe(true);

    // New touch - should reset
    act(() => result.current.onTouchStart(fakeTouchEvent()));
    expect(result.current.didLongPress.current).toBe(false);
  });
});
