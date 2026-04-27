"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.error("Global error:", error);
    }
  }, [error]);

  return (
    <html lang="en">
      <body className="min-h-screen bg-[#F5F3EE] flex items-center justify-center p-4 font-sans antialiased">
        <div className="rounded-xl border border-[#E2E8F0] bg-white p-8 shadow-sm max-w-md w-full text-center">
          <h1 className="text-xl font-bold text-[#0F172A] mb-2">
            Critical error
          </h1>
          <p className="text-sm text-[#64748B] mb-6">
            {error.message || "Something went wrong. Please try again."}
          </p>
          <button
            type="button"
            onClick={reset}
            className="inline-flex h-11 items-center justify-center rounded-lg bg-[#0B8A96] px-4 font-semibold text-white hover:bg-[#0A7A85] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
