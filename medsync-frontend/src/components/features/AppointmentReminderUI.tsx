"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Bell, MessageSquare, Mail, Clock, AlertCircle } from "lucide-react";

interface ReminderConfig {
  id: string;
  reminder_type: "sms" | "email" | "both";
  hours_before: number;
  is_active: boolean;
  template?: string;
  last_sent_at?: string;
}

interface ReminderHistory {
  id: string;
  appointment_id: string;
  patient_name: string;
  reminder_type: string;
  status: "sent" | "failed" | "pending";
  sent_at: string;
  error_message?: string;
}

export default function AppointmentReminderUI() {
  const api = useApi();
  const toast = useToast();

  const [configs, setConfigs] = useState<ReminderConfig[]>([]);
  const [history, setHistory] = useState<ReminderHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const [newConfig, setNewConfig] = useState({
    reminder_type: "sms" as "sms" | "email" | "both",
    hours_before: 24,
    is_active: true,
  });

  const loadConfigs = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.get<{ data: ReminderConfig[] }>(
        "/appointments/reminder-configs"
      );
      setConfigs(data.data || []);
    } catch {
      // Silently fail - feature may not be fully implemented yet
      setConfigs([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  const loadHistory = useCallback(async () => {
    try {
      const data = await api.get<{ data: ReminderHistory[] }>(
        "/appointments/reminder-history?limit=50"
      );
      setHistory(data.data || []);
    } catch {
      setHistory([]);
    }
  }, [api]);

  useEffect(() => {
    loadConfigs();
    loadHistory();
  }, [loadConfigs, loadHistory]);

  const handleSaveConfig = async () => {
    try {
      if (editing) {
        await api.patch(`/appointments/reminder-configs/${editing}`, newConfig);
        toast.success("Reminder config updated");
      } else {
        await api.post("/appointments/reminder-configs", newConfig);
        toast.success("Reminder config created");
      }
      await loadConfigs();
      setShowForm(false);
      setEditing(null);
      setNewConfig({ reminder_type: "sms", hours_before: 24, is_active: true });
    } catch (err) {
      toast.error(`Failed to save: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Delete this reminder config?")) return;
    try {
      await api.delete(`/appointments/reminder-configs/${id}`);
      toast.success("Reminder config deleted");
      await loadConfigs();
    } catch (err) {
      toast.error(`Failed to delete: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
  };

  const handleToggleActive = async (id: string, isActive: boolean) => {
    try {
      await api.patch(`/appointments/reminder-configs/${id}`, {
        is_active: !isActive,
      });
      await loadConfigs();
    } catch {
      toast.error("Failed to toggle reminder");
    }
  };

  const handleEditConfig = (config: ReminderConfig) => {
    setEditing(config.id);
    setNewConfig({
      reminder_type: config.reminder_type,
      hours_before: config.hours_before,
      is_active: config.is_active,
    });
    setShowForm(true);
  };

  const getReminderIcon = (type: string) => {
    if (type === "sms") return <MessageSquare className="h-4 w-4" />;
    if (type === "email") return <Mail className="h-4 w-4" />;
    return <Bell className="h-4 w-4" />;
  };

  const getStatusColor = (status: string) => {
    if (status === "sent") return "bg-green-100 text-green-800";
    if (status === "failed") return "bg-red-100 text-red-800";
    return "bg-yellow-100 text-yellow-800";
  };

  return (
    <div className="space-y-6">
      {/* Reminder Configuration */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-sora text-lg font-bold text-slate-900 dark:text-slate-100">Reminder Configurations</h2>
          {!showForm && (
            <Button onClick={() => setShowForm(true)} className="bg-[#0EAFBE]">
              + Add Reminder
            </Button>
          )}
        </div>

        {/* Form */}
        {showForm && (
          <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Type *</label>
                <select
                  value={newConfig.reminder_type}
                  onChange={(e) =>
                    setNewConfig({ ...newConfig, reminder_type: e.target.value as "sms" | "email" | "both" })
                  }
                  className="w-full mt-1 rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-sm"
                >
                  <option value="sms">SMS</option>
                  <option value="email">Email</option>
                  <option value="both">Both SMS &amp; Email</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Hours Before *</label>
                <Input
                  type="number"
                  min="1"
                  max="72"
                  value={newConfig.hours_before}
                  onChange={(e) =>
                    setNewConfig({ ...newConfig, hours_before: parseInt(e.target.value) || 24 })
                  }
                  className="mt-1"
                />
              </div>
            </div>

            <div>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={newConfig.is_active}
                  onChange={(e) => setNewConfig({ ...newConfig, is_active: e.target.checked })}
                  className="h-4 w-4 rounded border-slate-300 dark:border-slate-700"
                />
                <span className="text-sm text-slate-900 dark:text-slate-100">Active</span>
              </label>
            </div>

            <div className="flex gap-2">
              <Button onClick={handleSaveConfig} className="bg-[#0EAFBE]">
                {editing ? "Update" : "Create"}
              </Button>
              <Button
                onClick={() => {
                  setShowForm(false);
                  setEditing(null);
                  setNewConfig({ reminder_type: "sms", hours_before: 24, is_active: true });
                }}
                variant="outline"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Configs List */}
        {loading ? (
          <p className="text-slate-500 dark:text-slate-500">Loading...</p>
        ) : configs.length === 0 ? (
          <p className="text-slate-500 dark:text-slate-500">No reminder configurations yet.</p>
        ) : (
          <div className="space-y-3">
            {configs.map((config) => (
              <div
                key={config.id}
                className="flex items-center justify-between p-4 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:bg-slate-900"
              >
                <div className="flex items-center gap-3 flex-1">
                  <div className="flex items-center gap-2 text-[#0EAFBE]">
                    {getReminderIcon(config.reminder_type)}
                    <span className="text-sm font-medium capitalize">{config.reminder_type}</span>
                  </div>
                  <span className="text-sm text-slate-500 dark:text-slate-500">{config.hours_before}h before</span>
                  {config.last_sent_at && (
                    <span className="text-xs text-[#94A3B8]">
                      Last sent: {new Date(config.last_sent_at).toLocaleDateString()}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleToggleActive(config.id, config.is_active)}
                    className={`px-3 py-1 rounded text-xs font-medium ${
                      config.is_active
                        ? "bg-green-100 text-green-800"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {config.is_active ? "Active" : "Inactive"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleEditConfig(config)}
                    className="px-3 py-1 rounded border border-slate-200 dark:border-slate-800 text-xs text-slate-900 dark:text-slate-100 hover:bg-slate-100 dark:bg-slate-900"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(config.id)}
                    className="px-3 py-1 rounded border border-red-200 text-xs text-red-600 hover:bg-red-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Reminder History */}
      <Card className="p-6">
        <h2 className="font-sora text-lg font-bold text-slate-900 dark:text-slate-100 mb-4">Recent Reminders</h2>

        {history.length === 0 ? (
          <p className="text-slate-500 dark:text-slate-500">No reminder history yet.</p>
        ) : (
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {history.map((item) => (
              <div
                key={item.id}
                className="flex items-start justify-between p-4 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:bg-slate-900"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-900 dark:text-slate-100">{item.patient_name}</span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusColor(item.status)}`}>
                      {item.status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-500 dark:text-slate-500 mt-1">
                    {getReminderIcon(item.reminder_type)} {item.reminder_type.toUpperCase()}
                  </p>
                  {item.error_message && (
                    <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                      <AlertCircle className="h-3 w-3" />
                      {item.error_message}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 text-right">
                  <Clock className="h-4 w-4 text-slate-500 dark:text-slate-500" />
                  <span className="text-xs text-slate-500 dark:text-slate-500">
                    {new Date(item.sent_at).toLocaleString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Info Banner */}
      <Card className="p-4 bg-blue-50 border-blue-200">
        <div className="flex items-start gap-3">
          <Bell className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-900">
            <p className="font-medium">Appointment Reminders</p>
            <p className="text-xs mt-1">
              Configure automatic SMS and email reminders for patients before their appointments. 
              Reminders are sent based on the configured hours before appointment time.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
