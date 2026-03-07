import { motion } from "framer-motion";
import { useRef, useCallback } from "react";
import type { ReactNode } from "react";

interface Props {
  activeIndex: number;
  onSwitch: (index: number) => void;
  children: ReactNode[];
}

/** Check if an element or any ancestor has horizontal scroll */
function hasHorizontalScroll(el: HTMLElement | null): boolean {
  while (el) {
    if (el.scrollWidth > el.clientWidth + 1) return true;
    el = el.parentElement;
  }
  return false;
}

export function SwipeContainer({ activeIndex, onSwitch, children }: Props) {
  const dragEnabled = useRef(true);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    dragEnabled.current = !hasHorizontalScroll(e.target as HTMLElement);
  }, []);

  const handleDragEnd = (
    _: unknown,
    info: { offset: { x: number }; velocity: { x: number } }
  ) => {
    if (!dragEnabled.current) return;

    const threshold = 50;
    const velThreshold = 500;

    if (info.offset.x < -threshold || info.velocity.x < -velThreshold) {
      if (activeIndex < children.length - 1) onSwitch(activeIndex + 1);
    } else if (info.offset.x > threshold || info.velocity.x > velThreshold) {
      if (activeIndex > 0) onSwitch(activeIndex - 1);
    }
  };

  return (
    <div className="relative overflow-hidden flex-1" onPointerDown={handlePointerDown}>
      <motion.div
        className="flex h-full"
        animate={{ x: `-${activeIndex * 100}%` }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        drag={dragEnabled.current ? "x" : false}
        dragConstraints={{ left: 0, right: 0 }}
        dragElastic={0.15}
        dragDirectionLock
        onDragEnd={handleDragEnd}
      >
        {children.map((child, i) => (
          <div key={i} className="w-full shrink-0 h-full overflow-y-auto">
            {child}
          </div>
        ))}
      </motion.div>
    </div>
  );
}
