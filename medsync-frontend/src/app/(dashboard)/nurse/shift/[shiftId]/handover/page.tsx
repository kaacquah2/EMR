"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useNurses } from "@/hooks/use-nurses";
import { ShiftHandoverForm } from "@/components/features/nurse/shift-handover-form";
import { User } from "@/lib/types";

interface PageProps {
  params: {
    shiftId: string;
  };
}

export default function SubmitShiftHandoverPage({ params }: PageProps) {
  const { shiftId } = params;
  const router = useRouter();
  const { user } = useAuth();
  const { getNursesAtHospital } = useNurses();

  const [incomingNurses, setIncomingNurses] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadNurses = async () => {
      if (!user?.hospital_id) {
        setError("Unable to determine hospital");
        setLoading(false);
        return;
      }

      try {
        const nurses = await getNursesAtHospital(user.hospital_id);
        // Filter out the current user from the list
        const filteredNurses = nurses.filter((n) => n.user_id !== user.user_id);
        setIncomingNurses(filteredNurses);
      } catch {
        setError("Failed to load nurses");
      } finally {
        setLoading(false);
      }
    };

    loadNurses();
  }, [user, getNursesAtHospital]);

  const handleSubmitSuccess = () => {
    router.push("/dashboard");
  };

  const handleCancel = () => {
    router.back();
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Submit Shift Handover</h1>
          {incomingNurses.length > 0 && (
            <p className="mt-2 text-gray-600">
              This handover will be sent to the selected nurse for acknowledgement.
            </p>
          )}
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-red-800 text-sm font-medium">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-200 border-t-blue-600"></div>
          </div>
        ) : incomingNurses.length === 0 ? (
          <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
            <p className="text-yellow-800 text-sm">
              No other nurses available at your hospital to handover to.
            </p>
          </div>
        ) : (
          <ShiftHandoverForm
            shiftId={shiftId}
            onSubmitSuccess={handleSubmitSuccess}
            onCancel={handleCancel}
            incomingNurses={incomingNurses}
          />
        )}
      </div>
    </div>
  );
}
