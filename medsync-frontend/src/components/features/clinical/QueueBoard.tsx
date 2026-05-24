"use client";

import React from "react";
import { 
  Users, 
  Clock, 
  ArrowRight,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface QueueItem {
  id: string;
  patient_id: string;
  patient_name: string;
  ghana_health_id: string;
  triage_color: "red" | "orange" | "yellow" | "green" | "blue";
  waiting_since: string;
  department: string;
  chief_complaint: string;
}

interface QueueBoardProps {
  items: QueueItem[];
  onAction?: (id: string) => void;
}

/**
 * Queue Board Component
 * 
 * Visualizes patient flow with triage color coding and waiting time tracking.
 */
export function QueueBoard({ items, onAction }: QueueBoardProps) {
  const getTriageColor = (color: QueueItem["triage_color"]) => {
    switch (color) {
      case "red": return "bg-red-500";
      case "orange": return "bg-orange-500";
      case "yellow": return "bg-yellow-400";
      case "green": return "bg-emerald-500";
      case "blue": return "bg-blue-500";
      default: return "bg-slate-300";
    }
  };

  const calculateWaitTime = (since: string) => {
    const start = new Date(since).getTime();
    const now = new Date().getTime();
    const diffMins = Math.floor((now - start) / (1000 * 60));
    
    if (diffMins < 60) return `${diffMins}m`;
    const hours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;
    return `${hours}h ${mins}m`;
  };

  const sortedItems = [...items].sort((a, b) => {
    // Sort by priority (red first) then wait time
    const priorityMap = { red: 0, orange: 1, yellow: 2, green: 3, blue: 4 };
    if (priorityMap[a.triage_color] !== priorityMap[b.triage_color]) {
      return priorityMap[a.triage_color] - priorityMap[b.triage_color];
    }
    return new Date(a.waiting_since).getTime() - new Date(b.waiting_since).getTime();
  });

  return (
    <Card className="shadow-lg border-slate-200 dark:border-slate-800 overflow-hidden">
      <CardHeader className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-bold flex items-center gap-2">
            <Users className="h-5 w-5 text-[#0EAFBE]" />
            Active Patient Queue
          </CardTitle>
          <Badge variant="secondary" className="px-3 py-1">
            {items.length} Patients Waiting
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider border-b border-slate-100 dark:border-slate-800">
                <th className="px-6 py-4 text-left">Priority</th>
                <th className="px-6 py-4 text-left">Patient</th>
                <th className="px-6 py-4 text-left">Wait Time</th>
                <th className="px-6 py-4 text-left">Complaint</th>
                <th className="px-6 py-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {sortedItems.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/50 transition-colors">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <div className={`h-3 w-3 rounded-full ${getTriageColor(item.triage_color)} shadow-sm`} />
                      <span className="text-xs font-bold uppercase tracking-tighter">{item.triage_color}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="text-sm font-bold text-slate-900 dark:text-white">{item.patient_name}</span>
                      <span className="text-xs text-slate-500 font-mono">{item.ghana_health_id}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                      <Clock className="h-3.5 w-3.5" />
                      <span className={`text-sm font-medium ${parseInt(calculateWaitTime(item.waiting_since)) > 60 ? 'text-rose-600 font-bold' : ''}`}>
                        {calculateWaitTime(item.waiting_since)}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-sm text-slate-600 dark:text-slate-400 line-clamp-1 max-w-[200px]">
                      {item.chief_complaint || "—"}
                    </p>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Button 
                      size="sm" 
                      variant="ghost" 
                      className="hover:bg-[#0EAFBE]/10 hover:text-[#0EAFBE]"
                      onClick={() => onAction?.(item.id)}
                    >
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              ))}
              {sortedItems.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-12 text-center text-slate-500 dark:text-slate-400">
                    <Users className="h-12 w-12 mx-auto opacity-10 mb-4" />
                    <p>The queue is currently empty.</p>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
