'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth-context';
import { useApi } from '@/hooks/use-api';
import { AlertCircle, TrendingUp, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { hasRole, ALL_ADMIN_ROLES } from '@/lib/permissions';

interface OvertimeStaff {
  staff_id: string;
  staff_name: string;
  total_hours: number;
  overtime_hours: number;
  is_exceeding_limit: boolean;
  shifts_completed: number;
}

export default function OvertimeTrackingPage() {
  const router = useRouter();
  const { user } = useAuth();
  const api = useApi();
  const [staffOvertime, setStaffOvertime] = useState<OvertimeStaff[]>([]);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [thresholdHours, setThresholdHours] = useState(160);
  const [filter, setFilter] = useState<'all' | 'exceeding' | 'at-risk'>('all');

  // RBAC-17: use centralised admin role check
  useEffect(() => {
    if (user && !hasRole(user.role, ALL_ADMIN_ROLES)) {
      router.push('/unauthorized');
    }
  }, [user, router]);

  // Fetch overtime data
  useEffect(() => {
    const fetchOvertimeData = async () => {
      if (!user) return;

      try {
        setLoading(true);
        setError('');

        const monthStr = `${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, '0')}`;
        const response = await api.get<{
          data: OvertimeStaff[];
          overtime_threshold_hours: number;
          month: string;
        }>(`/shifts/overtime-report?month=${monthStr}`);

        if (response) {
          setStaffOvertime(response.data || []);
          setThresholdHours(response.overtime_threshold_hours);
        }
      } catch (err) {
        setError('Failed to load overtime data');
        if (process.env.NODE_ENV === 'development') {
          console.error(err);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchOvertimeData();
  }, [user, currentMonth, api]);

  // Get filtered staff list
  const getFilteredStaff = useCallback(() => {
    switch (filter) {
      case 'exceeding':
        return staffOvertime.filter((s) => s.is_exceeding_limit);
      case 'at-risk':
        return staffOvertime.filter(
          (s) => !s.is_exceeding_limit && s.total_hours > thresholdHours * 0.9
        );
      case 'all':
      default:
        return staffOvertime;
    }
  }, [staffOvertime, filter, thresholdHours]);

  // Calculate statistics
  const stats = {
    totalStaff: staffOvertime.length,
    exceedingCount: staffOvertime.filter((s) => s.is_exceeding_limit).length,
    atRiskCount: staffOvertime.filter(
      (s) => !s.is_exceeding_limit && s.total_hours > thresholdHours * 0.9
    ).length,
    avgOvertimeHours:
      staffOvertime.length > 0
        ? Math.round(
            (staffOvertime.reduce((sum, s) => sum + s.overtime_hours, 0) /
              staffOvertime.length) *
              10
          ) / 10
        : 0,
    totalOvertimeHours: staffOvertime.reduce((sum, s) => sum + s.overtime_hours, 0),
  };

  // Download CSV report
  const handleDownloadReport = useCallback(() => {
    const csvContent = [
      ['Staff Name', 'Total Hours', 'Threshold Hours', 'Overtime Hours', 'Shifts Completed', 'Status'],
      ...staffOvertime.map((staff) => [
        staff.staff_name,
        staff.total_hours.toString(),
        thresholdHours.toString(),
        staff.overtime_hours.toString(),
        staff.shifts_completed.toString(),
        staff.is_exceeding_limit ? 'EXCEEDING' : 'NORMAL',
      ]),
    ]
      .map((row) => row.map((cell) => `"${cell}"`).join(','))
      .join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `overtime-report-${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, '0')}.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  }, [staffOvertime, currentMonth, thresholdHours]);

  if (!user || !hasRole(user.role, ALL_ADMIN_ROLES)) {
    return null;
  }

  const filteredStaff = getFilteredStaff();
  const monthName = currentMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  if (loading && staffOvertime.length === 0) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-center">
          <div className="mb-4 text-lg font-semibold">Loading overtime data...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Overtime Tracking</h1>
          <p className="text-gray-600">Monitor staff overtime and workload distribution</p>
        </div>
        <Button onClick={handleDownloadReport} className="gap-2">
          <Download className="h-4 w-4" />
          Download Report
        </Button>
      </div>

      {/* Error message */}
      {error && (
        <div className="flex gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-800">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {/* Month Navigation */}
      <div className="flex items-center justify-between rounded-lg bg-white p-4 shadow-sm">
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1))}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div className="flex items-center px-4 font-semibold min-w-48">
            {monthName}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1))}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setCurrentMonth(new Date())}
        >
          Current Month
        </Button>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-600">Total Staff</p>
              <p className="text-3xl font-bold">{stats.totalStaff}</p>
            </div>
          </CardContent>
        </Card>

        <Card accent="red">
          <CardContent className="pt-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-600">Exceeding Threshold</p>
              <p className="text-3xl font-bold text-red-600">{stats.exceedingCount}</p>
              <p className="text-xs text-gray-500">{((stats.exceedingCount / stats.totalStaff) * 100).toFixed(0)}% of staff</p>
            </div>
          </CardContent>
        </Card>

        <Card accent="amber">
          <CardContent className="pt-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-600">At Risk (90%+)</p>
              <p className="text-3xl font-bold text-amber-600">{stats.atRiskCount}</p>
              <p className="text-xs text-gray-500">{((stats.atRiskCount / stats.totalStaff) * 100).toFixed(0)}% of staff</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-600">Avg Overtime</p>
              <p className="text-3xl font-bold">{stats.avgOvertimeHours}h</p>
              <p className="text-xs text-gray-500">Total: {stats.totalOvertimeHours}h</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 border-b border-gray-200">
        {(['all', 'exceeding', 'at-risk'] as const).map((filterOption) => (
          <button
            key={filterOption}
            onClick={() => setFilter(filterOption)}
            className={`px-4 py-2 font-medium text-sm transition-colors ${
              filter === filterOption
                ? 'border-b-2 border-blue-600 text-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {filterOption === 'all'
              ? `All Staff (${staffOvertime.length})`
              : filterOption === 'exceeding'
              ? `Exceeding (${stats.exceedingCount})`
              : `At Risk (${stats.atRiskCount})`}
          </button>
        ))}
      </div>

      {/* Overtime Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Staff Overtime Details
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b bg-gray-50">
                <tr className="text-left">
                  <th className="px-4 py-3 font-semibold">Staff Name</th>
                  <th className="px-4 py-3 font-semibold">Total Hours</th>
                  <th className="px-4 py-3 font-semibold">Threshold</th>
                  <th className="px-4 py-3 font-semibold">Overtime</th>
                  <th className="px-4 py-3 font-semibold">Utilization %</th>
                  <th className="px-4 py-3 font-semibold">Shifts</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredStaff.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-gray-500">
                      No staff found matching the selected filter
                    </td>
                  </tr>
                ) : (
                  filteredStaff.map((staff) => {
                    const utilization = Math.round((staff.total_hours / thresholdHours) * 100);
                    const isAtRisk = !staff.is_exceeding_limit && utilization >= 90;

                    return (
                      <tr key={staff.staff_id} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium">{staff.staff_name}</td>
                        <td className="px-4 py-3">{staff.total_hours}h</td>
                        <td className="px-4 py-3 text-gray-600">{thresholdHours}h</td>
                        <td className="px-4 py-3">
                          <span
                            className={`font-semibold ${
                              staff.overtime_hours > 0 ? 'text-red-600' : 'text-green-600'
                            }`}
                          >
                            {staff.overtime_hours}h
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="space-y-1">
                            <div className="text-sm font-medium">{utilization}%</div>
                            <div className="h-2 w-24 overflow-hidden rounded-full bg-gray-200">
                              <div
                                className={`h-full transition-colors ${
                                  utilization >= 100
                                    ? 'bg-red-600'
                                    : utilization >= 90
                                    ? 'bg-amber-500'
                                    : 'bg-green-600'
                                }`}
                                style={{ width: `${Math.min(utilization, 100)}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3">{staff.shifts_completed}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-block rounded px-2 py-1 text-xs font-medium ${
                              staff.is_exceeding_limit
                                ? 'bg-red-100 text-red-700'
                                : isAtRisk
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-green-100 text-green-700'
                            }`}
                          >
                            {staff.is_exceeding_limit ? 'EXCEEDING' : isAtRisk ? 'AT RISK' : 'NORMAL'}
                          </span>
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

      {/* Notes */}
      <div className="rounded-lg bg-blue-50 p-4 text-sm text-blue-800">
        <p className="font-semibold mb-1">📋 Overtime Threshold Information</p>
        <p>
          The monthly overtime threshold is <strong>{thresholdHours} hours</strong>. Staff members exceeding this
          threshold require manager approval for additional shifts. The &quot;At Risk&quot; category includes staff at 90% or
          higher utilization.
        </p>
      </div>
    </div>
  );
}
