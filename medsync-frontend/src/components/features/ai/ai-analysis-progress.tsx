"use client";

import React from "react";
import type { AIAnalysis } from "@/lib/types";

interface AIAnalysisProgressProps {
  jobId: string | null;
  status: "idle" | "pending" | "processing" | "completed" | "failed" | "cancelled";
  progressPercent: number;
  currentStep: string;
  analysis: AIAnalysis | null;
  error: Error | null;
  onCancel: () => Promise<void>;
  onStart: () => Promise<void>;
  onRetry?: () => Promise<void>;
  onClose?: () => void;
  onStartNew?: () => void;
}

export function AIAnalysisProgress({
  jobId,
  status,
  progressPercent,
  currentStep,
  analysis,
  error,
  onCancel,
  onStart,
  onRetry,
  onClose,
  onStartNew,
}: AIAnalysisProgressProps) {
  const [isCancelling, setIsCancelling] = React.useState(false);
  const [isStarting, setIsStarting] = React.useState(false);

  const handleCancel = async () => {
    setIsCancelling(true);
    try {
      await onCancel();
    } finally {
      setIsCancelling(false);
    }
  };

  const handleStart = async () => {
    setIsStarting(true);
    try {
      await onStart();
    } finally {
      setIsStarting(false);
    }
  };

  const handleRetry = async () => {
    setIsStarting(true);
    try {
      if (onRetry) {
        await onRetry();
      }
    } finally {
      setIsStarting(false);
    }
  };

  const handleClose = () => {
    if (onClose) {
      onClose();
    }
  };

  const handleStartNew = async () => {
    if (onStartNew) {
      onStartNew();
    }
  };

  // Idle state
  if (status === "idle" && !jobId) {
    return (
      <div className="rounded-xl border border-slate-200 dark:border-slate-800/80 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.06),0_2px_8px_rgba(11,138,150,0.04)]">
        <div className="mb-4">
          <h3 className="font-sora text-xl font-bold text-slate-900 dark:text-slate-100">
            AI-Powered Analysis
          </h3>
        </div>
        <p className="mb-6 text-sm text-[#475569]">
          Advanced AI analysis will provide diagnostic recommendations and
          insights based on the patient&apos;s medical records.
        </p>
        <button
          onClick={handleStart}
          disabled={isStarting}
          className="rounded-lg bg-[#3B82F6] px-4 py-2 text-white font-medium hover:bg-[#2563EB] disabled:bg-[#9CA3AF] transition-colors"
        >
          {isStarting ? "Starting..." : "Analyze with AI"}
        </button>
      </div>
    );
  }

  // Pending/Processing state
  if ((status === "pending" || status === "processing") && jobId) {
    const displayPercent = Math.min(progressPercent, 99);

    return (
      <div className="rounded-xl border border-slate-200 dark:border-slate-800/80 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.06),0_2px_8px_rgba(11,138,150,0.04)]">
        <div className="mb-6 flex items-center justify-between">
          <h3 className="font-sora text-xl font-bold text-slate-900 dark:text-slate-100">
            AI Analysis in Progress
          </h3>
          <button
            onClick={handleCancel}
            disabled={isCancelling}
            className="rounded-full bg-red-50 p-2 hover:bg-red-100 disabled:bg-gray-100 transition-colors"
            title="Cancel analysis"
          >
            <svg
              className="h-5 w-5 text-[#DC2626]"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>

        <div className="mb-4">
          <p className="mb-2 text-sm font-medium text-[#475569]">
            {currentStep || "Processing..."}
          </p>
          <div className="relative h-3 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            <div
              className="h-full bg-[#3B82F6] transition-all duration-300 ease-out"
              style={{ width: `${displayPercent}%` }}
            />
          </div>
        </div>

        <p className="text-right text-xs text-slate-500 dark:text-slate-500">
          Progress: {displayPercent}%
        </p>
      </div>
    );
  }

  // Completed state
  if (status === "completed" && analysis) {
    return (
      <div className="rounded-xl border border-slate-200 dark:border-slate-800/80 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.06),0_2px_8px_rgba(11,138,150,0.04)]">
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-4">
            <svg
              className="h-6 w-6 text-[#059669]"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            <h3 className="font-sora text-xl font-bold text-slate-900 dark:text-slate-100">
              Analysis Complete
            </h3>
          </div>
        </div>

        {/* Diagnostic Insights */}
        <div className="mb-6 rounded-lg bg-[#F0F9FF] p-4 border border-[#BAE6FD]">
          <h4 className="mb-3 font-sora font-bold text-[#0369A1]">
            Diagnostic Insights
          </h4>
          <p className="text-sm text-[#0C2340]">{analysis.diagnostic_insights}</p>
        </div>

        {/* Recommendations */}
        {analysis.recommendations && analysis.recommendations.length > 0 && (
          <div className="mb-6">
            <h4 className="mb-3 font-sora font-bold text-slate-900 dark:text-slate-100">
              Recommendations
            </h4>
            <ul className="space-y-2">
              {analysis.recommendations.map((rec, idx) => (
                <li key={idx} className="flex gap-3 text-sm text-[#475569]">
                  <svg
                    className="h-5 w-5 flex-shrink-0 text-[#3B82F6]"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 10 10.293 5.707a1 1 0 010-1.414z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Risk Factors */}
        {analysis.risk_factors && analysis.risk_factors.length > 0 && (
          <div className="mb-6">
            <h4 className="mb-3 font-sora font-bold text-slate-900 dark:text-slate-100">
              Risk Factors
            </h4>
            <div className="flex flex-wrap gap-2">
              {analysis.risk_factors.map((risk, idx) => (
                <span
                  key={idx}
                  className="rounded-full bg-[#FEF3C7] px-3 py-1 text-xs font-medium text-[#92400E]"
                >
                  {risk}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-3 pt-4">
          <button
            onClick={handleStartNew}
            className="flex-1 rounded-lg bg-[#3B82F6] px-4 py-2 text-white font-medium hover:bg-[#2563EB] transition-colors"
          >
            Start New Analysis
          </button>
          {onClose && (
            <button
              onClick={handleClose}
              className="rounded-lg border border-[#D1D5DB] px-4 py-2 text-[#475569] font-medium hover:bg-[#F9FAFB] transition-colors"
            >
              Close
            </button>
          )}
        </div>
      </div>
    );
  }

  // Failed state
  if (status === "failed" && error) {
    return (
      <div className="rounded-xl border border-[#FEE2E2] bg-[#FEF2F2] p-6 shadow-[0_1px_3px_rgba(0,0,0,0.06),0_2px_8px_rgba(11,138,150,0.04)]">
        <div className="flex gap-3">
          <svg
            className="h-6 w-6 flex-shrink-0 text-[#DC2626]"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
              clipRule="evenodd"
            />
          </svg>
          <div className="flex-1">
            <h3 className="mb-2 font-sora font-bold text-[#991B1B]">
              Analysis Failed
            </h3>
            <p className="mb-4 text-sm text-[#7F1D1D]">{error.message}</p>
            <button
              onClick={handleRetry || handleStart}
              disabled={isStarting}
              className="rounded-lg bg-[#DC2626] px-4 py-2 text-white font-medium hover:bg-[#B91C1C] disabled:bg-[#9CA3AF] transition-colors"
            >
              {isStarting ? "Retrying..." : "Retry Analysis"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Cancelled state
  if (status === "cancelled") {
    return (
      <div className="rounded-xl border border-slate-200 dark:border-slate-800/80 bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.06),0_2px_8px_rgba(11,138,150,0.04)]">
        <div className="flex gap-3 items-start">
          <svg
            className="h-6 w-6 flex-shrink-0 text-slate-500 dark:text-slate-500 mt-0.5"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
          <div className="flex-1">
            <h3 className="mb-2 font-sora font-bold text-[#475569]">
              Analysis Cancelled
            </h3>
            <p className="mb-4 text-sm text-slate-500 dark:text-slate-500">
              The analysis has been cancelled. You can start a new analysis at any time.
            </p>
            <button
              onClick={handleStartNew}
              className="rounded-lg bg-[#3B82F6] px-4 py-2 text-white font-medium hover:bg-[#2563EB] transition-colors"
            >
              Start New Analysis
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
