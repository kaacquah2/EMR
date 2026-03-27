"use client";

import React, { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface Hospital {
  hospital_id: string;
  name: string;
  nhis_code: string;
  region: string;
  is_active: boolean;
  created_at: string;
  staff: {
    total: number;
    doctors: number;
    nurses: number;
    others: number;
  };
  interop: {
    cross_facility_patients: number;
    active_consents: number;
    referrals_received: number;
  };
}

interface DashboardData {
  hospitals: Hospital[];
  total_hospitals: number;
  total_active: number;
}

export default function SuperAdminHospitalOnboarding() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedHospital, setSelectedHospital] = useState<Hospital | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [connectivityOpen, setConnectivityOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    nhis_code: "",
    region: "",
    address: "",
    phone: "",
    email: "",
  });

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await fetch("/api/superadmin/onboarding-dashboard", {
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

  const handleCreateHospital = async () => {
    try {
      const response = await fetch("/api/superadmin/onboard-hospital", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      if (response.ok) {
        setCreateOpen(false);
        setFormData({
          name: "",
          nhis_code: "",
          region: "",
          address: "",
          phone: "",
          email: "",
        });
        fetchDashboard();
      } else {
        setError("Failed to create hospital");
      }
    } catch {
      setError("Error creating hospital");
    }
  };

  const handleBulkImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !selectedHospital) return;

    const formDataMulti = new FormData();
    formDataMulti.append("csv_file", file);

    try {
      const response = await fetch(
        `/api/superadmin/hospitals/${selectedHospital.hospital_id}/bulk-import-staff`,
        {
          method: "POST",
          body: formDataMulti,
        }
      );
      if (response.ok) {
        const result = await response.json();
        alert(`Imported ${result.summary.created_count} staff. Errors: ${result.summary.error_count}`);
        setImportOpen(false);
        fetchDashboard();
      } else {
        setError("Failed to import staff");
      }
    } catch {
      setError("Error importing staff");
    }
  };

  if (loading) {
    return <div className="p-6">Loading...</div>;
  }

  if (error) {
    return <div className="p-6 text-red-600">{error}</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Hospital Onboarding Dashboard</h1>
        <Button onClick={() => setCreateOpen(true)}>Create Hospital</Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-4">
          <div className="text-sm text-gray-500">Total Hospitals</div>
          <div className="text-2xl font-bold">{data?.total_hospitals}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">Active Hospitals</div>
          <div className="text-2xl font-bold">{data?.total_active}</div>
        </Card>
        <Card className="p-4">
          <div className="text-sm text-gray-500">Interop Connected</div>
          <div className="text-2xl font-bold">
            {data?.hospitals.filter((h) => h.interop.cross_facility_patients > 0).length}
          </div>
        </Card>
      </div>

      {/* Hospital List */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-4">Hospitals</h2>
        <div className="space-y-4">
          {data?.hospitals.map((hospital) => (
            <div key={hospital.hospital_id} className="border rounded p-4 hover:bg-gray-50">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold">{hospital.name}</h3>
                  <p className="text-sm text-gray-600">
                    NHIS: {hospital.nhis_code} | Region: {hospital.region}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setSelectedHospital(hospital);
                      setImportOpen(true);
                    }}
                  >
                    Import Staff
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setSelectedHospital(hospital);
                      setConnectivityOpen(true);
                    }}
                  >
                    View Connectivity
                  </Button>
                </div>
              </div>

              {/* Staff Stats */}
              <div className="grid grid-cols-4 gap-2 mt-3 text-sm">
                <div>
                  <span className="text-gray-600">Total Staff: </span>
                  <span className="font-semibold">{hospital.staff.total}</span>
                </div>
                <div>
                  <span className="text-gray-600">Doctors: </span>
                  <span className="font-semibold">{hospital.staff.doctors}</span>
                </div>
                <div>
                  <span className="text-gray-600">Nurses: </span>
                  <span className="font-semibold">{hospital.staff.nurses}</span>
                </div>
                <div>
                  <span className="text-gray-600">Others: </span>
                  <span className="font-semibold">{hospital.staff.others}</span>
                </div>
              </div>

              {/* Interop Stats */}
              <div className="grid grid-cols-3 gap-2 mt-2 text-sm text-blue-600">
                <div>Shared Patients: {hospital.interop.cross_facility_patients}</div>
                <div>Active Consents: {hospital.interop.active_consents}</div>
                <div>Referrals In: {hospital.interop.referrals_received}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Create Hospital Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Hospital</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Input
              placeholder="Hospital Name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            />
            <Input
              placeholder="NHIS Code"
              value={formData.nhis_code}
              onChange={(e) => setFormData({ ...formData, nhis_code: e.target.value })}
            />
            <Input
              placeholder="Region"
              value={formData.region}
              onChange={(e) => setFormData({ ...formData, region: e.target.value })}
            />
            <Input
              placeholder="Address"
              value={formData.address}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
            />
            <Input
              placeholder="Phone"
              value={formData.phone}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
            />
            <Input
              placeholder="Email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            />
            <Button onClick={handleCreateHospital} className="w-full">
              Create
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Bulk Import Dialog */}
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Bulk Import Staff - {selectedHospital?.name}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              Upload a CSV file with columns: email, full_name, role, ward (optional)
            </p>
            <input
              type="file"
              accept=".csv"
              onChange={handleBulkImport}
              className="w-full"
            />
          </div>
        </DialogContent>
      </Dialog>

      {/* Connectivity Dialog */}
      <Dialog open={connectivityOpen} onOpenChange={setConnectivityOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Interop Connectivity - {selectedHospital?.name}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            <p>
              <span className="font-semibold">Shared Patients:</span>{" "}
              {selectedHospital?.interop.cross_facility_patients}
            </p>
            <p>
              <span className="font-semibold">Active Consents Granted:</span>{" "}
              {selectedHospital?.interop.active_consents}
            </p>
            <p>
              <span className="font-semibold">Referrals Received:</span>{" "}
              {selectedHospital?.interop.referrals_received}
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
