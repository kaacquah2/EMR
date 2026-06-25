"use client";

import { useAuth } from "@/lib/auth-context";
import { roleAccentColours } from "@/lib/constants";

export default function ComingSoonPage() {
  const { user } = useAuth();

  const roleName = user?.role
    ?.split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ") || "User";

  const accentColor = roleAccentColours[user?.role || "doctor"];

  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-8 text-center">
        <div
          className={`w-16 h-16 rounded-full ${accentColor} mx-auto mb-6 flex items-center justify-center`}
        >
          <svg
            className="w-8 h-8 text-white"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>

        <h1 className="text-2xl font-bold text-slate-900 mb-4">
          Coming Soon
        </h1>

        <p className="text-slate-600 mb-6">
          The <span className="font-semibold">{roleName}</span> module is
          currently under development and will be available in a future release.
        </p>

        <p className="text-sm text-slate-500">
          We&apos;re working hard to bring you this feature. Check back soon!
        </p>
      </div>
    </div>
  );
}
