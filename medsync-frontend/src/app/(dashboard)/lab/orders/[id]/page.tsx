"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useApi } from "@/hooks/use-api";

type LabOrderDetail = {
  id: string;
  patient_name: string;
  patient_age: number | null;
  patient_gender: string | null;
  gha_id: string;
  test_name: string;
  urgency: "stat" | "urgent" | "routine";
  status: string;
  ordering_doctor_name: string;
  ordered_at: string;
  result?: {
    result_value?: string | null;
    reference_range?: string | null;
    attachment_url?: string | null;
  } | null;
};

const stepLabel = ["Collected", "In Progress", "Result", "Critical check", "Upload", "Submit"];

function parseRange(range: string): { low: number; high: number } | null {
  const parts = range.split("-");
  if (parts.length !== 2) return null;
  const low = Number(parts[0].trim());
  const high = Number(parts[1].trim());
  if (!Number.isFinite(low) || !Number.isFinite(high)) return null;
  return { low, high };
}

export default function LabOrderResultEntryPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const api = useApi();

  const [order, setOrder] = useState<LabOrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [resultValue, setResultValue] = useState("");
  const [referenceRange, setReferenceRange] = useState("");
  const [criticalNotified, setCriticalNotified] = useState(false);
  const [attachmentUrl, setAttachmentUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const orderId = params?.id;

  useEffect(() => {
    if (!orderId) return;
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const res = await api.get<LabOrderDetail>(`/lab/orders/${orderId}`);
        if (cancelled) return;
        setOrder(res);
        setResultValue(res.result?.result_value || "");
        setReferenceRange(res.result?.reference_range || "");
        setAttachmentUrl(res.result?.attachment_url || "");
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load order");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, orderId]);

  const canCollect = order?.status === "ordered";
  const canStart = order?.status === "collected";
  const canResult = order?.status === "in_progress";
  const numericResult = Number(String(resultValue).trim().split(" ")[0]);
  const parsedRange = useMemo(() => parseRange(referenceRange), [referenceRange]);
  const comparison = useMemo(() => {
    if (!Number.isFinite(numericResult) || !parsedRange) return null;
    if (numericResult < parsedRange.low) return "below";
    if (numericResult > parsedRange.high) return "above";
    return "normal";
  }, [numericResult, parsedRange]);
  const critical = comparison === "above" || comparison === "below";

  const stepIndex = useMemo(() => {
    if (!order) return 0;
    if (order.status === "ordered") return 0;
    if (order.status === "collected") return 1;
    if (order.status === "in_progress") return 2;
    if (order.status === "resulted") return 5;
    return 5;
  }, [order]);

  async function transition(status: "collected" | "in_progress") {
    if (!orderId) return;
    setSubmitting(true);
    setError("");
    try {
      const updated = await api.patch<LabOrderDetail>(`/lab/orders/${orderId}`, { status });
      setOrder(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Status update failed");
    } finally {
      setSubmitting(false);
    }
  }

  async function uploadFile(file: File) {
    if (!file) return;
    if (file.type !== "application/pdf") {
      setError("Only PDF files are allowed");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("File must be 10MB or less");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await api.postForm<{ url: string }>("/lab/attachments/upload", form);
      setAttachmentUrl(res.url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function submitResult() {
    if (!orderId) return;
    setSubmitting(true);
    setError("");
    try {
      await api.post(`/lab/orders/${orderId}/result`, {
        result_value: resultValue,
        reference_range: referenceRange,
        attachment_url: attachmentUrl || undefined,
        critical_value_notified: critical ? criticalNotified : false,
      });
      router.push("/lab/orders");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Result submit failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="text-[#64748B]">Loading order...</div>;
  if (!order) return <div className="text-[#DC2626]">Order not found.</div>;

  return (
    <div className="space-y-6">
      <h1 className="font-sora text-2xl font-bold text-[#0F172A]">Result Entry</h1>
      <Card className="p-4">
        <p className="font-medium">{order.patient_name} ({order.gha_id})</p>
        <p className="text-sm text-[#64748B]">{order.test_name} - {order.ordering_doctor_name}</p>
      </Card>

      <Card className="p-4">
        <div className="flex flex-wrap gap-2 text-xs">
          {stepLabel.map((label, idx) => (
            <span
              key={label}
              className={`rounded-full px-2 py-1 ${idx < stepIndex ? "bg-blue-600 text-white" : idx === stepIndex ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-500"}`}
            >
              {idx < stepIndex ? "●" : idx === stepIndex ? "◉" : "○"} {label}
            </span>
          ))}
        </div>
      </Card>

      <Card className="p-4 space-y-3">
        <div className="flex flex-wrap gap-2">
          <Button disabled={!canCollect || submitting} onClick={() => transition("collected")}>Mark Collected</Button>
          <Button disabled={!canStart || submitting} onClick={() => transition("in_progress")}>Start Analysis</Button>
        </div>

        <Input
          label="Result value"
          value={resultValue}
          onChange={(e) => setResultValue(e.target.value)}
          placeholder="11.5 g/dL"
          disabled={!canResult}
        />
        <Input
          label="Reference range"
          value={referenceRange}
          onChange={(e) => setReferenceRange(e.target.value)}
          placeholder="13.5-17.5"
          disabled={!canResult}
        />

        {comparison && (
          <p className={`text-sm ${comparison === "normal" ? "text-green-700" : "text-amber-700"}`}>
            {comparison === "normal" ? "● Normal" : comparison === "above" ? "▲ Above range" : "▼ Below range"}
          </p>
        )}

        {critical && (
          <div className="rounded border border-red-300 bg-red-50 p-3">
            <p className="text-sm font-semibold text-red-700">CRITICAL VALUE - notify ordering physician immediately.</p>
            <label className="mt-2 flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={criticalNotified}
                onChange={(e) => setCriticalNotified(e.target.checked)}
                disabled={!canResult}
              />
              I have notified the ordering physician
            </label>
          </div>
        )}

        <div className="space-y-2">
          <label className="block text-sm font-medium text-[#0F172A]">Upload lab report PDF (optional)</label>
          <input
            type="file"
            accept=".pdf,application/pdf"
            disabled={!canResult || uploading}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void uploadFile(file);
            }}
          />
          {attachmentUrl ? <p className="text-xs text-[#64748B] break-all">{attachmentUrl}</p> : null}
        </div>

        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => router.push("/lab/orders")}>Back</Button>
          <Button
            disabled={!canResult || submitting || !resultValue || (critical && !criticalNotified)}
            onClick={() => void submitResult()}
          >
            Post Result
          </Button>
        </div>
      </Card>

      {error ? <p className="text-sm text-[#DC2626]">{error}</p> : null}
    </div>
  );
}
