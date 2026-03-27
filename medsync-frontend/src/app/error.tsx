"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Route error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-6 px-4">
      <div className="rounded-xl border border-[#E2E8F0] bg-white p-8 shadow-sm max-w-md w-full text-center">
        <h1 className="font-sora text-xl font-bold text-[#0F172A] mb-2">
          Something went wrong
        </h1>
        <p className="text-sm text-[#64748B] mb-6">
          {error.message || "An unexpected error occurred."}
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Button onClick={reset}>Try again</Button>
          <Link
            href="/dashboard"
            className="inline-flex h-11 items-center justify-center rounded-lg border-[1.5px] border-[#CBD5E1] bg-white px-4 text-[15px] font-semibold text-[#0C1F3D] hover:bg-[#F1F5F9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2"
          >
            Back to Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
