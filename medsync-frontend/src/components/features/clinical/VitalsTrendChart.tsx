"use client";

import React, { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceArea,
  ReferenceLine,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface VitalData {
  created_at: string;
  temperature_c?: number;
  pulse_bpm?: number;
  resp_rate?: number;
  bp_systolic?: number;
  bp_diastolic?: number;
  spo2_percent?: number;
}

interface VitalsTrendChartProps {
  data: VitalData[];
}

/**
 * Vitals Trend Chart Component
 * 
 * Displays multiple vitals on a timeline with normal ranges and thresholds.
 */
export function VitalsTrendChart({ data }: VitalsTrendChartProps) {
  const [timeRange, setTimeRange] = useState<"24h" | "48h" | "7d">("24h");

  // Filter and format data based on selected time range
  const chartData = useMemo(() => {
    if (!data) return [];
    
    const now = new Date();
    const rangeMs = {
      "24h": 24 * 60 * 60 * 1000,
      "48h": 48 * 60 * 60 * 1000,
      "7d": 7 * 24 * 60 * 60 * 1000,
    }[timeRange];

    return data
      .filter((v) => {
        const date = new Date(v.created_at);
        return now.getTime() - date.getTime() <= rangeMs;
      })
      .map((v) => ({
        ...v,
        timestamp: new Date(v.created_at).getTime(),
        displayTime: new Date(v.created_at).toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        }),
      }))
      .sort((a, b) => a.timestamp - b.timestamp);
  }, [data, timeRange]);

  // Thresholds for alerts (simplified)
  const THRESHOLDS = {
    temp: { min: 36.5, max: 37.5 },
    hr: { min: 60, max: 100 },
    bp_sys: { min: 90, max: 140 },
    spo2: { min: 95, max: 100 },
  };

  return (
    <Card className="w-full shadow-lg border-slate-200 dark:border-slate-800">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-lg font-bold text-slate-800 dark:text-slate-100">
          Vitals Trend Analysis
        </CardTitle>
        <div className="flex gap-2 bg-slate-100 dark:bg-slate-950 p-1 rounded-lg">
          {(["24h", "48h", "7d"] as const).map((r) => (
            <Button
              key={r}
              variant={timeRange === r ? "primary" : "ghost"}
              size="sm"
              className="h-7 px-3 text-xs"
              onClick={() => setTimeRange(r)}
            >
              {r.toUpperCase()}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[400px] w-full mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis 
                dataKey="displayTime" 
                tick={{ fontSize: 10 }}
                tickMargin={10}
                stroke="#94a3b8"
              />
              <YAxis 
                tick={{ fontSize: 10 }} 
                stroke="#94a3b8"
              />
              <Tooltip 
                contentStyle={{ 
                  borderRadius: "8px", 
                  border: "none", 
                  boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1)",
                  fontSize: "12px"
                }} 
              />
              <Legend verticalAlign="top" height={36}/>
              
              {/* Normal Range Shading for Temperature (Example) */}
              <ReferenceArea 
                y1={THRESHOLDS.temp.min} 
                y2={THRESHOLDS.temp.max} 
                fill="#ecfdf5" 
                fillOpacity={0.5} 
                stroke="none"
              />

              {/* Alert threshold for SpO2 */}
              <ReferenceLine y={94} stroke="#ef4444" strokeDasharray="3 3" label={{ position: 'right', value: 'SpO2 Low', fill: '#ef4444', fontSize: 10 }} />

              <Line
                type="monotone"
                dataKey="temperature_c"
                name="Temp (°C)"
                stroke="#10b981"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="pulse_bpm"
                name="HR (bpm)"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="bp_systolic"
                name="BP Sys"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={{ r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="bp_diastolic"
                name="BP Dia"
                stroke="#d97706"
                strokeWidth={2}
                dot={{ r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="spo2_percent"
                name="SpO2 (%)"
                stroke="#ef4444"
                strokeWidth={2}
                dot={{ r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="resp_rate"
                name="RR"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
