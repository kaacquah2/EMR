"use client";

import React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function UnauthorizedPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
      <Card className="w-full max-w-md border-[#D97706]/30 bg-[#FFFBEB]/60" accent="amber">
        <CardContent className="pt-6 text-center">
          <h1 className="font-sora text-2xl font-bold text-[#0F172A]">Access denied</h1>
          <p className="mt-2 text-[#64748B]">You do not have permission to view this page.</p>
          <Link href="/dashboard" className="mt-6 inline-block">
            <Button>Back to Dashboard</Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
