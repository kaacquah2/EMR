import * as React from "react";

export type SkeletonProps = React.HTMLAttributes<HTMLDivElement>;

export const Skeleton = React.forwardRef<HTMLDivElement, SkeletonProps>(
  ({ className = "", ...props }, ref) => (
    <div
      ref={ref}
      className={`animate-pulse rounded-md bg-slate-200 dark:bg-slate-800 dark:bg-[#334155] ${className}`}
      {...props}
    />
  )
);
Skeleton.displayName = "Skeleton";

export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800/80 dark:border-[#334155] bg-white dark:bg-slate-800 dark:bg-slate-200 p-6 shadow-sm">
      <Skeleton className="mb-4 h-5 w-2/3" />
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className="h-4 w-full" />
        ))}
      </div>
    </div>
  );
}

export function ListSkeleton({
  rows = 5,
  showAvatar = false,
}: {
  rows?: number;
  showAvatar?: boolean;
}) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 rounded-lg border border-slate-200 dark:border-slate-800/80 dark:border-[#334155] bg-white dark:bg-slate-800 dark:bg-slate-200 p-4"
        >
          {showAvatar && <Skeleton className="h-10 w-10 shrink-0 rounded-full" />}
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton({
  rows = 5,
  cols = 4,
}: {
  rows?: number;
  cols?: number;
}) {
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-800/80 dark:border-[#334155] bg-white dark:bg-slate-800 dark:bg-slate-200 overflow-hidden">
      <div className="flex gap-4 border-b border-slate-200 dark:border-slate-800 dark:border-[#334155] bg-slate-50 dark:bg-slate-900 dark:bg-slate-900 dark:bg-slate-100 p-4">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex gap-4 border-b border-slate-200 dark:border-slate-800/50 dark:border-[#334155]/50 p-4 last:border-0"
        >
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}
