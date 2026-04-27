'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth-context';
import { useApi } from '@/hooks/use-api';
import {
  Pill,
  Clock,
  AlertTriangle,
  RefreshCw,
  User,
  Package,
} from 'lucide-react';

interface PrescriptionItem {
  prescription_id: string;
  patient_id: string;
  patient_name: string;
  drug_name: string;
  dosage: string;
  frequency: string;
  duration_days: number | null;
  route: string;
  priority: 'stat' | 'urgent' | 'routine';
  prescribed_by: string;
  prescribed_at: string;
  wait_time_minutes: number;
  allergy_conflict: boolean;
  drug_interaction_checked: boolean;
  drug_interactions: DrugInteraction[] | null;
  notes: string | null;
}

interface DrugInteraction {
  interacting_drug: string;
  severity: 'mild' | 'moderate' | 'severe';
  description: string;
}

interface WorklistSummary {
  total_pending: number;
  stat_count: number;
  urgent_count: number;
  routine_count: number;
}

interface WorklistData {
  worklist: PrescriptionItem[];
  summary: WorklistSummary;
}

interface DispenseModalState {
  isOpen: boolean;
  prescription: PrescriptionItem | null;
}

interface DispenseFormData {
  dispensed_quantity: string;
  dispense_notes: string;
  drug_interaction_override: boolean;
}

const PRIORITY_COLORS = {
  stat: {
    bg: 'bg-red-50',
    border: 'border-red-500',
    badge: 'bg-red-600 text-white',
    text: 'text-red-700',
    label: 'STAT',
    dot: 'bg-red-600',
  },
  urgent: {
    bg: 'bg-amber-50',
    border: 'border-amber-500',
    badge: 'bg-amber-500 text-white',
    text: 'text-amber-700',
    label: 'URGENT',
    dot: 'bg-amber-500',
  },
  routine: {
    bg: 'bg-gray-50',
    border: 'border-gray-400',
    badge: 'bg-gray-400 text-white',
    text: 'text-gray-600',
    label: 'ROUTINE',
    dot: 'bg-gray-400',
  },
};

