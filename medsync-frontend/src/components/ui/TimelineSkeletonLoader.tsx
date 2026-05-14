import * as React from "react";
import { Skeleton } from "./skeleton";

export function TimelineSkeletonLoader() {
  return (
    <div className="flex flex-col h-full bg-white dark:bg-slate-900 dark:bg-slate-100">
      {/* Zoom Controls Skeleton */}
      <div className="flex flex-wrap gap-2 p-4 border-b border-gray-200 dark:border-gray-700">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton
            key={`zoom-${i}`}
            className="h-10 w-24 rounded-lg"
          />
        ))}
      </div>

      {/* Filter Chips Skeleton */}
      <div className="flex flex-wrap gap-2 p-4 border-b border-gray-200 dark:border-gray-700">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton
            key={`filter-${i}`}
            className="h-9 w-32 rounded-full"
          />
        ))}
      </div>

      {/* Timeline Content Skeleton */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-gray-300 dark:bg-gray-600" />

          {/* Skeleton Event Cards */}
          <div className="space-y-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={`event-${i}`} className="flex gap-4">
                {/* Date badge on timeline */}
                <div className="flex flex-col items-center pt-1">
                  <div className="w-4 h-4 rounded-full bg-gray-300 dark:bg-gray-600 border-4 border-white dark:border-slate-900 dark:border-slate-100 absolute -ml-11" />
                  <Skeleton className="text-xs font-semibold -mt-3 whitespace-nowrap h-3 w-12 mt-2" />
                </div>

                {/* Event card skeleton */}
                <div className="flex-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-4 space-y-3">
                  {/* Badge and severity row */}
                  <div className="flex items-start justify-between gap-2">
                    <Skeleton className="h-6 w-24 rounded-full" />
                    <Skeleton className="h-5 w-16 rounded" />
                  </div>

                  {/* Summary text */}
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-4 w-2/3" />
                  </div>

                  {/* Date and provider row */}
                  <div className="flex items-center justify-between">
                    <Skeleton className="h-3 w-20" />
                    <Skeleton className="h-3 w-24" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
