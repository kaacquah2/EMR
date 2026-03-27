"use client";

import React, { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface OnboardingStatus {
  not_started: number;
  in_progress: number;
  complete: number;
}

interface Staff {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  onboarding: {
    invited_at: string;
    account_activated: boolean;
    mfa_setup: boolean;
    license_verified: boolean | null;
    status: string;
  };
}

interface DashboardData {
  total_staff: number;
  by_status: OnboardingStatus;
  staff: Staff[];
}

const statusColors = {
  not_started: "bg-gray-100 text-gray-800",
  in_progress: "bg-yellow-100 text-yellow-800",
  complete: "bg-green-100 text-green-800",
};

const roleColors = {
  doctor: "bg-blue-50",
  nurse: "bg-pink-50",
  lab_technician: "bg-purple-50",
  receptionist: "bg-orange-50",
  hospital_admin: "bg-red-50",
};

export default function HospitalAdminStaffOnboarding() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStaff, setSelectedStaff] = useState<Staff | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await fetch("/api/admin/staff-onboarding", {
        headers: { "Content-Type": "application/json" },
      });
      if (response.ok) {
        const result = await response.json();
        setData(result);
      } else {
        setError("Failed to load dashboard");
      }
    } catch {
      setError("Error loading dashboard");
    } finally {
      setLoading(false);
    }
  };

  const filteredStaff = filterStatus
    ? data?.staff.filter((s) => s.onboarding.status === filterStatus)
    : data?.staff;

  if (loading) {
    return <div className="p-6">Loading...</div>;
  }

  if (error) {
    return <div className="p-6 text-red-600">{error}</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Staff Onboarding Dashboard</h1>
        <p className="text-gray-600">Track staff activation, MFA setup, and license verification</p>
      </div>

      {/* Status Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card
          className="p-4 cursor-pointer hover:shadow-md"
          onClick={() => setFilterStatus(null)}
        >
          <div className="text-sm text-gray-500">Total Staff</div>
          <div className="text-3xl font-bold">{data?.total_staff}</div>
        </Card>
        <Card
          className="p-4 cursor-pointer hover:shadow-md bg-gray-50"
          onClick={() => setFilterStatus("not_started")}
        >
          <div className="text-sm text-gray-600">Not Started</div>
          <div className="text-3xl font-bold">{data?.by_status.not_started}</div>
        </Card>
        <Card
          className="p-4 cursor-pointer hover:shadow-md bg-yellow-50"
          onClick={() => setFilterStatus("in_progress")}
        >
          <div className="text-sm text-yellow-600">In Progress</div>
          <div className="text-3xl font-bold">{data?.by_status.in_progress}</div>
        </Card>
        <Card
          className="p-4 cursor-pointer hover:shadow-md bg-green-50"
          onClick={() => setFilterStatus("complete")}
        >
          <div className="text-sm text-green-600">Complete</div>
          <div className="text-3xl font-bold">{data?.by_status.complete}</div>
        </Card>
      </div>

      {/* Legend */}
      <div className="text-sm text-gray-600">
        Click on status cards to filter • Click on a staff member to see details
      </div>

      {/* Staff List */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-4">
          {filterStatus
            ? `Staff - ${filterStatus.replace("_", " ").toUpperCase()}`
            : "All Staff"}
        </h2>
        <div className="space-y-3">
          {filteredStaff && filteredStaff.length > 0 ? (
            filteredStaff.map((staff) => (
              <div
                key={staff.user_id}
                className={`border rounded p-4 cursor-pointer hover:shadow-md transition ${
                  roleColors[staff.role as keyof typeof roleColors] || "bg-gray-50"
                }`}
                onClick={() => {
                  setSelectedStaff(staff);
                  setDetailsOpen(true);
                }}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-semibold">{staff.full_name}</h3>
                    <p className="text-sm text-gray-600">{staff.email}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      Role: {staff.role.replace("_", " ")}
                    </p>
                  </div>
                  <div className="text-right">
                    <span
                      className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                        statusColors[staff.onboarding.status as keyof typeof statusColors]
                      }`}
                    >
                      {staff.onboarding.status.replace("_", " ")}
                    </span>
                  </div>
                </div>

                {/* Onboarding Steps */}
                <div className="mt-3 space-y-1 text-sm">
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-4 h-4 rounded-full flex items-center justify-center ${
                        staff.onboarding.account_activated
                          ? "bg-green-500 text-white"
                          : "bg-gray-300"
                      }`}
                    >
                      {staff.onboarding.account_activated ? "✓" : ""}
                    </span>
                    <span>Account Activated</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`w-4 h-4 rounded-full flex items-center justify-center ${
                        staff.onboarding.mfa_setup
                          ? "bg-green-500 text-white"
                          : "bg-gray-300"
                      }`}
                    >
                      {staff.onboarding.mfa_setup ? "✓" : ""}
                    </span>
                    <span>MFA Setup</span>
                  </div>
                  {staff.onboarding.license_verified !== null && (
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-4 h-4 rounded-full flex items-center justify-center ${
                          staff.onboarding.license_verified
                            ? "bg-green-500 text-white"
                            : "bg-yellow-400"
                        }`}
                      >
                        {staff.onboarding.license_verified ? "✓" : ""}
                      </span>
                      <span>License Verified</span>
                    </div>
                  )}
                </div>
              </div>
            ))
          ) : (
            <p className="text-gray-500 text-center py-8">No staff found</p>
          )}
        </div>
      </Card>

      {/* Staff Details Dialog */}
      <Dialog open={detailsOpen} onOpenChange={setDetailsOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Staff Onboarding Details</DialogTitle>
          </DialogHeader>
          {selectedStaff && (
            <div className="space-y-4">
              <div>
                <p className="text-sm text-gray-600">Name</p>
                <p className="font-semibold">{selectedStaff.full_name}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Email</p>
                <p className="font-semibold">{selectedStaff.email}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Role</p>
                <p className="font-semibold">{selectedStaff.role.replace("_", " ")}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Invited Date</p>
                <p className="font-semibold">
                  {new Date(selectedStaff.onboarding.invited_at).toLocaleDateString()}
                </p>
              </div>

              <div className="pt-4 border-t space-y-3">
                <h3 className="font-semibold">Onboarding Progress</h3>
                
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Account Activated</span>
                    <span className="text-sm font-semibold">
                      {selectedStaff.onboarding.account_activated ? "✓ Yes" : "✗ Pending"}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">MFA Setup</span>
                    <span className="text-sm font-semibold">
                      {selectedStaff.onboarding.mfa_setup ? "✓ Yes" : "✗ Pending"}
                    </span>
                  </div>
                  {selectedStaff.onboarding.license_verified !== null && (
                    <div className="flex justify-between items-center">
                      <span className="text-sm">License Verified (Doctor)</span>
                      <span className="text-sm font-semibold">
                        {selectedStaff.onboarding.license_verified
                          ? "✓ Yes"
                          : "✗ Pending"}
                      </span>
                    </div>
                  )}
                </div>

                <div>
                  <p className="text-sm font-semibold mb-2">Overall Status</p>
                  <span
                    className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                      statusColors[
                        selectedStaff.onboarding.status as keyof typeof statusColors
                      ]
                    }`}
                  >
                    {selectedStaff.onboarding.status.replace("_", " ")}
                  </span>
                </div>

                <div className="pt-3 space-y-2">
                  <p className="text-xs text-gray-500">
                    {selectedStaff.onboarding.status === "not_started" &&
                      "This staff member needs to activate their account and complete MFA setup."}
                    {selectedStaff.onboarding.status === "in_progress" &&
                      "This staff member is in the onboarding process. Check back soon."}
                    {selectedStaff.onboarding.status === "complete" &&
                      "This staff member has completed all onboarding steps."}
                  </p>
                </div>
              </div>

              <div className="pt-4 border-t flex gap-2">
                <Button variant="outline" className="flex-1">
                  Resend Invite
                </Button>
                <Button variant="outline" className="flex-1">
                  Reset MFA
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
