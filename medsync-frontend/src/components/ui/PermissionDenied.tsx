"use client";

import React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface PermissionDeniedProps {
  message: string;
  showBack?: boolean;
}

export function PermissionDenied({ message, showBack = true }: PermissionDeniedProps) {
  return (
    <div className="rounded-lg border border-[#F59E0B]/40 bg-[#FEF3C7] p-4 text-[#B45309]">
      <p className="font-medium">{message}</p>
      {showBack && (
        <Link href="/dashboard" className="mt-3 inline-block">
          <Button variant="secondary" size="sm">Back to Dashboard</Button>
        </Link>
      )}
    </div>
  );
}
