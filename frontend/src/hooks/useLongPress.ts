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

  const start: React.TouchEventHandler = useCallback(
    () => {
      didLongPress.current = false;
      timerRef.current = window.setTimeout(() => {
        didLongPress.current = true;
        callback();
      }, delay);
    },
    [callback, delay],
  );

  const cancel: React.TouchEventHandler = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const onContextMenu = useCallback(
    (e: React.MouseEvent) => {
      if (didLongPress.current) e.preventDefault();
    },
    [],
  );

  return {
    onTouchStart: start,
    onTouchEnd: cancel,
    onTouchMove: cancel,
    onContextMenu,
    didLongPress,
  };
}
