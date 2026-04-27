"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { createApiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import type { AIAnalysisJobResponse, AIAnalysis } from "@/lib/types";

const MAX_POLLING_DURATION = 30 * 60 * 1000; // 30 minutes
const INITIAL_POLL_INTERVAL = 1000; // 1 second

interface ExponentialBackoffState {
  pollCount: number;
  currentInterval: number;
  startTime: number;
}

export function useAsyncAIAnalysis(patientId: string | null) {
  const auth = useAuth();
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<
    "idle" | "pending" | "processing" | "completed" | "failed" | "cancelled"
  >("idle");
  const [progressPercent, setProgressPercent] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const backoffStateRef = useRef<ExponentialBackoffState>({
    pollCount: 0,
    currentInterval: INITIAL_POLL_INTERVAL,
    startTime: 0,
  });

  const intervalIdRef = useRef<NodeJS.Timeout | null>(null);
  const apiRef = useRef(createApiClient(() => auth.getAccessToken()));

  // Calculate exponential backoff interval
  const getNextInterval = (): number => {
    const state = backoffStateRef.current;
    const elapsedTime = Date.now() - state.startTime;

    if (elapsedTime > MAX_POLLING_DURATION) {
      return -1; // Signal timeout
    }

    // Exponential backoff: 1s → 2s → 5s → 10s
    if (state.pollCount < 10) {
      return 1000;
    } else if (state.pollCount < 30) {
      return 2000;
    } else if (state.pollCount < 60) {
      return 5000;
    }
    return 10000;
  };

  const startAnalysis = useCallback(
    async (options?: {
      analysisType?: "comprehensive" | "quick";
    }): Promise<string> => {
      if (!patientId) {
        const err = new Error("Patient ID is required");
        setError(err);
        setStatus("failed");
        throw err;
      }

      try {
        setIsLoading(true);
        setError(null);
        setStatus("pending");
        setProgressPercent(0);
        setCurrentStep("");

        const api = apiRef.current;
        const response = await api.post<AIAnalysisJobResponse>(
          `/ai/async-analysis/${patientId}`,
          {
            analysis_type: options?.analysisType || "comprehensive",
          }
        );

        if (response && response.job_id) {
          setJobId(response.job_id);
          backoffStateRef.current = {
            pollCount: 0,
            currentInterval: INITIAL_POLL_INTERVAL,
            startTime: Date.now(),
          };
          setIsLoading(false);
          return response.job_id;
        } else {
          throw new Error("Invalid response: missing job_id");
        }
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to start analysis";
        const newError = new Error(errorMessage);
        setError(newError);
        setStatus("failed");
        setIsLoading(false);
        throw newError;
      }
    },
    [patientId]
  );

  const pollStatus = useCallback(async (): Promise<AIAnalysisJobResponse | null> => {
    if (!jobId) {
      throw new Error("No job ID available");
    }

    try {
      const api = apiRef.current;
      const response = await api.get<AIAnalysisJobResponse>(
        `/ai/async-analysis/status/${jobId}`
      );

      if (!response) {
        throw new Error("Empty response from API");
      }

      // Update state based on response
      setStatus((response.status || "processing") as typeof status);
      setProgressPercent(response.progress_percent ?? 0);
      setCurrentStep(response.current_step || "");

      if (response.status === "completed" && response.analysis) {
        setAnalysis(response.analysis);
      }

      backoffStateRef.current.pollCount += 1;
      return response;
    } catch (err) {
      // Handle 404: Job not found
      if (err instanceof Error && err.message.includes("404")) {
        setStatus("cancelled");
        setJobId(null);
        return null;
      }

      // Handle other errors with retry
      const errorMessage =
        err instanceof Error ? err.message : "Failed to poll status";
      const newError = new Error(errorMessage);
      setError(newError);

      // Re-throw for caller to handle
      throw newError;
    }
  }, [jobId]);

  const cancelJob = useCallback(async (): Promise<void> => {
    if (!jobId) {
      return;
    }

    try {
      const api = apiRef.current;
      await api.post(`/ai/async-analysis/${jobId}/cancel`, {});
      setStatus("cancelled");
      setJobId(null);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to cancel job";
      setError(new Error(errorMessage));
    }
  }, [jobId]);

  // Polling effect
  useEffect(() => {
    // Skip polling if status is terminal or no jobId
    if (
      !jobId ||
      status === "completed" ||
      status === "failed" ||
      status === "cancelled"
    ) {
      if (intervalIdRef.current) {
        clearInterval(intervalIdRef.current);
        intervalIdRef.current = null;
      }
      return;
    }

    // Start polling
    const poll = async () => {
      try {
        const nextInterval = getNextInterval();
        if (nextInterval === -1) {
          // Timeout reached
          setStatus("failed");
          setError(new Error("Analysis polling timed out after 30 minutes"));
          if (intervalIdRef.current) {
            clearInterval(intervalIdRef.current);
            intervalIdRef.current = null;
          }
          return;
        }

        await pollStatus();

        // Update interval for next poll
        backoffStateRef.current.currentInterval = nextInterval;
      } catch (err) {
        // Log error but don't stop polling (will retry)
        if (process.env.NODE_ENV === "development") {
          console.error("Polling error:", err);
        }
      }
    };

    // Initial poll immediately
    poll();

    // Set up interval for subsequent polls
    intervalIdRef.current = setInterval(() => {
      poll();
    }, backoffStateRef.current.currentInterval);

    return () => {
      if (intervalIdRef.current) {
        clearInterval(intervalIdRef.current);
        intervalIdRef.current = null;
      }
    };
  }, [jobId, status, pollStatus]);

  return {
    startAnalysis,
    pollStatus,
    getResults: () => analysis,
    cancelJob,
    jobId,
    status,
    progressPercent,
    currentStep,
    analysis,
    isLoading,
    error,
  };
}
