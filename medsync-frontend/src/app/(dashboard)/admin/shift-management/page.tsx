'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth-context';
import { useApi } from '@/hooks/use-api';
import { AlertCircle, Calendar, Plus, ChevronLeft, ChevronRight } from 'lucide-react';
import { ConflictDetectionModal } from '@/components/features/ConflictDetectionModal';
import { hasRole, ALL_ADMIN_ROLES } from '@/lib/permissions';

interface Shift {
  shift_id: string;
  staff_name: string;
  staff_id: string;
  ward_name: string | null;
  shift_start: string;
  shift_end: string | null;
  status: string;
}

interface StaffMember {
  id: string;
  username: string;
  first_name: string;
  last_name: string;
  role: string;
}

interface Ward {
  id: string;
  name: string;
  hospital_id: string;
}

interface ShiftConflict {
  conflicting_shift_id: string;
  overlap_start: string;
  overlap_end: string;
  conflict_type: string;
}

interface ShiftListResponse {
  data: Shift[];
  total?: number;
}

interface StaffListResponse {
  data: StaffMember[];
  total?: number;
}

interface WardListResponse {
  data: Ward[];
}

interface ConflictCheckResponse {
  has_conflict: boolean;
  conflicts?: ShiftConflict[];
}

export default function ShiftManagementPage() {
  const router = useRouter();
  const { user } = useAuth();
  const api = useApi();
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [staffList, setStaffList] = useState<StaffMember[]>([]);
  const [wardList, setWardList] = useState<Ward[]>([]);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [, setSelectedShift] = useState<Shift | null>(null);

  // Form state
  const [formData, setFormData] = useState({
    staff_id: '',
    ward_id: '',
    scheduled_start: '',
    scheduled_end: '',
  });

  // Conflict detection state
  const [showConflictModal, setShowConflictModal] = useState(false);
  const [detectedConflicts, setDetectedConflicts] = useState<ShiftConflict[]>([]);
  const [, setPendingFormSubmit] = useState(false);

  // RBAC-17: use centralised admin role check
  useEffect(() => {
    if (user && !hasRole(user.role, ALL_ADMIN_ROLES)) {
      router.push('/unauthorized');
    }
  }, [user, router]);

  // Fetch shifts and staff
  useEffect(() => {
    const fetchData = async () => {
      if (!user) return;

      try {
        setLoading(true);
        setError('');

        // Get shifts for current month
        const from = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1)
          .toISOString()
          .split('T')[0];
        const to = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0)
          .toISOString()
          .split('T')[0];

        const shiftsResponse = await api.get<ShiftListResponse>(`/shifts/roster?date_from=${from}&date_to=${to}&limit=100`);
        if (shiftsResponse) {
          setShifts(shiftsResponse.data || []);
        }

        // Get staff list (from users endpoint)
        const staffResponse = await api.get<StaffListResponse>(`/admin/users?limit=500`);
        if (staffResponse) {
          // Filter to clinical roles only
          setStaffList(
            staffResponse.data?.filter((u: StaffMember) =>
              ['nurse', 'lab_technician', 'doctor'].includes(u.role)
            ) || []
          );
        }

        // Get wards (from facilities endpoint)
        const wardsResponse = await api.get<WardListResponse>(`/admin/wards`);
        if (wardsResponse) {
          setWardList(wardsResponse.data || []);
        }
      } catch (err) {
        setError('Failed to load shift data');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [user, currentDate, api]);

  // Handle creating new shift - first check for conflicts
  // Submit shift to backend
  const submitShift = useCallback(
    async (overrideReason?: string) => {
      try {
        setLoading(true);
        setError('');

        const response = await api.post(`/shifts/roster/create`, {
          staff_id: formData.staff_id,
          ward_id: formData.ward_id || null,
          scheduled_start: formData.scheduled_start,
          scheduled_end: formData.scheduled_end,
          override_reason: overrideReason,
        });

        if (response) {
          // Refresh shifts
          const from = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1)
            .toISOString()
            .split('T')[0];
          const to = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 0)
            .toISOString()
            .split('T')[0];

          const shiftsResponse = await api.get<ShiftListResponse>(`/shifts/roster?date_from=${from}&date_to=${to}&limit=100`);
          if (shiftsResponse) {
            setShifts(shiftsResponse.data || []);
          }

          setShowCreateForm(false);
          setFormData({ staff_id: '', ward_id: '', scheduled_start: '', scheduled_end: '' });
          setShowConflictModal(false);
          setPendingFormSubmit(false);
        } else {
          setError('Failed to create shift');
        }
      } catch (err) {
        setError('Error creating shift');
        console.error(err);
      } finally {
        setLoading(false);
      }
    },
    [formData, currentDate, api]
  );

  const handleCreateShift = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!formData.staff_id || !formData.scheduled_start || !formData.scheduled_end) {
        setError('Please fill in all required fields');
        return;
      }

      try {
        setLoading(true);
        setError('');

        // Check for conflicts first
        const conflictCheckResponse = await api.post<ConflictCheckResponse>(`/shifts/check-conflict`, {
          staff_id: formData.staff_id,
          scheduled_start: formData.scheduled_start,
          scheduled_end: formData.scheduled_end,
        });

        if (conflictCheckResponse?.has_conflict) {
          // Show conflict modal
          const conflicts = conflictCheckResponse.conflicts || [];
          setDetectedConflicts(conflicts);
          setPendingFormSubmit(true);
          setShowConflictModal(true);
          setLoading(false);
          return;
        }

        // No conflicts, proceed with shift creation
        await submitShift();
      } catch (err) {
        setError('Error checking for conflicts');
        console.error(err);
        setLoading(false);
      }
    },
    [formData, api, submitShift]
  );

  // Handle deleting shift
  const handleDeleteShift = useCallback(
    async (shiftId: string) => {
      if (!confirm('Are you sure you want to delete this shift?')) return;

      try {
        setLoading(true);
        setError('');

        const response = await api.delete(`/shifts/schedule/${shiftId}/delete`);

        if (response) {
          // Refresh shifts
          setShifts(shifts.filter((s) => s.shift_id !== shiftId));
        } else {
          setError('Failed to delete shift');
        }
      } catch (err) {
        setError('Error deleting shift');
        console.error(err);
      } finally {
        setLoading(false);
      }
    },
    [shifts, api]
  );

  // Get days in month
  const getDaysInMonth = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();

    return { daysInMonth, startingDayOfWeek, year, month };
  };

  // Get shifts for a specific date
  const getShiftsForDate = (date: number) => {
    const { year, month } = getDaysInMonth();
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(date).padStart(2, '0')}`;
    return shifts.filter((shift) => shift.shift_start.split('T')[0] === dateStr);
  };

  if (!user || !hasRole(user.role, ALL_ADMIN_ROLES)) {
    return null;
  }

  if (loading && shifts.length === 0) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="mb-4 text-lg font-semibold">Loading shift management...</div>
        </div>
      </div>
    );
  }

  const { daysInMonth, startingDayOfWeek, year, month } = getDaysInMonth();
  const monthName = new Date(year, month).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const calendarDays = [];
  for (let i = 0; i < startingDayOfWeek; i++) {
    calendarDays.push(null);
  }
  for (let i = 1; i <= daysInMonth; i++) {
    calendarDays.push(i);
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Shift Management</h1>
          <p className="text-gray-600">Create and manage staff shifts for {user.hospital_name || 'your facility'}</p>
        </div>
        <Button onClick={() => setShowCreateForm(!showCreateForm)} className="gap-2">
          <Plus className="h-4 w-4" />
          New Shift
        </Button>
      </div>

      {/* Error message */}
      {error && (
        <div className="flex gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {/* Create Shift Form */}
      {showCreateForm && (
        <Card className="border-blue-200 bg-blue-50">
          <CardHeader>
            <CardTitle>Create New Shift</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateShift} className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium">Staff Member *</label>
                  <select
                    value={formData.staff_id}
                    onChange={(e) => setFormData({ ...formData, staff_id: e.target.value })}
                    className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    required
                  >
                    <option value="">Select a staff member...</option>
                    {staffList.map((staff) => (
                      <option key={staff.id} value={staff.id}>
                        {staff.first_name} {staff.last_name} ({staff.role})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium">Ward (Optional)</label>
                  <select
                    value={formData.ward_id}
                    onChange={(e) => setFormData({ ...formData, ward_id: e.target.value })}
                    className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                  >
                    <option value="">No ward assignment</option>
                    {wardList.map((ward) => (
                      <option key={ward.id} value={ward.id}>
                        {ward.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium">Start Date & Time *</label>
                  <input
                    type="datetime-local"
                    value={formData.scheduled_start}
                    onChange={(e) => setFormData({ ...formData, scheduled_start: e.target.value })}
                    className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium">End Date & Time *</label>
                  <input
                    type="datetime-local"
                    value={formData.scheduled_end}
                    onChange={(e) => setFormData({ ...formData, scheduled_end: e.target.value })}
                    className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    required
                  />
                </div>
              </div>

              <div className="flex gap-2 pt-4">
                <Button type="submit" disabled={loading}>
                  {loading ? 'Creating...' : 'Create Shift'}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowCreateForm(false);
                    setFormData({ staff_id: '', ward_id: '', scheduled_start: '', scheduled_end: '' });
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Calendar View */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5" />
                {monthName}
              </CardTitle>
              <p className="text-sm text-gray-600">Showing {shifts.length} shifts this month</p>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1))}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentDate(new Date())}
              >
                Today
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1))}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {/* Day header */}
          <div className="mb-4 grid grid-cols-7 gap-2">
            {dayNames.map((day) => (
              <div key={day} className="text-center font-semibold text-sm">
                {day}
              </div>
            ))}
          </div>

          {/* Calendar grid */}
          <div className="grid grid-cols-7 gap-2">
            {calendarDays.map((day, idx) => (
              <div
                key={idx}
                className={`min-h-24 rounded-lg border p-2 ${
                  day === null
                    ? 'bg-gray-50'
                    : day === new Date().getDate() &&
                      currentDate.getMonth() === new Date().getMonth() &&
                      currentDate.getFullYear() === new Date().getFullYear()
                    ? 'border-blue-300 bg-blue-50'
                    : 'border-gray-200 bg-white'
                }`}
              >
                {day && (
                  <div className="space-y-1">
                    <div className="font-semibold text-sm">{day}</div>
                    <div className="space-y-1 text-xs">
                      {getShiftsForDate(day).map((shift) => (
                        <div
                          key={shift.shift_id}
                          className="rounded bg-amber-100 p-1 hover:bg-amber-200 cursor-pointer"
                          onClick={() => setSelectedShift(shift)}
                        >
                          <div className="font-medium truncate">{shift.staff_name.split(' ')[0]}</div>
                          <div className="text-gray-600">
                            {new Date(shift.shift_start).toLocaleTimeString('en-US', {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Shift List Table */}
      <Card>
        <CardHeader>
          <CardTitle>All Shifts</CardTitle>
          <p className="text-sm text-gray-600">Complete list of shifts for {monthName}</p>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr className="text-left">
                  <th className="py-2 font-semibold">Staff</th>
                  <th className="py-2 font-semibold">Ward</th>
                  <th className="py-2 font-semibold">Start</th>
                  <th className="py-2 font-semibold">End</th>
                  <th className="py-2 font-semibold">Duration</th>
                  <th className="py-2 font-semibold">Status</th>
                  <th className="py-2 font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {shifts.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-4 text-center text-gray-500">
                      No shifts scheduled for this month
                    </td>
                  </tr>
                ) : (
                  shifts.map((shift) => {
                    const startDate = new Date(shift.shift_start);
                    const endDate = shift.shift_end ? new Date(shift.shift_end) : null;
                    const duration = endDate
                      ? Math.round((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60) * 10) / 10
                      : '-';

                    return (
                      <tr key={shift.shift_id} className="border-b hover:bg-gray-50">
                        <td className="py-3">{shift.staff_name}</td>
                        <td className="py-3">{shift.ward_name || '-'}</td>
                        <td className="py-3">{startDate.toLocaleString()}</td>
                        <td className="py-3">{endDate ? endDate.toLocaleString() : '-'}</td>
                        <td className="py-3">{duration} hrs</td>
                        <td className="py-3">
                          <span
                            className={`inline-block rounded px-2 py-1 text-xs font-medium ${
                              shift.status === 'completed'
                                ? 'bg-green-100 text-green-700'
                                : shift.status === 'active'
                                ? 'bg-blue-100 text-blue-700'
                                : 'bg-gray-100 text-gray-700'
                            }`}
                          >
                            {shift.status}
                          </span>
                        </td>
                        <td className="py-3">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteShift(shift.shift_id)}
                            className="text-red-600 hover:text-red-700"
                          >
                            Delete
                          </Button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Conflict Detection Modal */}
      <ConflictDetectionModal
        staffName={
          staffList.find((s) => s.id === formData.staff_id)
            ? `${staffList.find((s) => s.id === formData.staff_id)?.first_name} ${staffList.find((s) => s.id === formData.staff_id)?.last_name}`
            : 'Selected Staff'
        }
        requestedStart={formData.scheduled_start}
        requestedEnd={formData.scheduled_end}
        conflicts={detectedConflicts}
        isOpen={showConflictModal}
        onClose={() => {
          setShowConflictModal(false);
          setPendingFormSubmit(false);
        }}
        onConfirm={submitShift}
        onCancel={() => {
          setShowConflictModal(false);
          setPendingFormSubmit(false);
        }}
      />
    </div>
  );
}
