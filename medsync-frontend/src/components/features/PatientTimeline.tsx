"use client";

import * as React from "react";
import { useState, useMemo } from "react";
import { usePatientTimeline } from "@/hooks/use-patient-timeline";
import { SlideOver } from "@/components/features/SlideOver";
import { ListSkeleton } from "@/components/ui/skeleton";
import type { TimelineEvent, TimelineEventType } from "@/lib/types";

interface PatientTimelineProps {
  patientId: string;
}

type ZoomLevel = "all" | "1y" | "6m" | "3m" | "30d";

interface EventFilters {
  encounter: boolean;
  admission: boolean;
  lab_result: boolean;
  vital: boolean;
  prescription: boolean;
  alert: boolean;
}

const EVENT_TYPE_LABELS: Record<TimelineEventType, string> = {
  encounter: "Encounters",
  admission: "Admissions",
  lab_result: "Lab Results",
  vital: "Vitals",
  prescription: "Prescriptions",
  alert: "Alerts",
};

const EVENT_TYPE_COLORS: Record<
  TimelineEventType,
  { bg: string; text: string; border: string; badge: string }
> = {
  encounter: {
    bg: "bg-blue-100",
    text: "text-blue-900",
    border: "border-blue-300",
    badge: "bg-blue-600 text-white",
  },
  admission: {
    bg: "bg-purple-100",
    text: "text-purple-900",
    border: "border-purple-300",
    badge: "bg-purple-600 text-white",
  },
  lab_result: {
    bg: "bg-amber-100",
    text: "text-amber-900",
    border: "border-amber-300",
    badge: "bg-amber-600 text-white",
  },
  vital: {
    bg: "bg-green-100",
    text: "text-green-900",
    border: "border-green-300",
    badge: "bg-green-600 text-white",
  },
  prescription: {
    bg: "bg-teal-100",
    text: "text-teal-900",
    border: "border-teal-300",
    badge: "bg-teal-600 text-white",
  },
  alert: {
    bg: "bg-red-100",
    text: "text-red-900",
    border: "border-red-300",
    badge: "bg-red-600 text-white",
  },
};

const ZOOM_OPTIONS: Array<{ label: string; value: ZoomLevel }> = [
  { label: "All time", value: "all" },
  { label: "1 year", value: "1y" },
  { label: "6 months", value: "6m" },
  { label: "3 months", value: "3m" },
  { label: "30 days", value: "30d" },
];

/**
 * Calculate the cutoff date based on zoom level
 */
function calculateCutoffDate(zoom: ZoomLevel): Date | null {
  const today = new Date();
  switch (zoom) {
    case "1y":
      return new Date(today.setDate(today.getDate() - 365));
    case "6m":
      return new Date(today.setDate(today.getDate() - 180));
    case "3m":
      return new Date(today.setDate(today.getDate() - 90));
    case "30d":
      return new Date(today.setDate(today.getDate() - 30));
    case "all":
    default:
      return null;
  }
}

/**
 * Format a date for display
 */
function formatEventDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffTime = Math.abs(now.getTime() - date.getTime());
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  // Format as "MMM DD, YYYY"
  const options: Intl.DateTimeFormatOptions = {
    month: "short",
    day: "numeric",
    year: "numeric",
  };

  const formatted = date.toLocaleDateString("en-US", options);

  // Add relative time for recent events
  if (diffDays === 0) return `Today, ${date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })}`;
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;

  return formatted;
}

/**
 * Get summary text for an event
 */
function getEventSummary(event: TimelineEvent): string {
  switch (event.type) {
    case "encounter":
      return `${event.encounter.encounter_type || "Encounter"} - ${event.encounter.chief_complaint || event.encounter.encounter_type || "Clinical visit"}`;
    case "admission":
      return `Admitted to ${event.ward_name || "Ward"} - ${event.reason || "Patient admission"}`;
    case "lab_result":
      return `Lab: ${event.test_name} - Result: ${event.lab_result.result_value || "Pending"}`;
    case "vital":
      return event.summary || "Vital signs recorded";
    case "prescription":
      return `${event.drug_name} - ${event.prescription.dosage} ${event.prescription.frequency}`;
    case "alert":
      return event.message || "Clinical alert";
    default:
      return "Event recorded";
  }
}

/**
 * Get severity color for lab results
 */
