'use client';

import { useState, useCallback } from 'react';
import { AlertTriangle, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface Conflict {
  shift_id?: string;
  conflicting_shift_id?: string;
  shift_start?: string;
  shift_end?: string;
  overlap_start?: string;
  overlap_end?: string;
  conflict_type?: string;
}

interface ConflictDetectionModalProps {
  staffName: string;
  requestedStart: string;
  requestedEnd: string;
  conflicts: Conflict[];
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (reason?: string) => Promise<void>;
  onCancel: () => void;
}

export function ConflictDetectionModal({
  staffName,
  requestedStart,
  requestedEnd,
  conflicts,
  isOpen,
  onConfirm,
  onCancel,
}: ConflictDetectionModalProps) {
  const [loading, setLoading] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');

  const handleConfirm = useCallback(async () => {
    setLoading(true);
    try {
      await onConfirm(overrideReason || 'Staff requested override');
      setOverrideReason('');
    } finally {
      setLoading(false);
    }
  }, [onConfirm, overrideReason]);

  const handleCancel = useCallback(() => {
    setOverrideReason('');
    onCancel();
  }, [onCancel]);

  if (!isOpen) return null;

  const formatDateTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    });
  };

  const calculateDuration = (start: string, end: string) => {
    const startDate = new Date(start);
    const endDate = new Date(end);
    const minutes = Math.round((endDate.getTime() - startDate.getTime()) / (1000 * 60));
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-lg bg-white shadow-xl">
        {/* Header */}
        <div className="border-b border-red-200 bg-red-50 px-6 py-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-6 w-6 text-red-600" />
            <div>
              <h2 className="text-lg font-bold text-red-900">Shift Conflict Detected</h2>
              <p className="text-sm text-red-700">
                {staffName} has existing shift(s) that overlap with this time period
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="space-y-4 px-6 py-4">
          {/* Requested Shift Details */}
          <div className="rounded-lg bg-blue-50 p-4">
            <h3 className="mb-2 font-semibold text-blue-900">Requested Shift</h3>
            <div className="space-y-1 text-sm text-blue-800">
              <div>
                <span className="font-medium">Start:</span> {formatDateTime(requestedStart)}
              </div>
              <div>
                <span className="font-medium">End:</span> {formatDateTime(requestedEnd)}
              </div>
              <div>
                <span className="font-medium">Duration:</span>{' '}
                {calculateDuration(requestedStart, requestedEnd)}
              </div>
            </div>
          </div>

          {/* Existing Conflicts */}
          <div>
            <h3 className="mb-2 font-semibold text-gray-900">Conflicting Shifts ({conflicts.length})</h3>
            <div className="space-y-2">
              {conflicts.map((conflict, idx) => (
                <div key={conflict.shift_id ?? conflict.conflicting_shift_id ?? idx} className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-600" />
                    <div className="flex-1 space-y-1">
                      <div className="font-medium text-red-900">Conflict #{idx + 1}</div>
                      <div className="text-red-800">
                        {formatDateTime(conflict.shift_start ?? conflict.overlap_start ?? '')} to {formatDateTime(conflict.shift_end ?? conflict.overlap_end ?? '')}
                      </div>
                      <div className="text-xs text-red-700">
                        Duration: {calculateDuration(conflict.shift_start ?? conflict.overlap_start ?? '', conflict.shift_end ?? conflict.overlap_end ?? '')}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Override Reason */}
          <div className="space-y-2 border-t pt-4">
            <label className="block text-sm font-medium text-gray-700">
              Override Reason (Optional) *
            </label>
            <textarea
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              placeholder="e.g., 'Staff requested', 'Urgent coverage needed', etc."
              className="h-20 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder-gray-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500">
              This reason will be logged for audit purposes if you proceed with scheduling.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t bg-gray-50 px-6 py-4">
          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={handleCancel}
              disabled={loading}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleConfirm}
              disabled={loading}
              className="flex-1 bg-red-600 hover:bg-red-700"
            >
              {loading ? 'Creating...' : 'Proceed Anyway'}
            </Button>
          </div>
          <p className="mt-3 text-center text-xs text-gray-600">
            ⚠️ Proceeding will override the conflict. This action will be audited.
          </p>
        </div>
      </div>
    </div>
  );
}
