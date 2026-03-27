"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AuthLayout } from "@/components/auth/AuthLayout";

export default function SignInPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/login");
  }, [router]);
  return (
    <AuthLayout title="MedSync" subtitle="One Record. Every Hospital.">
      <p className="text-center text-[#64748B]">Redirecting to sign in...</p>
    </AuthLayout>
  );
}
