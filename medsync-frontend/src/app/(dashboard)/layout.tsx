import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import DashboardLayoutClient from "./DashboardLayoutClient";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const medsyncSession = cookieStore.get("medsync_session");
  const userRole = cookieStore.get("medsync_role")?.value;

  // 1. Server-side session check
  if (!medsyncSession) {
    redirect("/login");
  }

  // 2. Server-side RBAC check (second layer of defense)
  if (!userRole) {
    redirect("/login");
  }

  // Note: We can't easily check the full pathname here because it's a layout,
  // but we can ensure the role is valid for the dashboard generally.
  // The proxy and client-side check handle the specific path access.
  if (!["doctor", "nurse", "lab_tech", "receptionist", "hospital_admin", "super_admin", "pharmacy"].includes(userRole)) {
    redirect("/unauthorized");
  }

  return <DashboardLayoutClient>{children}</DashboardLayoutClient>;
}
