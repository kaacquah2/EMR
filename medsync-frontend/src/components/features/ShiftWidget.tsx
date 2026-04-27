"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";

interface Shift {
  id: string;
  start_time: string;
  shift_type: string;
  ward_id: string;
  ward_name: string;
  on_break: boolean;
  break_start_time?: string;
  end_time?: string;
}

export function ShiftWidget() {
  const router = useRouter();
  const { user } = useAuth();
  const api = useApi();
  const toast = useToast();

  const [shift, setShift] = useState<Shift | null>(null);
  const [loading, setLoading] = useState(true);
  const [onBreakLoading, setOnBreakLoading] = useState(false);
  const [currentTime, setCurrentTime] = useState<string>("");

  // Fetch current shift on mount
  useEffect(() => {
    if (!user || user.role !== "nurse") {
      setLoading(false);
      return;
    }

    const fetchShift = async () => {
      try {
        const res = await api.get<{ data?: Shift }>("/shifts/current");
        if (res?.data) {
          setShift(res.data);
        }
      } catch (err) {
        console.error("Failed to fetch current shift:", err);
      } finally {
        setLoading(false);
      }
    };

    void fetchShift();
  }, [api, user]);

  // Update current time every minute
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString("en-GB", {
          hour: "2-digit",
          minute: "2-digit",
        })
      );
    };

    updateTime();
    const interval = setInterval(updateTime, 60_000);
    return () => clearInterval(interval);
  }, []);

  // Only show if user is a nurse
  if (!user || user.role !== "nurse") return null;

  const handleToggleBreak = async () => {
    if (!shift) return;
    setOnBreakLoading(true);

    try {
      const action = shift.on_break ? "resume" : "break";
      await api.post(`/shifts/${shift.id}/${action}`, {});

      // Update local state
      setShift({ ...shift, on_break: !shift.on_break });

      toast.success(`Break ${shift.on_break ? "resumed" : "started"}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update break status");
    } finally {
      setOnBreakLoading(false);
    }
  };

  const handleEndShift = () => {
    if (!shift) return;
    // Navigate to handover page with ward_id
    router.push(`/worklist/handover?ward_id=${shift.ward_id}`);
  };

  if (loading || !shift) {
    return (
      <div className="border-t border-[#1A3A5C] border-t-[#0B8A96]/30 p-4">
        <div className="text-xs text-white/60">Loading shift…</div>
      </div>
    );
  }

  return (
    <div className="border-t border-[#1A3A5C] border-t-[#0B8A96]/30 p-4">
      <div className="space-y-2.5">
        {/* Shift header */}
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-white/85">
            {shift.shift_type} shift
          </span>
          <span className="font-mono text-xs text-white/70">{currentTime}</span>
        </div>

        {/* Ward name */}
        <div className="text-sm font-medium text-white">Ward {shift.ward_name}</div>

        {/* Break indicator */}
        {shift.on_break && (
          <div className="rounded-lg bg-[#EF9F27]/20 px-2.5 py-1.5">
            <p className="text-xs font-medium text-[#EF9F27]">On break</p>
          </div>
        )}

        {/* Action buttons */}
        <div className="flex gap-2 pt-2">
          <Button
            size="sm"
            variant={shift.on_break ? "secondary" : "secondary"}
            onClick={() => void handleToggleBreak()}
            disabled={onBreakLoading}
            className="flex-1"
          >
            {onBreakLoading ? "…" : shift.on_break ? "Resume" : "Log break"}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={handleEndShift}
            className="flex-1"
          >
            End shift
          </Button>
        </div>
      </div>
    </div>
  );
}
