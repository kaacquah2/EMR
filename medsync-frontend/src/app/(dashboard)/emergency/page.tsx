'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { List } from 'react-window';
import { useAuth } from '@/lib/auth-context';
import { useApi } from '@/hooks/use-api';
import { EMERGENCY_QUEUE_ROLES, ROOM_ASSIGN_ROLES, hasRole } from "@/lib/permissions";
import { useRouter } from 'next/navigation';
import { RoomAssignmentModal } from '@/components/features/RoomAssignmentModal';
import { 
  AlertTriangle, 
  Clock, 
  Activity, 
  MapPin,
  RefreshCw,
  User
} from 'lucide-react';

interface TriageVitals {
  bp_systolic?: number;
  bp_diastolic?: number;
  heart_rate?: number;
  respiratory_rate?: number;
  spo2?: number;
  temperature?: number;
  pain_scale?: number;
}

interface QueuePatient {
  appointment_id: string;
  patient_id: string;
  patient_name: string;
  patient_age?: number;
  patient_gender?: string;
  triage_color: 'red' | 'yellow' | 'green' | 'blue' | null;
  chief_complaint: string | null;
  wait_time_minutes: number;
  triage_vitals: TriageVitals | null;
  ed_room_assignment: string | null;
  ed_arrival_time: string;
  triaged_at: string | null;
  triaged_by_name: string | null;
}

interface QueueSummary {
  total_waiting: number;
  red_count: number;
  yellow_count: number;
  green_count: number;
  blue_count: number;
  avg_wait_minutes: number;
}

interface QueueData {
  queue: QueuePatient[];
  summary: QueueSummary;
}

const TRIAGE_COLORS = {
  red: {
    bg: 'bg-red-50',
    border: 'border-red-500',
    badge: 'bg-red-600 text-white',
    text: 'text-red-700',
    label: 'RED - Immediate',
    priority: '<5 min',
  },
  yellow: {
    bg: 'bg-amber-50',
    border: 'border-amber-500',
    badge: 'bg-amber-500 text-white',
    text: 'text-amber-700',
    label: 'YELLOW - Urgent',
    priority: '<30 min',
  },
  green: {
    bg: 'bg-green-50',
    border: 'border-green-500',
    badge: 'bg-green-600 text-white',
    text: 'text-green-700',
    label: 'GREEN - Less Urgent',
    priority: '<2 hr',
  },
  blue: {
    bg: 'bg-blue-50',
    border: 'border-blue-500',
    badge: 'bg-blue-500 text-white',
    text: 'text-blue-700',
    label: 'BLUE - Non-Urgent',
    priority: 'Routine',
  },
  null: {
    bg: 'bg-gray-50',
    border: 'border-gray-300',
    badge: 'bg-gray-400 text-white',
    text: 'text-gray-600',
    label: 'Not Triaged',
    priority: 'Pending',
  },
};

