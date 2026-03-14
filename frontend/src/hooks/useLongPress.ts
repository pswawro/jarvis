import { useRef, useCallback, useEffect } from "react";

export function useLongPress(callback: () => void, delay = 500) {
  const timerRef = useRef<number | null>(null);
  const didLongPress = useRef(false);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const start = useCallback(
    (e: React.TouchEvent) => {
      didLongPress.current = false;
      timerRef.current = window.setTimeout(() => {
        didLongPress.current = true;
        callback();
      }, delay);
    },
    [callback, delay],
  );

  const cancel = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  return {
    onTouchStart: start,
    onTouchEnd: cancel,
    onTouchMove: cancel,
    didLongPress,
  };
}
