import { Metadata } from "next";
import { PharmacyDashboard } from "@/components/features/pharmacy/PharmacyDashboard";

export const metadata: Metadata = {
  title: "Pharmacy Inventory | MedSync",
  description: "Pharmacy inventory and drug stock management",
};

export default function PharmacyInventoryPage() {
  return (
    <div className="space-y-6">
      <PharmacyDashboard />
    </div>
  );
}
