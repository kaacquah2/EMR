"use client";

import * as React from "react";
import { createPortal } from "react-dom";

/**
 * Position sides for the tooltip relative to the trigger element.
 */
type TooltipSide = "top" | "bottom" | "left" | "right";

/**
 * Trigger behavior for showing the tooltip.
 */
type TooltipTrigger = "hover" | "click" | "focus";

/**
 * Props for the Tooltip component.
 */
export interface TooltipProps {
  /** Content that triggers the tooltip. */
  children: React.ReactNode;
  /** Tooltip text or content. */
  content: React.ReactNode;
  /** Position relative to trigger element. @default 'top' */
  side?: TooltipSide;
  /** Trigger behavior. @default 'hover' */
  trigger?: TooltipTrigger;
  /** Custom styling for tooltip box. */
  className?: string;
  /** Delay in milliseconds before showing tooltip. @default 200 */
  delayMs?: number;
}

/**
 * Position calculation result.
 */
interface Position {
  top: number;
  left: number;
  side: TooltipSide;
}

/**
 * Get offset values for tooltip position based on side.
 */
function getOffsetForSide(
  side: TooltipSide,
  gap: number = 8
): { x: number; y: number } {
  const offsetMap: Record<TooltipSide, { x: number; y: number }> = {
    top: { x: 0, y: -gap },
    bottom: { x: 0, y: gap },
    left: { x: -gap, y: 0 },
    right: { x: gap, y: 0 },
  };
  return offsetMap[side];
}

/**
 * Calculate tooltip position based on trigger element and viewport.
 * Auto-adjusts side if tooltip would be clipped.
 */
function calculatePosition(
  triggerRect: DOMRect,
  tooltipRect: DOMRect | null,
  preferredSide: TooltipSide,
  gap: number = 8
): Position {
  if (!tooltipRect) {
    return { top: 0, left: 0, side: preferredSide };
  }

  const viewport = {
    width: window.innerWidth,
    height: window.innerHeight,
  };

  const MARGIN = 8; // Margin from viewport edges

  // Helper to check if position would be visible
  const isPositionValid = (
    side: TooltipSide,
    triggerRect: DOMRect,
    tooltipRect: DOMRect
  ): boolean => {
    const offset = getOffsetForSide(side, gap);
    let top = 0;
    let left = 0;

    if (side === "top") {
      top = triggerRect.top + offset.y - tooltipRect.height;
      left =
        triggerRect.left +
        triggerRect.width / 2 -
        tooltipRect.width / 2 +
        offset.x;
    } else if (side === "bottom") {
      top = triggerRect.bottom + offset.y;
      left =
        triggerRect.left +
        triggerRect.width / 2 -
        tooltipRect.width / 2 +
        offset.x;
    } else if (side === "left") {
      top =
        triggerRect.top +
        triggerRect.height / 2 -
        tooltipRect.height / 2 +
        offset.y;
      left = triggerRect.left + offset.x - tooltipRect.width;
    } else {
      top =
        triggerRect.top +
        triggerRect.height / 2 -
        tooltipRect.height / 2 +
        offset.y;
      left = triggerRect.right + offset.x;
    }

    return (
      top >= MARGIN &&
      top + tooltipRect.height <= viewport.height - MARGIN &&
      left >= MARGIN &&
      left + tooltipRect.width <= viewport.width - MARGIN
    );
  };

  // Try preferred side first
  let finalSide = preferredSide;
  if (!isPositionValid(preferredSide, triggerRect, tooltipRect)) {
    // Try alternatives in order: opposite, top, bottom, left, right
    const alternatives: TooltipSide[] = [];

    if (preferredSide === "top") {
      alternatives.push("bottom", "left", "right");
    } else if (preferredSide === "bottom") {
      alternatives.push("top", "left", "right");
    } else if (preferredSide === "left") {
      alternatives.push("right", "top", "bottom");
    } else {
      alternatives.push("left", "top", "bottom");
    }

    for (const side of alternatives) {
      if (isPositionValid(side, triggerRect, tooltipRect)) {
        finalSide = side;
        break;
      }
    }
  }

  // Calculate final position
  const offset = getOffsetForSide(finalSide, gap);
  let top = 0;
  let left = 0;

  if (finalSide === "top") {
    top = triggerRect.top + offset.y - tooltipRect.height;
    left =
      triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2 + offset.x;
  } else if (finalSide === "bottom") {
    top = triggerRect.bottom + offset.y;
    left =
      triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2 + offset.x;
  } else if (finalSide === "left") {
    top =
      triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2 + offset.y;
    left = triggerRect.left + offset.x - tooltipRect.width;
  } else {
    top =
      triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2 + offset.y;
    left = triggerRect.right + offset.x;
  }

  // Clamp to viewport with margin
  top = Math.max(MARGIN, Math.min(top, viewport.height - tooltipRect.height - MARGIN));
  left = Math.max(
    MARGIN,
    Math.min(left, viewport.width - tooltipRect.width - MARGIN)
  );

  return { top, left, side: finalSide };
}

/**
 * Get arrow position based on tooltip side.
 */
