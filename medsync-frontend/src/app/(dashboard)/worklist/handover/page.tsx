"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Clock, AlertCircle, CheckCircle, Users } from "lucide-react";

interface ShiftInfo {
  shift_id: string;
  started_at: string;
  ward_name: string;
  patients_seen: number;
  duration_minutes: number;
  break_time_minutes: number;
}

interface NextShiftNurse {
  id: string;
  full_name: string;
  email: string;
}

export default function ShiftHandoverPage() {
  const router = useRouter();
  const api = useApi();
  const toast = useToast();

  const [shiftInfo, setShiftInfo] = useState<ShiftInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [nextNurses, setNextNurses] = useState<NextShiftNurse[]>([]);

  const [handoverNotes, setHandoverNotes] = useState("");
  const [selectedNextNurse, setSelectedNextNurse] = useState("");
  const [criticalAlerts, setCriticalAlerts] = useState({
    pending_tests: false,
    medication_follow_up: false,
    patient_escalation: false,
    equipment_issues: false,
  });

  const loadShiftInfo = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.get<{ shift: ShiftInfo }>(
        "/nurse/current-shift"
      );
      setShiftInfo(data.shift);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Could not load shift info"
      );
      setLoading(false);
    }
  }, [api, toast]);

  const loadNextNurses = useCallback(async () => {
    try {
      const data = await api.get<{ data: NextShiftNurse[] }>(
        "/admin/nurses?limit=50"
      );
      setNextNurses(data.data || []);
    } catch {
      // Silently fail - optional feature
      setNextNurses([]);
    }
  }, [api]);

  useEffect(() => {
    loadShiftInfo();
    loadNextNurses();
  }, [loadShiftInfo, loadNextNurses]);

  const handleSubmitHandover = async () => {
    if (!shiftInfo) {
      toast.error("Shift information not loaded");
      return;
    }

    if (!handoverNotes.trim()) {
      toast.error("Please provide handover notes");
      return;
    }

    setSubmitting(true);
    try {
      await api.post(
        `/nurse/shift/${shiftInfo.shift_id}/handover`,
        {
          handover_notes: handoverNotes,
          critical_alerts: Object.keys(criticalAlerts).filter(
            (key) => criticalAlerts[key as keyof typeof criticalAlerts]
          ),
          next_nurse_id: selectedNextNurse || null,
        }
      );

      toast.success("Shift handover completed successfully");
      router.push("/dashboard");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to submit handover"
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-[#64748B]">Loading shift information...</div>
      </div>
    );
  }

  if (!shiftInfo) {
    return (
      <Card className="m-6 p-6 border-amber-200 bg-amber-50">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-amber-900">No active shift</p>
            <p className="text-sm text-amber-800 mt-1">
              You do not have an active shift to handover. Please start a shift first.
            </p>
            <Button
              onClick={() => router.push("/dashboard")}
              className="mt-3 bg-amber-600 hover:bg-amber-700"
            >
              Back to Dashboard
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  const durationHours = Math.floor(shiftInfo.duration_minutes / 60);
  const durationMinutes = shiftInfo.duration_minutes % 60;
  const breakHours = Math.floor(shiftInfo.break_time_minutes / 60);
  const breakMinutes = shiftInfo.break_time_minutes % 60;

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="font-sora text-3xl font-bold text-[#0F172A]">Shift Handover</h1>
        <p className="text-[#64748B] mt-2">
          Complete your shift handover to the next nurse and ensure continuity of care.
        </p>
      </div>

      {/* Shift Summary */}
      <Card className="p-6 border-blue-200 bg-blue-50">
        <h2 className="font-sora font-bold text-[#0F172A] mb-4">Shift Summary</h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div>
            <p className="text-xs text-[#64748B] uppercase font-medium">Ward</p>
            <p className="font-sora font-bold text-[#0F172A] mt-1">
              {shiftInfo.ward_name}
            </p>
          </div>
          <div>
            <p className="text-xs text-[#64748B] uppercase font-medium flex items-center gap-1">
              <Clock className="h-4 w-4" /> Duration
            </p>
            <p className="font-sora font-bold text-[#0F172A] mt-1">
              {durationHours}h {durationMinutes}m
            </p>
          </div>
          <div>
            <p className="text-xs text-[#64748B] uppercase font-medium">Break Time</p>
            <p className="font-sora font-bold text-[#0F172A] mt-1">
              {breakHours}h {breakMinutes}m
            </p>
          </div>
          <div>
            <p className="text-xs text-[#64748B] uppercase font-medium flex items-center gap-1">
              <Users className="h-4 w-4" /> Patients Seen
            </p>
            <p className="font-sora font-bold text-[#0F172A] mt-1">
              {shiftInfo.patients_seen}
            </p>
          </div>
        </div>
      </Card>

      {/* Handover Form */}
      <Card className="p-6 space-y-6">
        <div>
          <label className="block text-sm font-medium text-[#0F172A] mb-2">
            Handover Notes *
          </label>
          <textarea
            value={handoverNotes}
            onChange={(e) => setHandoverNotes(e.target.value)}
            placeholder="Document important information for the next shift:
- Patient status updates
- Pending procedures or tests
- Equipment issues
- Care coordination notes
- Any escalations or concerns"
            className="w-full rounded-lg border border-[#E2E8F0] bg-white px-3 py-3 text-sm h-32 focus:outline-none focus:ring-2 focus:ring-[#0EAFBE]"
          />
          <p className="text-xs text-[#64748B] mt-1">
            {handoverNotes.length}/500 characters
          </p>
        </div>

        {/* Critical Alerts */}
        <div>
          <label className="block text-sm font-medium text-[#0F172A] mb-3">
            Critical Alerts
          </label>
          <div className="space-y-3">
            {Object.entries({
              pending_tests: "Pending lab tests or imaging",
              medication_follow_up: "Medication follow-up required",
              patient_escalation: "Patient escalation/deterioration",
              equipment_issues: "Equipment maintenance needed",
            }).map(([key, label]) => (
              <label key={key} className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={criticalAlerts[key as keyof typeof criticalAlerts]}
                  onChange={(e) =>
                    setCriticalAlerts((prev) => ({
                      ...prev,
                      [key]: e.target.checked,
                    }))
                  }
                  className="h-4 w-4 rounded border-[#CBD5E1]"
                />
                <span className="text-sm text-[#0F172A]">{label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Next Shift Nurse */}
        {nextNurses.length > 0 && (
          <div>
            <label className="block text-sm font-medium text-[#0F172A] mb-2">
              Next Shift Nurse (optional)
            </label>
            <select
              value={selectedNextNurse}
              onChange={(e) => setSelectedNextNurse(e.target.value)}
              className="w-full rounded-lg border border-[#E2E8F0] bg-white px-3 py-2 text-sm"
            >
              <option value="">-- Not specified --</option>
              {nextNurses.map((nurse) => (
                <option key={nurse.id} value={nurse.id}>
                  {nurse.full_name} ({nurse.email})
                </option>
              ))}
            </select>
            <p className="text-xs text-[#64748B] mt-1">
              Select the nurse taking the next shift for handover acknowledgment.
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4 border-t border-[#E2E8F0]">
          <Button
            onClick={handleSubmitHandover}
            disabled={submitting || !handoverNotes.trim()}
            className="flex-1 bg-[#0EAFBE] hover:bg-[#0B94A6]"
          >
            {submitting ? "Submitting..." : "Complete Shift Handover"}
          </Button>
          <Button
            onClick={() => router.back()}
            variant="outline"
            className="flex-1"
          >
            Cancel
          </Button>
        </div>
      </Card>

      {/* Info Banner */}
      <Card className="p-4 bg-green-50 border-green-200">
        <div className="flex items-start gap-3">
          <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-green-900">
            <p className="font-medium">Shift Handover Best Practices</p>
            <ul className="text-xs mt-2 space-y-1">
              <li>• Be clear and concise in your notes</li>
              <li>• Highlight any urgent patient concerns</li>
              <li>• Mention any follow-up appointments or procedures</li>
              <li>• Report any equipment or staffing issues</li>
              <li>• Confirm handover was received by next shift</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}
