"use client";

import React, { useEffect, useState } from "react";
import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const WARNING_SECONDS = 2 * 60;

function formatMmSs(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface InactivityModalProps {
  open: boolean;
  onStayLoggedIn: () => void;
  onLogout: () => void;
}

export function InactivityModal({ open, onStayLoggedIn, onLogout }: InactivityModalProps) {
  const [secondsLeft, setSecondsLeft] = useState(WARNING_SECONDS);

  useEffect(() => {
    if (!open) return;
    queueMicrotask(() => setSecondsLeft(WARNING_SECONDS));
    const endAt = Date.now() + WARNING_SECONDS * 1000;
    const id = setInterval(() => {
      const left = Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left <= 0) {
        clearInterval(id);
        onLogout();
      }
    }, 1000);
    return () => clearInterval(id);
  }, [open, onLogout]);

  return (
    <Dialog open={open} onOpenChange={() => {}}>
      <DialogPortal>
        <DialogOverlay />
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-[#B45309]">Session Expiring Soon</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-slate-500 dark:text-slate-500 mb-4">
            Your session will expire in <strong>{formatMmSs(secondsLeft)}</strong> due to inactivity.
          </p>
          <div className="flex gap-2 justify-end">
            <Button variant="secondary" onClick={onLogout}>
              Log Out Now
            </Button>
            <Button onClick={onStayLoggedIn}>
              Stay Logged In
            </Button>
          </div>
        </DialogContent>
      </DialogPortal>
    </Dialog>
  );
}
