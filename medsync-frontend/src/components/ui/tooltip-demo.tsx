/**
 * Example/Demo component showing all Tooltip features.
 * This demonstrates how to use the Tooltip component with different configurations.
 *
 * @example
 * ```tsx
 * import { TooltipDemo } from '@/components/ui/tooltip-demo';
 *
 * export default function Page() {
 *   return <TooltipDemo />;
 * }
 * ```
 */

"use client";

import { Tooltip } from "./Tooltip";
import { Button } from "./button";

export function TooltipDemo() {
  return (
    <div className="flex flex-col gap-12 p-8 bg-white dark:bg-slate-950 min-h-screen">
      {/* Header */}
      <div className="max-w-4xl">
        <h1 className="text-3xl font-bold mb-2 text-slate-900 dark:text-white">
          Tooltip Component Demo
        </h1>
        <p className="text-slate-600 dark:text-slate-300">
          Production-ready accessible tooltip component with automatic positioning, animations, and keyboard support.
        </p>
      </div>

      {/* Hover Trigger */}
      <section className="max-w-4xl">
        <h2 className="text-xl font-semibold mb-6 text-slate-900 dark:text-white">
          Hover Trigger (Default)
        </h2>
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {["top", "right", "bottom", "left"].map((position) => (
            <div key={position} className="flex items-center justify-center min-h-24">
              <Tooltip
                content={`Tooltip on ${position}`}
                side={position as "top" | "bottom" | "left" | "right"}
                trigger="hover"
              >
                <Button variant="secondary">
                  Hover Me
                </Button>
              </Tooltip>
            </div>
          ))}
        </div>
      </section>

      {/* Click Trigger */}
      <section className="max-w-4xl">
        <h2 className="text-xl font-semibold mb-6 text-slate-900 dark:text-white">
          Click Trigger
        </h2>
        <div className="flex gap-4">
          <Tooltip
            content="Click to toggle this tooltip"
            trigger="click"
            side="top"
          >
            <Button variant="primary">
              Click Me
            </Button>
          </Tooltip>
          <Tooltip
            content="This is another clickable tooltip"
            trigger="click"
            side="right"
          >
            <Button variant="outline">
              Click Me Too
            </Button>
          </Tooltip>
        </div>
      </section>

      {/* Focus Trigger */}
      <section className="max-w-4xl">
        <h2 className="text-xl font-semibold mb-6 text-slate-900 dark:text-white">
          Focus Trigger
        </h2>
        <div className="flex gap-4">
          <Tooltip
            content="This tooltip appears on focus"
            trigger="focus"
            side="top"
          >
            <input
              type="text"
              placeholder="Focus me to see tooltip"
              className="px-3 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500"
            />
          </Tooltip>
        </div>
      </section>

      {/* Delay Configuration */}
      <section className="max-w-4xl">
        <h2 className="text-xl font-semibold mb-6 text-slate-900 dark:text-white">
          Delay Configuration
        </h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <Tooltip content="No delay" delayMs={0}>
            <Button variant="secondary">No Delay</Button>
          </Tooltip>
          <Tooltip content="200ms delay" delayMs={200}>
            <Button variant="secondary">200ms</Button>
          </Tooltip>
          <Tooltip content="500ms delay" delayMs={500}>
            <Button variant="secondary">500ms</Button>
          </Tooltip>
        </div>
      </section>

      {/* Dark Mode Support */}
      <section className="max-w-4xl">
        <h2 className="text-xl font-semibold mb-6 text-slate-900 dark:text-white">
          Dark Mode Support
        </h2>
        <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">
          The tooltip automatically adapts to light and dark modes. Light mode shows light background, dark mode shows dark background.
        </p>
        <Tooltip content="This tooltip adapts to your theme" side="top">
          <Button variant="primary">
            Theme-Aware Tooltip
          </Button>
        </Tooltip>
      </section>

      {/* Long Content */}
      <section className="max-w-4xl">
        <h2 className="text-xl font-semibold mb-6 text-slate-900 dark:text-white">
          Long Content
        </h2>
        <Tooltip
          content="This is a longer tooltip content that may wrap to multiple lines depending on the max-width constraint and viewport size."
          side="top"
          delayMs={100}
        >
          <Button variant="secondary">
            Hover for Long Tooltip
          </Button>
        </Tooltip>
      </section>

      {/* Accessibility Info */}
      <section className="max-w-4xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-3 text-blue-900 dark:text-blue-100">
          ♿ Accessibility Features
        </h2>
        <ul className="space-y-2 text-sm text-blue-800 dark:text-blue-200">
          <li>✓ <code className="bg-blue-100 dark:bg-blue-800/50 px-1 rounded">{`role="tooltip"`}</code> for screen readers</li>
          <li>✓ <code className="bg-blue-100 dark:bg-blue-800/50 px-1 rounded">aria-describedby</code> connecting trigger to tooltip</li>
          <li>✓ ESC key support to dismiss tooltip</li>
          <li>✓ Keyboard navigation with focus trigger</li>
          <li>✓ Automatic positioning to stay within viewport</li>
          <li>✓ Works with any trigger element</li>
        </ul>
      </section>

      {/* Implementation Info */}
      <section className="max-w-4xl bg-slate-100 dark:bg-slate-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-3 text-slate-900 dark:text-white">
          Implementation Details
        </h2>
        <div className="space-y-2 text-sm text-slate-700 dark:text-slate-300">
          <p>
            <strong>Component Path:</strong> <code className="bg-slate-200 dark:bg-slate-700 px-2 py-1 rounded">
              medsync-frontend/src/components/ui/Tooltip.tsx
            </code>
          </p>
          <p>
            <strong>Props:</strong> children, content, side, trigger, className, delayMs
          </p>
          <p>
            <strong>Features:</strong> Portal-based rendering, viewport-aware positioning, Tailwind animations, dark mode support
          </p>
        </div>
      </section>
    </div>
  );
}