const VirtualQueueList = ({ 
  queue, 
  canAssignRoom, 
  setSelectedPatient, 
  router, 
}: { 
  queue: QueuePatient[], 
  canAssignRoom: boolean, 
  setSelectedPatient: (p: QueuePatient) => void, 
  router: ReturnType<typeof useRouter>, 
}) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const Row = ({ index, style }: any) => {
    const patient = queue[index];
    const colorScheme = TRIAGE_COLORS[patient.triage_color as keyof typeof TRIAGE_COLORS || 'null'];
    
    // Inline helpers
    const getWaitTimeColorLocal = (minutes: number, triageColor: string | null) => {
      if (!triageColor) return 'text-gray-600';
      const thresholds = { red: 5, yellow: 30, green: 120, blue: 240 };
      const threshold = thresholds[triageColor as keyof typeof thresholds] || 240;
      if (minutes > threshold * 1.5) return 'text-red-600 font-bold';
      if (minutes > threshold) return 'text-amber-600 font-semibold';
      return 'text-gray-700';
    };

    const formatWaitTimeLocal = (minutes: number) => {
      if (minutes < 60) return `${minutes}m`;
      return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
    };

    return (
      <div style={style} className="pb-3 px-1">
        <div
          className={`bg-white rounded-lg shadow-sm border-l-4 ${colorScheme.border} p-5 hover:shadow-md transition-shadow cursor-pointer h-full`}
          onClick={() => {
            if (canAssignRoom && !patient.ed_room_assignment) {
              setSelectedPatient(patient);
            } else {
              router.push(`/patients/${patient.patient_id}`);
            }
          }}
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <div className="flex items-center justify-center w-8 h-8 bg-gray-100 rounded-full text-sm font-bold text-gray-700">
                  {index + 1}
                </div>
                <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <User className="w-4 h-4 text-gray-500" />
                  {patient.patient_name}
                </h3>
                <span className={`px-3 py-1 rounded-full text-xs font-bold ${colorScheme.badge}`}>
                  {colorScheme.label}
                </span>
                <div className="flex items-center gap-1 text-sm">
                  <Clock className="w-4 h-4 text-gray-500" />
                  <span className={getWaitTimeColorLocal(patient.wait_time_minutes, patient.triage_color)}>
                    {formatWaitTimeLocal(patient.wait_time_minutes)} wait
                  </span>
                </div>
              </div>
              {patient.chief_complaint && (
                <div className="mb-2 text-sm">
                  <span className="font-semibold text-gray-700">Complaint: </span>
                  <span className="text-gray-900">{patient.chief_complaint}</span>
                </div>
              )}
            </div>
            <div className="ml-4 flex flex-col gap-2">
              {patient.ed_room_assignment ? (
                <div className="flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded-lg">
                  <MapPin className="w-4 h-4 text-green-700" />
                  <span className="text-sm font-semibold text-green-900">{patient.ed_room_assignment}</span>
                </div>
              ) : canAssignRoom ? (
                <button
                  onClick={(e) => { e.stopPropagation(); setSelectedPatient(patient); }}
                  className="px-3 py-2 bg-primary text-white text-sm rounded-lg hover:bg-primary-dark transition-colors"
                >
                  Assign Room
                </button>
              ) : (
                <div className="text-sm text-gray-500">No room</div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <List
      rowCount={queue.length}
      rowHeight={160}
      style={{ height: 600, width: "100%" }}
      rowComponent={Row}
      rowProps={{}}
    />
  );
};

export default function EmergencyQueuePage() {
  const { user } = useAuth();
  const api = useApi();
  const router = useRouter();
  const [queueData, setQueueData] = useState<QueueData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [selectedPatient, setSelectedPatient] = useState<QueuePatient | null>(null);

  const fetchQueue = useCallback(async () => {
    try {
      setError(null);
      const data = await api.get<QueueData>('/emergency/queue');
      setQueueData(data);
      setLastRefresh(new Date());
    } catch (err: unknown) {
      if (process.env.NODE_ENV === 'development') {
        console.error('Failed to fetch emergency queue:', err);
      }
      const message = err instanceof Error ? err.message : 'Failed to load emergency queue';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [api]);

  // Auto-refresh every 15 seconds
  useEffect(() => {
    fetchQueue();

    if (autoRefresh) {
      const interval = setInterval(fetchQueue, 15000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, fetchQueue]);


  const formatWaitTime = (minutes: number) => {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
  };

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-gray-500">Please log in to access the emergency queue.</p>
      </div>
    );
  }

  // RBAC-01/02: use centralised ROLES constants
  const canViewQueue = hasRole(user.role, EMERGENCY_QUEUE_ROLES);
  const canAssignRoom = hasRole(user.role, ROOM_ASSIGN_ROLES);

  if (!canViewQueue) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <AlertTriangle className="w-16 h-16 text-amber-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Access Denied</h2>
          <p className="text-gray-600">You do not have permission to view the emergency queue.</p>
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
            <AlertTriangle className="w-8 h-8 text-red-600" />
            Emergency Department Queue
          </h1>
          <p className="text-gray-600 mt-1">
            Real-time triage queue • {user.hospital_name || 'All Hospitals'}
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
            onClick={fetchQueue}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-50 transition-colors"
            data-testid="emergency-refresh-button"
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
      {queueData && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-sm text-gray-600 mb-1">Total Waiting</div>
            <div className="text-2xl font-bold text-gray-900">{queueData.summary.total_waiting}</div>
          </div>
          
          <div className="bg-red-50 p-4 rounded-lg shadow-sm border border-red-200">
            <div className="text-sm text-red-700 mb-1 flex items-center gap-1">
              <div className="w-3 h-3 bg-red-600 rounded-full" />
              RED
            </div>
            <div className="text-2xl font-bold text-red-900">{queueData.summary.red_count}</div>
          </div>
          
          <div className="bg-amber-50 p-4 rounded-lg shadow-sm border border-amber-200">
            <div className="text-sm text-amber-700 mb-1 flex items-center gap-1">
              <div className="w-3 h-3 bg-amber-500 rounded-full" />
              YELLOW
            </div>
            <div className="text-2xl font-bold text-amber-900">{queueData.summary.yellow_count}</div>
          </div>
          
          <div className="bg-green-50 p-4 rounded-lg shadow-sm border border-green-200">
            <div className="text-sm text-green-700 mb-1 flex items-center gap-1">
              <div className="w-3 h-3 bg-green-600 rounded-full" />
              GREEN
            </div>
            <div className="text-2xl font-bold text-green-900">{queueData.summary.green_count}</div>
          </div>
          
          <div className="bg-blue-50 p-4 rounded-lg shadow-sm border border-blue-200">
            <div className="text-sm text-blue-700 mb-1 flex items-center gap-1">
              <div className="w-3 h-3 bg-blue-500 rounded-full" />
              BLUE
            </div>
            <div className="text-2xl font-bold text-blue-900">{queueData.summary.blue_count}</div>
          </div>
          
          <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
            <div className="text-sm text-gray-600 mb-1">Avg Wait</div>
            <div className="text-2xl font-bold text-gray-900">
              {formatWaitTime(Math.round(queueData.summary.avg_wait_minutes))}
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
      {loading && !queueData && (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 text-gray-400 animate-spin" />
        </div>
      )}

      {/* Queue List */}
      {queueData && queueData.queue.length === 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
          <Activity className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-800 mb-2">No Patients in Queue</h3>
          <p className="text-gray-600">The emergency department queue is currently empty.</p>
        </div>
      )}      {queueData && queueData.queue.length > 0 && (
        <div className="h-[600px] w-full">
          <VirtualQueueList 
            queue={queueData.queue} 
            canAssignRoom={canAssignRoom}
            setSelectedPatient={setSelectedPatient}
            router={router}
          />
        </div>
      )}

      {/* Room Assignment Modal */}
      {selectedPatient && canAssignRoom && !selectedPatient.ed_room_assignment && (
        <RoomAssignmentModal
          patient={{
            id: selectedPatient.appointment_id,
            patient_name: selectedPatient.patient_name,
            ed_room_assignment: selectedPatient.ed_room_assignment ?? undefined,
          }}
          onAssign={() => {
            setSelectedPatient(null);
            void fetchQueue();
          }}
          onClose={() => setSelectedPatient(null)}
        />
      )}
    </div>
  );
}