export default function PharmacyWorklistPage() {
  const { user } = useAuth();
  const api = useApi();
  const [worklistData, setWorklistData] = useState<WorklistData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [dispenseModal, setDispenseModal] = useState<DispenseModalState>({
    isOpen: false,
    prescription: null,
  });
  const [dispenseForm, setDispenseForm] = useState<DispenseFormData>({
    dispensed_quantity: '',
    dispense_notes: '',
    drug_interaction_override: false,
  });
  const [dispensing, setDispensing] = useState(false);
  const [dispenseError, setDispenseError] = useState<string | null>(null);

  const fetchWorklist = useCallback(async () => {
    try {
      setError(null);
      const data = await api.get<WorklistData>('/pharmacy/worklist');
      setWorklistData(data);
      setLastRefresh(new Date());
    } catch (err: unknown) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Failed to fetch pharmacy worklist:', err);
      }
      const errorObj = err as { message?: string };
      setError(errorObj.message || 'Failed to load pharmacy worklist');
    } finally {
      setLoading(false);
    }
  }, [api]);

  // Auto-refresh every 15 seconds
  useEffect(() => {
    fetchWorklist();

    if (autoRefresh) {
      const interval = setInterval(fetchWorklist, 15000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, fetchWorklist]);

  const formatWaitTime = (minutes: number) => {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  const getWaitTimeColor = (minutes: number, priority: string) => {
    const thresholds = {
      stat: 5,
      urgent: 30,
      routine: 120,
    };

    const threshold = thresholds[priority as keyof typeof thresholds] || 120;

    if (minutes > threshold * 1.5) return 'text-red-600 font-bold';
    if (minutes > threshold) return 'text-amber-600 font-semibold';
    return 'text-gray-700';
  };

  const openDispenseModal = (prescription: PrescriptionItem) => {
    setDispenseModal({ isOpen: true, prescription });
    setDispenseForm({
      dispensed_quantity: '',
      dispense_notes: '',
      drug_interaction_override: false,
    });
    setDispenseError(null);
  };

  const closeDispenseModal = () => {
    setDispenseModal({ isOpen: false, prescription: null });
    setDispenseForm({
      dispensed_quantity: '',
      dispense_notes: '',
      drug_interaction_override: false,
    });
    setDispenseError(null);
  };

  const handleDispense = async () => {
    if (!dispenseModal.prescription) return;

    const quantity = parseInt(dispenseForm.dispensed_quantity, 10);
    if (isNaN(quantity) || quantity <= 0) {
      setDispenseError('Please enter a valid quantity');
      return;
    }

    const hasInteractions =
      dispenseModal.prescription.drug_interactions &&
      dispenseModal.prescription.drug_interactions.length > 0;

    if (hasInteractions && !dispenseForm.drug_interaction_override) {
      setDispenseError(
        'Please acknowledge the drug interaction warning by checking the override box'
      );
      return;
    }

    setDispensing(true);
    setDispenseError(null);

    try {
      const body: Record<string, unknown> = {
        dispensed_quantity: quantity,
        dispense_notes: dispenseForm.dispense_notes || undefined,
      };

      if (hasInteractions) {
        body.drug_interaction_override = true;
      }

      await api.post(
        `/pharmacy/dispense/${dispenseModal.prescription.prescription_id}`,
        body
      );

      closeDispenseModal();
      // Refresh the worklist
      fetchWorklist();
    } catch (err: unknown) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Failed to dispense prescription:', err);
      }
      const errorObj = err as { message?: string };
      setDispenseError(errorObj.message || 'Failed to dispense prescription');
    } finally {
      setDispensing(false);
    }
  };

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-500">Please log in to access the pharmacy worklist.</p>
      </div>
    );
  }

  // Check role permissions
  const canViewWorklist = [
    'pharmacy_technician',
    'nurse',
    'hospital_admin',
    'super_admin',
  ].includes(user.role);

  if (!canViewWorklist) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <AlertTriangle className="w-16 h-16 text-amber-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Access Denied</h2>
          <p className="text-gray-600">
            You do not have permission to view the pharmacy worklist.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
            <Pill className="w-8 h-8 text-blue-600" />
            Pharmacy Worklist
          </h1>
          <p className="text-gray-600 mt-1">
            Pending prescriptions • {user.hospital_name || 'All Hospitals'}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded border-gray-300"
            />
            Auto-refresh (15s)
          </label>

          <button
            onClick={fetchWorklist}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            data-testid="pharmacy-refresh-button"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {lastRefresh && (
        <div className="text-sm text-gray-500 mb-4">
          Last updated: {lastRefresh.toLocaleTimeString()}
        </div>
      )}

      {/* Summary Cards */}
      {worklistData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-sm text-gray-600 mb-1">Total Pending</div>
            <div className="text-2xl font-bold text-gray-900">
              {worklistData.summary.total_pending}
            </div>
          </div>

          <div className="bg-red-50 p-4 rounded-lg shadow-sm border border-red-200">
            <div className="text-sm text-red-700 mb-1 flex items-center gap-1">
              <div className="w-3 h-3 bg-red-600 rounded-full" />
              STAT
            </div>
            <div className="text-2xl font-bold text-red-900">
              {worklistData.summary.stat_count}
            </div>
          </div>

          <div className="bg-amber-50 p-4 rounded-lg shadow-sm border border-amber-200">
            <div className="text-sm text-amber-700 mb-1 flex items-center gap-1">
              <div className="w-3 h-3 bg-amber-500 rounded-full" />
              URGENT
            </div>
            <div className="text-2xl font-bold text-amber-900">
              {worklistData.summary.urgent_count}
            </div>
          </div>

          <div className="bg-gray-50 p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-sm text-gray-600 mb-1 flex items-center gap-1">
              <div className="w-3 h-3 bg-gray-400 rounded-full" />
              ROUTINE
            </div>
            <div className="text-2xl font-bold text-gray-900">
              {worklistData.summary.routine_count}
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-2 text-red-800">
            <AlertTriangle className="w-5 h-5" />
            <span className="font-semibold">Error:</span>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && !worklistData && (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
        </div>
      )}

      {/* Empty State */}
      {worklistData && worklistData.worklist.length === 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
          <Package className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-800 mb-2">
            No Pending Prescriptions
          </h3>
          <p className="text-gray-600">
            The pharmacy worklist is currently empty. All prescriptions have been dispensed.
          </p>
        </div>
      )}

      {/* Worklist */}
      {worklistData && worklistData.worklist.length > 0 && (
        <div className="space-y-3">
          {worklistData.worklist.map((prescription, index) => {
            const colorScheme = PRIORITY_COLORS[prescription.priority];

            return (
              <div
                key={prescription.prescription_id}
                className={`bg-white rounded-lg shadow-sm border-l-4 ${colorScheme.border} p-5 hover:shadow-md transition-shadow`}
                data-testid={`pharmacy-worklist-item-${index}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    {/* Patient and Priority */}
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                        <User className="w-4 h-4 text-gray-500" />
                        {prescription.patient_name}
                      </h3>

                      <span
                        className={`px-3 py-1 rounded-full text-xs font-bold ${colorScheme.badge}`}
                      >
                        {colorScheme.label}
                      </span>

                      <div className="flex items-center gap-1 text-sm">
                        <Clock className="w-4 h-4 text-gray-500" />
                        <span
                          className={getWaitTimeColor(
                            prescription.wait_time_minutes,
                            prescription.priority
                          )}
                        >
                          {formatWaitTime(prescription.wait_time_minutes)} wait
                        </span>
                      </div>
                    </div>

                    {/* Drug Details */}
                    <div className="mb-3">
                      <div className="flex items-center gap-2 mb-1">
                        <Pill className="w-4 h-4 text-blue-600" />
                        <span className="text-base font-medium text-gray-900">
                          {prescription.drug_name}
                        </span>
                      </div>
                      <div className="text-sm text-gray-700 ml-6">
                        <span className="font-semibold">Dosage:</span>{' '}
                        {prescription.dosage} •{' '}
                        <span className="font-semibold">Frequency:</span>{' '}
                        {prescription.frequency} •{' '}
                        <span className="font-semibold">Route:</span>{' '}
                        {prescription.route}
                        {prescription.duration_days && (
                          <>
                            {' '}
                            • <span className="font-semibold">Duration:</span>{' '}
                            {prescription.duration_days} days
                          </>
                        )}
                      </div>
                    </div>

                    {/* Prescribed By */}
                    <div className="text-sm text-gray-600 mb-2">
                      <span className="font-semibold">Prescribed by:</span>{' '}
                      {prescription.prescribed_by}
                    </div>

                    {/* Warnings */}
                    {prescription.allergy_conflict && (
                      <div className="flex items-center gap-2 px-3 py-2 bg-red-50 border border-red-200 rounded-lg mt-2">
                        <AlertTriangle className="w-5 h-5 text-red-600" />
                        <span className="text-sm font-semibold text-red-800">
                          ALLERGY CONFLICT - Patient has documented allergy to this medication
                        </span>
                      </div>
                    )}

                    {prescription.drug_interactions &&
                      prescription.drug_interactions.length > 0 && (
                        <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg mt-2">
                          <AlertTriangle className="w-5 h-5 text-amber-600" />
                          <span className="text-sm font-semibold text-amber-800">
                            Drug interaction detected:{' '}
                            {prescription.drug_interactions
                              .map((i) => i.interacting_drug)
                              .join(', ')}
                          </span>
                        </div>
                      )}

                    {/* Notes */}
                    {prescription.notes && (
                      <div className="text-sm text-gray-600 mt-2 italic">
                        Note: {prescription.notes}
                      </div>
                    )}
                  </div>

                  {/* Dispense Button */}
                  <div className="ml-4">
                    <button
                      onClick={() => openDispenseModal(prescription)}
                      className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                      data-testid={`dispense-button-${index}`}
                    >
                      <Package className="w-4 h-4" />
                      Dispense
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Dispense Modal */}
      {dispenseModal.isOpen && dispenseModal.prescription && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
          onClick={closeDispenseModal}
        >
          <div
            className="bg-white rounded-lg p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Package className="w-5 h-5 text-green-600" />
              Dispense Medication
            </h3>

            {/* Prescription Summary */}
            <div className="bg-gray-50 rounded-lg p-4 mb-4">
              <div className="font-semibold text-gray-900 mb-2">
                {dispenseModal.prescription.drug_name}
              </div>
              <div className="text-sm text-gray-700">
                <p>
                  <span className="font-medium">Patient:</span>{' '}
                  {dispenseModal.prescription.patient_name}
                </p>
                <p>
                  <span className="font-medium">Dosage:</span>{' '}
                  {dispenseModal.prescription.dosage}
                </p>
                <p>
                  <span className="font-medium">Frequency:</span>{' '}
                  {dispenseModal.prescription.frequency}
                </p>
                <p>
                  <span className="font-medium">Route:</span>{' '}
                  {dispenseModal.prescription.route}
                </p>
                {dispenseModal.prescription.duration_days && (
                  <p>
                    <span className="font-medium">Duration:</span>{' '}
                    {dispenseModal.prescription.duration_days} days
                  </p>
                )}
              </div>
            </div>

            {/* Drug Interaction Warning */}
            {dispenseModal.prescription.drug_interactions &&
              dispenseModal.prescription.drug_interactions.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle className="w-5 h-5 text-amber-600" />
                    <span className="font-semibold text-amber-800">
                      Drug Interaction Warning
                    </span>
                  </div>
                  <ul className="text-sm text-amber-900 space-y-1">
                    {dispenseModal.prescription.drug_interactions.map(
                      (interaction, idx) => (
                        <li key={idx}>
                          <span className="font-medium">
                            {interaction.interacting_drug}
                          </span>{' '}
                          ({interaction.severity}): {interaction.description}
                        </li>
                      )
                    )}
                  </ul>
                </div>
              )}

            {/* Allergy Warning */}
            {dispenseModal.prescription.allergy_conflict && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-600" />
                  <span className="font-semibold text-red-800">
                    ALLERGY CONFLICT - Patient has documented allergy to this
                    medication. Consult prescriber before dispensing.
                  </span>
                </div>
              </div>
            )}

            {/* Form */}
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="dispensed_quantity"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Quantity to Dispense <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  id="dispensed_quantity"
                  min="1"
                  value={dispenseForm.dispensed_quantity}
                  onChange={(e) =>
                    setDispenseForm((prev) => ({
                      ...prev,
                      dispensed_quantity: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Enter quantity"
                  data-testid="dispense-quantity-input"
                />
              </div>

              <div>
                <label
                  htmlFor="dispense_notes"
                  className="block text-sm font-medium text-gray-700 mb-1"
                >
                  Notes (Optional)
                </label>
                <textarea
                  id="dispense_notes"
                  rows={3}
                  value={dispenseForm.dispense_notes}
                  onChange={(e) =>
                    setDispenseForm((prev) => ({
                      ...prev,
                      dispense_notes: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Add any relevant notes..."
                  data-testid="dispense-notes-input"
                />
              </div>

              {/* Override Checkbox for Drug Interactions */}
              {dispenseModal.prescription.drug_interactions &&
                dispenseModal.prescription.drug_interactions.length > 0 && (
                  <div className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      id="drug_interaction_override"
                      checked={dispenseForm.drug_interaction_override}
                      onChange={(e) =>
                        setDispenseForm((prev) => ({
                          ...prev,
                          drug_interaction_override: e.target.checked,
                        }))
                      }
                      className="mt-1 rounded border-gray-300"
                      data-testid="interaction-override-checkbox"
                    />
                    <label
                      htmlFor="drug_interaction_override"
                      className="text-sm text-gray-700"
                    >
                      I acknowledge the drug interaction warning and confirm it is
                      safe to proceed with dispensing this medication.
                    </label>
                  </div>
                )}
            </div>

            {/* Error Message */}
            {dispenseError && (
              <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3">
                <div className="flex items-center gap-2 text-red-800 text-sm">
                  <AlertTriangle className="w-4 h-4" />
                  <span>{dispenseError}</span>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3 mt-6">
              <button
                onClick={closeDispenseModal}
                className="flex-1 px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors"
                data-testid="dispense-cancel-button"
              >
                Cancel
              </button>
              <button
                onClick={handleDispense}
                disabled={dispensing}
                className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                data-testid="dispense-confirm-button"
              >
                {dispensing ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Dispensing...
                  </>
                ) : (
                  <>
                    <Package className="w-4 h-4" />
                    Confirm Dispense
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
