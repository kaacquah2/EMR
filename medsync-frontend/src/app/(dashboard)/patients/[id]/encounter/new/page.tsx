"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function EncounterNewAliasPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  useEffect(() => {
    router.replace(`/patients/${id}/encounters/new`);
  }, [id, router]);

  return <div className="py-8 text-center text-[#64748B]">Redirecting...</div>;
}

