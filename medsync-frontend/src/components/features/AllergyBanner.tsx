import React from "react";
import type { Allergy } from "@/lib/types";

interface AllergyBannerProps {
  allergies: Allergy[];
}

export function AllergyBanner({ allergies }: AllergyBannerProps) {
  if (!allergies || allergies.length === 0) {
    return (
      <div className="min-h-[44px] w-full border-l-4 border-[#059669] bg-[#D1FAE5] px-6 py-3">
        <span className="font-sans text-sm font-semibold text-[#047857]">
          No known allergies documented
        </span>
      </div>
    );
  }

  const activeAllergies = allergies.filter((a) => a.is_active);
  const hasAnaphylaxis = activeAllergies.some((a) => {
    const severity = (a.severity || "").toLowerCase();
    const reaction = (a.reaction_type || "").toLowerCase();
    return severity === "anaphylaxis" || severity === "life_threatening" || reaction.includes("anaphylaxis");
  });
  if (activeAllergies.length === 0) {
    return (
      <div className="min-h-[44px] w-full border-l-4 border-[#059669] bg-[#D1FAE5] px-6 py-3">
        <span className="font-sans text-sm font-semibold text-[#047857]">
          No known allergies documented
        </span>
      </div>
    );
  }

  const text = activeAllergies
    .map(
      (a) =>
        `${a.allergen} (${a.reaction_type} — ${a.severity.replace(/_/g, " ").toUpperCase()})`
    )
    .join(" · ");

  return (
    <div className={`min-h-[44px] w-full border-l-4 px-6 py-3 ${hasAnaphylaxis ? "sticky top-0 border-[#B91C1C] bg-[#FEE2E2]" : "border-[#DC2626] bg-[#FFF1F2]"}`}>
      <span className="font-sans text-sm font-semibold text-[#B91C1C]">
        {hasAnaphylaxis ? "CRITICAL ALLERGY ALERT: " : "ALLERGIES: "}
        {text}
      </span>
    </div>
  );
}
