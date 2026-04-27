'use client';

import React, { useState, useEffect } from 'react';
import { useApi } from '@/hooks/use-api';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { AlertCircle, CheckCircle, Loader2 } from 'lucide-react';

interface Room {
  id: string;
  name: string;
  ward_id: string;
  capacity: number;
  available_beds: number;
  occupancy_status: 'available' | 'full' | 'maintenance';
}

interface RoomAssignmentModalProps {
  patient: {
    id: string;
    patient_name: string;
    ed_room_assignment?: string;
  };
  onAssign?: () => void;
  onClose?: () => void;
}

export function RoomAssignmentModal({
  patient,
  onAssign,
  onClose,
}: RoomAssignmentModalProps) {
  const api = useApi();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetchingRooms, setFetchingRooms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Fetch available rooms on modal open
  useEffect(() => {
    const fetchAvailableRooms = async () => {
      setFetchingRooms(true);
      setError(null);
      try {
        const response = await api.get<{ rooms?: Room[] }>('/admin/bed-management?available=true&hospital_scope=true');
        const data = response as { rooms?: Room[] };
        const availableRooms = (data.rooms || []).filter(
          (room: Room) => room.occupancy_status !== 'full'
        );
        setRooms(availableRooms);
        if (availableRooms.length === 0) {
          setError('No available rooms. Please check back later.');
        }
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : 'Failed to load available rooms. Please try again.';
        setError(message);
      } finally {
        setFetchingRooms(false);
      }
    };
    fetchAvailableRooms();
  }, [api]);

  const handleAssignRoom = async () => {
    if (!selectedRoomId) {
      setError('Please select a room before assigning.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await api.post(`/patients/${patient.id}/assign-room`, {
        room_id: selectedRoomId,
      });
      setSuccess(true);
      // Show success for 2 seconds then close
      setTimeout(() => {
        onAssign?.();
        onClose?.();
      }, 1500);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : 'Failed to assign room. Please try again.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const selectedRoom = rooms.find((r) => r.id === selectedRoomId);

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <Card
        className="w-full max-w-md mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <CardHeader>
          <CardTitle className="text-lg">
            Assign ED Room - {patient.patient_name}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Success State */}
          {success && (
            <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <div>
                <p className="font-medium text-green-900">Room assigned!</p>
                <p className="text-sm text-green-700">
                  {selectedRoom?.name} has been assigned successfully.
                </p>
              </div>
            </div>
          )}

          {/* Error State */}
          {error && !success && (
            <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
              <AlertCircle className="w-5 h-5 text-red-600" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Rooms Loading */}
          {fetchingRooms && !success && (
            <div className="flex items-center justify-center gap-2 p-4 text-gray-600">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Loading available rooms...</span>
            </div>
          )}

          {/* Room Selection Dropdown */}
          {!fetchingRooms && !success && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Available Rooms *
                </label>
                <select
                  value={selectedRoomId}
                  onChange={(e) => {
                    setSelectedRoomId(e.target.value);
                    setError(null);
                  }}
                  disabled={rooms.length === 0}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg
                    focus:outline-none focus:ring-2 focus:ring-blue-500
                    disabled:bg-gray-100 disabled:text-gray-500"
                >
                  <option value="">Select a room...</option>
                  {rooms.map((room) => (
                    <option key={room.id} value={room.id}>
                      {room.name} - {room.available_beds} bed
                      {room.available_beds !== 1 ? 's' : ''} available
                      {room.occupancy_status === 'full' ? ' (FULL)' : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Room Details */}
              {selectedRoom && (
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-sm font-medium text-blue-900">
                    {selectedRoom.name}
                  </p>
                  <p className="text-xs text-blue-700 mt-1">
                    Capacity: {selectedRoom.capacity} beds
                  </p>
                  <p className="text-xs text-blue-700">
                    Available: {selectedRoom.available_beds} beds
                  </p>
                  <p className="text-xs text-blue-700">
                    Status:{' '}
                    <span
                      className={
                        selectedRoom.occupancy_status === 'available'
                          ? 'text-green-700'
                          : 'text-yellow-700'
                      }
                    >
                      {selectedRoom.occupancy_status}
                    </span>
                  </p>
                </div>
              )}
            </>
          )}

          {/* Action Buttons */}
          {!success && (
            <div className="flex gap-2 justify-end pt-4 border-t">
              <Button
                variant="secondary"
                onClick={onClose}
                disabled={loading || fetchingRooms}
              >
                Cancel
              </Button>
              <Button
                onClick={handleAssignRoom}
                disabled={!selectedRoomId || loading || fetchingRooms || rooms.length === 0}
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Assigning...
                  </>
                ) : (
                  'Assign Room'
                )}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
