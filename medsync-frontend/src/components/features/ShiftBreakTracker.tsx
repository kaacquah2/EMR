'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useApi } from '@/hooks/use-api';
import { Clock, Play, Pause, LogOut, AlertCircle } from 'lucide-react';

interface ShiftData {
  shift_id: string;
  shift_start: string;
  shift_end?: string;
  break_start?: string;
  break_end?: string;
  break_duration_minutes: number;
  total_shift_hours?: number;
  ward_name: string;
  role: string;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours > 0) {
    return `${hours}h ${mins}m`;
  }
  return `${mins}m`;
}

export function ShiftBreakTracker({ onEndShift }: { onEndShift?: () => void }) {
  const api = useApi();
  const [shift, setShift] = useState<ShiftData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [onBreak, setOnBreak] = useState(false);
  const [elapsedMinutes, setElapsedMinutes] = useState(0);
  const [remainingMinutes, setRemainingMinutes] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  // Fetch current shift
  useEffect(() => {
    const fetchShift = async () => {
      try {
        setLoading(true);
        const response = await api.get<ShiftData>('/shifts/current');
        if (response) {
          setShift(response);
          setOnBreak(!!response.break_start && !response.break_end);
        } else {
          setShift(null);
        }
      } catch (err) {
        console.error('Failed to fetch current shift:', err);
        setShift(null);
      } finally {
        setLoading(false);
      }
    };

    fetchShift();
    const interval = setInterval(fetchShift, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [api]);

  // Update elapsed and remaining time
  useEffect(() => {
    if (!shift) return;

    const interval = setInterval(() => {
      const shiftStart = new Date(shift.shift_start);
      const now = new Date();
      const elapsedMs = now.getTime() - shiftStart.getTime();
      const elapsedMins = Math.floor(elapsedMs / 60000);
      setElapsedMinutes(elapsedMins);

      if (shift.shift_end) {
        const shiftEnd = new Date(shift.shift_end);
        const remainingMs = shiftEnd.getTime() - now.getTime();
        const remainingMins = Math.max(0, Math.floor(remainingMs / 60000));
        setRemainingMinutes(remainingMins);
      }
    }, 60000); // Update every minute

    // Initial calculation
    const shiftStart = new Date(shift.shift_start);
    const now = new Date();
    const elapsedMs = now.getTime() - shiftStart.getTime();
    const elapsedMins = Math.floor(elapsedMs / 60000);
    setElapsedMinutes(elapsedMins);

    if (shift.shift_end) {
      const shiftEnd = new Date(shift.shift_end);
      const remainingMs = shiftEnd.getTime() - now.getTime();
      const remainingMins = Math.max(0, Math.floor(remainingMs / 60000));
      setRemainingMinutes(remainingMins);
    }

    return () => clearInterval(interval);
  }, [shift]);

  const handleBreakToggle = useCallback(
    async (action: 'start' | 'end') => {
      if (!shift || submitting) return;

      try {
        setSubmitting(true);
        setError('');

        if (action === 'start') {
          await api.post(`/shifts/${shift.shift_id}/break/start`, {});
          setOnBreak(true);
        } else {
          await api.post(`/shifts/${shift.shift_id}/break/end`, {});
          setOnBreak(false);
        }

        // Refresh shift data
        const response = await api.get<ShiftData>('/shifts/current');
        if (response) {
          setShift(response);
        }
      } catch (err) {
        setError(`Failed to ${action} break`);
        console.error(err);
      } finally {
        setSubmitting(false);
      }
    },
    [shift, api, submitting]
  );

  const handleEndShift = useCallback(() => {
    if (onEndShift) {
      onEndShift();
    }
  }, [onEndShift]);

  if (loading) {
    return (
      <Card className="bg-gradient-to-br from-blue-50 to-blue-100">
        <CardContent className="pt-6">
          <div className="text-center text-gray-600">Loading shift data...</div>
        </CardContent>
      </Card>
    );
  }

  if (!shift) {
    return (
      <Card className="bg-gradient-to-br from-gray-50 to-gray-100">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-gray-700">
            <Clock className="h-5 w-5" />
            <span>No active shift. Start your shift to begin tracking.</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const shiftStartTime = formatTime(new Date(shift.shift_start));
  const breakDurationDisplay = shift.break_duration_minutes > 0
    ? formatDuration(shift.break_duration_minutes)
    : '0m';

  return (
    <Card className={onBreak ? 'bg-gradient-to-br from-amber-50 to-amber-100' : 'bg-gradient-to-br from-green-50 to-green-100'}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-lg">
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Shift Tracking
          </div>
          {onBreak && (
            <span className="rounded-full bg-amber-200 px-3 py-1 text-sm font-semibold text-amber-900">
              ON BREAK
            </span>
          )}
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">
        {error && (
          <div className="flex gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
            <p>{error}</p>
          </div>
        )}

        {/* Shift Details */}
        <div className="grid grid-cols-2 gap-4 rounded-lg bg-white p-4">
          <div>
            <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">Ward</p>
            <p className="text-sm font-semibold text-gray-900">{shift.ward_name}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">Shift Start</p>
            <p className="text-sm font-semibold text-gray-900">{shiftStartTime}</p>
          </div>
        </div>

        {/* Time Tracking Grid */}
        <div className="grid grid-cols-3 gap-3">
          {/* Elapsed Time */}
          <div className="rounded-lg bg-white p-3 text-center">
            <p className="text-xs font-medium text-gray-600 uppercase">Elapsed</p>
            <p className="text-2xl font-bold text-blue-600">{formatDuration(elapsedMinutes)}</p>
          </div>

          {/* Break Time */}
          <div className="rounded-lg bg-white p-3 text-center">
            <p className="text-xs font-medium text-gray-600 uppercase">Break Time</p>
            <p className="text-2xl font-bold text-amber-600">{breakDurationDisplay}</p>
            {onBreak && <p className="text-xs text-amber-700 mt-1">In progress</p>}
          </div>

          {/* Remaining Time */}
          {shift.shift_end && (
            <div className="rounded-lg bg-white p-3 text-center">
              <p className="text-xs font-medium text-gray-600 uppercase">Remaining</p>
              <p className={`text-2xl font-bold ${remainingMinutes < 120 ? 'text-orange-600' : 'text-green-600'}`}>
                {formatDuration(remainingMinutes)}
              </p>
            </div>
          )}
        </div>

        {/* Break Control */}
        <div className="flex gap-2">
          {!onBreak ? (
            <Button
              onClick={() => handleBreakToggle('start')}
              disabled={submitting}
              variant="outline"
              className="flex-1 gap-2"
            >
              <Pause className="h-4 w-4" />
              Start Break
            </Button>
          ) : (
            <Button
              onClick={() => handleBreakToggle('end')}
              disabled={submitting}
              variant="outline"
              className="flex-1 gap-2"
            >
              <Play className="h-4 w-4" />
              End Break
            </Button>
          )}

          {/* End Shift Button */}
          <Button
            onClick={handleEndShift}
            disabled={submitting}
            variant="danger"
            className="flex-1 gap-2"
          >
            <LogOut className="h-4 w-4" />
            End Shift
          </Button>
        </div>

        {/* Summary Info */}
        <div className="rounded-lg bg-white p-3 text-sm text-gray-700">
          <p className="font-medium mb-1">📋 How it works:</p>
          <ul className="space-y-1 text-xs list-disc list-inside">
            <li>Elapsed time updates every minute automatically</li>
            <li>Click &quot;Start Break&quot; when taking a break, &quot;End Break&quot; when resuming</li>
            <li>Click &quot;End Shift&quot; when done (opens handover form)</li>
            <li>All times are tracked and audited for compliance</li>
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