function getSeverityColor(
  event: TimelineEvent
): string {
  if (event.type === "lab_result") {
    switch (event.severity) {
      case "critical":
        return "text-red-600 font-semibold";
      case "abnormal":
        return "text-orange-600 font-medium";
      case "normal":
      default:
        return "text-green-600";
    }
  }
  return "";
}

/**
 * PatientTimeline - Display events on a vertical scrollable timeline
 */
export function PatientTimeline({ patientId }: PatientTimelineProps) {
  const { events, loading, error, refetch } = usePatientTimeline(patientId);
  const [zoom, setZoom] = useState<ZoomLevel>("all");
  const [filters, setFilters] = useState<EventFilters>({
    encounter: true,
    admission: true,
    lab_result: true,
    vital: true,
    prescription: true,
    alert: true,
  });
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);
  const [showDetail, setShowDetail] = useState(false);

  // Filter events based on zoom and filters
  const filteredEvents = useMemo(() => {
    const cutoffDate = calculateCutoffDate(zoom);

    return events.filter((event) => {
      // Check zoom level filter
      if (cutoffDate) {
        const eventDate = new Date(event.date);
        if (eventDate < cutoffDate) return false;
      }

      // Check event type filter
      return filters[event.type as keyof EventFilters];
    });
  }, [events, zoom, filters]);

  const handleFilterToggle = (eventType: TimelineEventType) => {
    setFilters((prev) => ({
      ...prev,
      [eventType]: !prev[eventType],
    }));
  };

  const handleEventClick = (event: TimelineEvent) => {
    setSelectedEvent(event);
    setShowDetail(true);
  };

  // Render event details in SlideOver
  const renderEventDetails = (event: TimelineEvent) => {
    switch (event.type) {
      case "encounter":
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Type</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                {event.encounter.encounter_type || "Encounter"}
              </p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Chief Complaint</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                {event.encounter.chief_complaint || "No chief complaint recorded"}
              </p>
            </div>
            {event.encounter.hpi && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">History of Present Illness</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.encounter.hpi}</p>
              </div>
            )}
            {event.encounter.examination_findings && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Examination Findings</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.encounter.examination_findings}</p>
              </div>
            )}
            {event.encounter.assessment_plan && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Assessment & Plan</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.encounter.assessment_plan}</p>
              </div>
            )}
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Provider</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.provider || "Unknown"}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Date</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{formatEventDate(event.date)}</p>
            </div>
          </div>
        );

      case "admission":
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Ward</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.ward_name || "Unknown"}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Admitted At</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{formatEventDate(event.admission_date)}</p>
            </div>
            {event.discharge_date && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Discharged At</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{formatEventDate(event.discharge_date)}</p>
              </div>
            )}
            {event.reason && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Discharge Reason</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.reason}</p>
              </div>
            )}
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Provider</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.provider || "Unknown"}</p>
            </div>
          </div>
        );

      case "lab_result":
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Test Name</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.test_name}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Result Value</h3>
              <p className={`mt-1 text-sm font-medium ${getSeverityColor(event)}`}>
                {event.lab_result.result_value || "Pending"}
              </p>
            </div>
            {event.reference_range && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Reference Range</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.reference_range}</p>
              </div>
            )}
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Status</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400 capitalize">{event.severity}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Date</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{formatEventDate(event.date)}</p>
            </div>
          </div>
        );

      case "vital":
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Vitals Summary</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.summary || "No data"}</p>
            </div>
            {event.vital.bp_systolic && event.vital.bp_diastolic && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Blood Pressure</h3>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                    {event.vital.bp_systolic}/{event.vital.bp_diastolic} mmHg
                  </p>
                </div>
              </div>
            )}
            {event.vital.pulse_bpm && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Heart Rate</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.vital.pulse_bpm} bpm</p>
              </div>
            )}
            {event.vital.resp_rate && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Respiratory Rate</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.vital.resp_rate} breaths/min</p>
              </div>
            )}
            {event.vital.temperature_c && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Temperature</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.vital.temperature_c}°C</p>
              </div>
            )}
            {event.vital.spo2_percent && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Oxygen Saturation</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.vital.spo2_percent}%</p>
              </div>
            )}
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Date</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{formatEventDate(event.date)}</p>
            </div>
          </div>
        );

      case "prescription":
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Drug Name</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.drug_name}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Dosage</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.prescription.dosage}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Frequency</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.prescription.frequency}</p>
            </div>
            {event.prescription.duration_days && (
              <div>
                <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Duration</h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.prescription.duration_days} days</p>
              </div>
            )}
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Route</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400 capitalize">{event.prescription.route}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Dispense Status</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400 capitalize">
                {event.dispense_status}
              </p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Date</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{formatEventDate(event.date)}</p>
            </div>
          </div>
        );

      case "alert":
        return (
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Message</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{event.message}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Severity</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400 capitalize">{event.severity}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Status</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400 capitalize">{event.alert.status}</p>
            </div>
            <div>
              <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">Date</h3>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{formatEventDate(event.date)}</p>
            </div>
          </div>
        );

      default:
        return <p className="text-sm text-gray-600 dark:text-gray-400">No details available</p>;
    }
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-slate-900 dark:bg-slate-100">
      {/* Zoom Controls */}
      <div className="flex flex-wrap gap-2 p-4 border-b border-gray-200 dark:border-gray-700">
        {ZOOM_OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={() => setZoom(option.value)}
            className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
              zoom === option.value
                ? "border-2 border-blue-600 bg-blue-50 text-blue-900 dark:bg-blue-900/20 dark:text-blue-300"
                : "border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-gray-400 dark:hover:border-gray-500"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {/* Filter Chips */}
      <div className="flex flex-wrap gap-2 p-4 border-b border-gray-200 dark:border-gray-700">
        {(Object.keys(EVENT_TYPE_LABELS) as TimelineEventType[]).map((eventType) => (
          <button
            key={eventType}
            onClick={() => handleFilterToggle(eventType)}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
              filters[eventType]
                ? `${EVENT_TYPE_COLORS[eventType].badge}`
                : `border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:border-gray-400 dark:hover:border-gray-500`
            }`}
          >
            {EVENT_TYPE_LABELS[eventType]}
          </button>
        ))}
      </div>

      {/* Timeline Content */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-6 space-y-4">
            <ListSkeleton rows={5} />
          </div>
        ) : error ? (
          <div className="p-6 text-center">
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6">
              <p className="text-red-800 dark:text-red-300 font-medium mb-3">{error}</p>
              <button
                onClick={() => refetch()}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="p-6 text-center">
            <div className="text-gray-600 dark:text-gray-400">
              <p className="text-lg font-medium">No events found</p>
              <p className="text-sm mt-2">
                {events.length === 0
                  ? "No events recorded for this patient"
                  : "No events match the selected filters"}
              </p>
            </div>
          </div>
        ) : (
          <div className="relative p-6">
            {/* Timeline line */}
            <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-gray-300 dark:bg-gray-600" />

            {/* Events */}
            <div className="space-y-6">
              {filteredEvents.map((event) => {
                const colors = EVENT_TYPE_COLORS[event.type];
                return (
                  <div key={`${event.type}-${event.id}`} className="flex gap-4">
                    {/* Date badge on timeline */}
                    <div className="flex flex-col items-center pt-1">
                      <div className={`w-4 h-4 rounded-full ${colors.badge} border-4 border-white dark:border-slate-900 dark:border-slate-100 absolute -ml-11`} />
                      <div className={`text-xs font-semibold text-gray-500 dark:text-gray-400 -mt-3 whitespace-nowrap`}>
                        {new Date(event.date).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })}
                      </div>
                    </div>

                    {/* Event card */}
                    <button
                      onClick={() => handleEventClick(event)}
                      className={`flex-1 rounded-lg border-l-4 p-4 transition-all hover:shadow-lg hover:scale-105 cursor-pointer ${colors.bg} ${colors.border} ${colors.text}`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className={`text-xs font-bold px-3 py-1 rounded-full ${colors.badge}`}>
                          {EVENT_TYPE_LABELS[event.type]}
                        </span>
                        {event.type === "lab_result" && (
                          <span className={`text-xs font-semibold capitalize ${getSeverityColor(event)}`}>
                            {event.severity}
                          </span>
                        )}
                      </div>

                      <p className="text-sm font-medium mb-2">{getEventSummary(event)}</p>

                      <div className="flex items-center justify-between">
                        <span className="text-xs opacity-75">{formatEventDate(event.date)}</span>
                        {event.provider && (
                          <span className="text-xs opacity-75">
                            {event.provider}
                          </span>
                        )}
                      </div>
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* SlideOver for event details */}
      <SlideOver
        open={showDetail}
        onOpenChange={setShowDetail}
        title={selectedEvent ? `${EVENT_TYPE_LABELS[selectedEvent.type]} Details` : undefined}
      >
        {selectedEvent && renderEventDetails(selectedEvent)}
      </SlideOver>
    </div>
  );
}