function getArrowClasses(side: TooltipSide): string {
  const baseClasses =
    "absolute w-2 h-2 bg-inherit dark:bg-inherit rotate-45";

  const positionMap: Record<TooltipSide, string> = {
    top: "bottom-[-4px] left-1/2 -translate-x-1/2",
    bottom: "top-[-4px] left-1/2 -translate-x-1/2",
    left: "right-[-4px] top-1/2 -translate-y-1/2",
    right: "left-[-4px] top-1/2 -translate-y-1/2",
  };

  return `${baseClasses} ${positionMap[side]}`;
}

/**
 * Accessible Tooltip component with automatic positioning, animations, and keyboard support.
 *
 * @example
 * ```tsx
 * <Tooltip content="Delete this record" side="top" trigger="hover">
 *   <button>Delete</button>
 * </Tooltip>
 * ```
 */
const Tooltip = React.forwardRef<
  HTMLDivElement,
  TooltipProps & React.HTMLAttributes<HTMLDivElement>
>(
  (
    {
      children,
      content,
      side = "top",
      trigger = "hover",
      className = "",
      delayMs = 200,
      ...props
    }
  ) => {
    const triggerRef = React.useRef<HTMLDivElement>(null);
    const tooltipRef = React.useRef<HTMLDivElement>(null);
    const [isVisible, setIsVisible] = React.useState(false);
    const [position, setPosition] = React.useState<Position>({
      top: 0,
      left: 0,
      side,
    });
    const timeoutRef = React.useRef<NodeJS.Timeout | null>(null);
    const [isMounted, setIsMounted] = React.useState(false);
    const [tooltipId, setTooltipId] = React.useState<string>("");

    // Ensure component is mounted on client side and generate stable ID
    React.useEffect(() => {
      setIsMounted(true);
      setTooltipId(`tooltip-${Math.random().toString(36).substr(2, 9)}`);
    }, []);

    // Update position when tooltip becomes visible
    React.useEffect(() => {
      if (!isVisible || !isMounted) return;

      const updatePosition = () => {
        if (!triggerRef.current || !tooltipRef.current) return;

        const triggerRect = triggerRef.current.getBoundingClientRect();
        const tooltipRect = tooltipRef.current.getBoundingClientRect();

        const newPosition = calculatePosition(triggerRect, tooltipRect, side);
        setPosition(newPosition);
      };

      // Initial position calculation
      updatePosition();

      // Recalculate on scroll or resize
      window.addEventListener("scroll", updatePosition, true);
      window.addEventListener("resize", updatePosition);

      return () => {
        window.removeEventListener("scroll", updatePosition, true);
        window.removeEventListener("resize", updatePosition);
      };
    }, [isVisible, side, isMounted]);

    // Handle show with delay
    const showTooltip = React.useCallback(() => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        setIsVisible(true);
      }, delayMs);
    }, [delayMs]);

    // Handle hide (no delay)
    const hideTooltip = React.useCallback(() => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      setIsVisible(false);
    }, []);

    // Handle hover trigger
    const handleMouseEnter = () => {
      if (trigger === "hover") {
        showTooltip();
      }
    };

    const handleMouseLeave = () => {
      if (trigger === "hover") {
        hideTooltip();
      }
    };

    // Handle click trigger
    const handleClick = () => {
      if (trigger === "click") {
        setIsVisible((prev) => !prev);
      }
    };

    // Handle focus trigger
    const handleFocus = () => {
      if (trigger === "focus") {
        showTooltip();
      }
    };

    const handleBlur = () => {
      if (trigger === "focus") {
        hideTooltip();
      }
    };

    // Handle escape key
    React.useEffect(() => {
      if (!isVisible) return;

      const handleKeyDown = (event: KeyboardEvent) => {
        if (event.key === "Escape") {
          hideTooltip();
        }
      };

      document.addEventListener("keydown", handleKeyDown);
      return () => {
        document.removeEventListener("keydown", handleKeyDown);
      };
    }, [isVisible, hideTooltip]);

    // Cleanup timeout on unmount
    React.useEffect(() => {
      return () => {
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }
      };
    }, []);

    if (!isMounted) return <div ref={triggerRef}>{children}</div>;

    return (
      <>
        <div
          ref={triggerRef}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          onClick={handleClick}
          onFocus={handleFocus}
          onBlur={handleBlur}
          aria-describedby={tooltipId}
        >
          {children}
        </div>

        {isVisible &&
          createPortal(
            <div
              ref={tooltipRef}
              id={tooltipId}
              role="tooltip"
              className={`fixed pointer-events-none z-50 px-2.5 py-1.5 text-sm font-medium rounded-md max-w-xs whitespace-normal bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900 shadow-lg animate-in fade-in duration-200 overflow-hidden ${className}`}
              style={{
                top: `${position.top}px`,
                left: `${position.left}px`,
              }}
              {...props}
            >
              {content}
              <div className={getArrowClasses(position.side)} />
            </div>,
            document.body
          )}
      </>
    );
  }
);

Tooltip.displayName = "Tooltip";

export { Tooltip };
export type { TooltipSide, TooltipTrigger };
