import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useAsyncAIAnalysis } from "@/hooks/use-async-ai-analysis";
import type { AIAnalysisJobResponse } from "@/lib/types";

// Mock createApiClient
vi.mock("@/lib/api-client", () => ({
  createApiClient: vi.fn(),
}));

// Mock useAuth
vi.mock("@/lib/auth-context", () => ({
  useAuth: vi.fn(() => ({
    user: { id: "user-123", hospital_id: "hospital-123" },
    token: "mock-token",
  })),
}));

import { createApiClient } from "@/lib/api-client";

describe("useAsyncAIAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("initializes with correct state", () => {
    const mockApi = {
      post: vi.fn(),
      get: vi.fn(),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    expect(result.current.jobId).toBeNull();
    expect(result.current.status).toBe("idle");
    expect(result.current.progressPercent).toBe(0);
    expect(result.current.currentStep).toBe("");
    expect(result.current.analysis).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("startAnalysis returns jobId and sets pending status", async () => {
    const mockApi = {
      post: vi.fn().mockResolvedValue({
        job_id: "job-123",
        status: "pending",
        progress_percent: 0,
        current_step: "",
      } as AIAnalysisJobResponse),
      get: vi.fn(),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    let jobId: string | undefined;
    await act(async () => {
      jobId = await result.current.startAnalysis();
    });

    expect(jobId).toBe("job-123");
    expect(result.current.jobId).toBe("job-123");
    expect(result.current.status).toBe("pending");
    expect(mockApi.post).toHaveBeenCalledWith(
      "/ai/async-analysis/patient-1",
      { analysis_type: "comprehensive" }
    );
  });

  it("startAnalysis with custom options", async () => {
    const mockApi = {
      post: vi.fn().mockResolvedValue({
        job_id: "job-456",
        status: "pending",
        progress_percent: 0,
        current_step: "",
      } as AIAnalysisJobResponse),
      get: vi.fn(),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-2"));

    await act(async () => {
      await result.current.startAnalysis({ analysisType: "quick" });
    });

    expect(mockApi.post).toHaveBeenCalledWith(
      "/ai/async-analysis/patient-2",
      { analysis_type: "quick" }
    );
  });

  it("pollStatus updates progress and currentStep", { timeout: 15000 }, async () => {
    const mockApi = {
      post: vi.fn().mockResolvedValue({
        job_id: "job-123",
        status: "pending",
      } as AIAnalysisJobResponse),
      get: vi.fn()
        .mockResolvedValueOnce({
          job_id: "job-123",
          status: "processing",
          progress_percent: 25,
          current_step: "Analyzing patient vitals...",
        } as AIAnalysisJobResponse)
        .mockResolvedValueOnce({
          job_id: "job-123",
          status: "processing",
          progress_percent: 50,
          current_step: "Generating recommendations...",
        } as AIAnalysisJobResponse),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    // Start analysis
    await act(async () => {
      await result.current.startAnalysis();
    });

    expect(result.current.jobId).toBe("job-123");

    // Advance to first poll
    await act(async () => {
      vi.advanceTimersByTime(1100);
    });

    await waitFor(() => {
      expect(result.current.progressPercent).toBe(25);
    });

    // Advance to second poll
    await act(async () => {
      vi.advanceTimersByTime(1100);
    });

    await waitFor(() => {
      expect(result.current.progressPercent).toBe(50);
    });
  });

  it("completes analysis and populates results", { timeout: 15000 }, async () => {
    const mockAnalysis = {
      job_id: "job-123",
      patient_id: "patient-1",
      analysis_type: "comprehensive",
      diagnostic_insights: "Potential hypertension detected",
      recommendations: ["Monitor blood pressure"],
      risk_factors: ["High BP"],
      created_at: "2024-01-01T12:00:00Z",
    };

    const mockApi = {
      post: vi.fn().mockResolvedValue({
        job_id: "job-123",
        status: "pending",
      } as AIAnalysisJobResponse),
      get: vi.fn()
        .mockResolvedValueOnce({
          job_id: "job-123",
          status: "processing",
          progress_percent: 75,
          current_step: "Almost done...",
        } as AIAnalysisJobResponse)
        .mockResolvedValueOnce({
          job_id: "job-123",
          status: "completed",
          progress_percent: 100,
          current_step: "Complete",
          analysis: mockAnalysis,
        } as AIAnalysisJobResponse),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    await act(async () => {
      await result.current.startAnalysis();
    });

    // First poll
    await act(async () => {
      vi.advanceTimersByTime(1100);
    });

    await waitFor(() => {
      expect(result.current.status).toBe("processing");
    });

    // Second poll - completes
    await act(async () => {
      vi.advanceTimersByTime(1100);
    });

    await waitFor(() => {
      expect(result.current.status).toBe("completed");
      expect(result.current.analysis).toEqual(mockAnalysis);
    });
  });

  it("handles 404 error and sets cancelled status", async () => {
    const mockApi = {
      post: vi.fn().mockResolvedValue({
        job_id: "job-123",
        status: "pending",
      } as AIAnalysisJobResponse),
      get: vi.fn().mockRejectedValue(new Error("404 Not Found")),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    await act(async () => {
      await result.current.startAnalysis();
    });

    await waitFor(() => {
      expect(result.current.jobId).toBe("job-123");
    });

    await act(async () => {
      vi.advanceTimersByTime(1100);
    });

    await waitFor(() => {
      expect(result.current.status).toBe("cancelled");
    });
  });

  it("cancels job stops polling", async () => {
    const mockApi = {
      post: vi.fn()
        .mockResolvedValueOnce({
          job_id: "job-123",
          status: "pending",
        } as AIAnalysisJobResponse)
        .mockResolvedValueOnce({}), // cancel endpoint
      get: vi.fn().mockResolvedValue({
        job_id: "job-123",
        status: "processing",
        progress_percent: 50,
      } as AIAnalysisJobResponse),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    await act(async () => {
      await result.current.startAnalysis();
    });

    expect(result.current.jobId).toBe("job-123");

    await act(async () => {
      await result.current.cancelJob();
    });

    expect(result.current.status).toBe("cancelled");
    expect(result.current.jobId).toBeNull();
  });

  it("stops polling when status is completed", { timeout: 15000 }, async () => {
    const mockAnalysis = {
      job_id: "job-123",
      patient_id: "patient-1",
      analysis_type: "comprehensive",
      diagnostic_insights: "Test insights",
      recommendations: [],
      risk_factors: [],
      created_at: "2024-01-01T12:00:00Z",
    };

    const mockApi = {
      post: vi.fn().mockResolvedValue({
        job_id: "job-123",
        patient_id: "patient-1",
        status: "pending",
        progress_percent: 0,
        current_step: "Starting",
        celery_task_id: "celery-task-123",
        created_at: "2024-01-01T12:00:00Z",
        updated_at: "2024-01-01T12:00:00Z",
      } as AIAnalysisJobResponse),
      get: vi.fn().mockResolvedValue({
        job_id: "job-123",
        patient_id: "patient-1",
        status: "completed",
        progress_percent: 100,
        current_step: "Complete",
        celery_task_id: "celery-task-123",
        created_at: "2024-01-01T12:00:00Z",
        updated_at: "2024-01-01T12:00:00Z",
        analysis: mockAnalysis,
      } as AIAnalysisJobResponse),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    await act(async () => {
      await result.current.startAnalysis();
    });

    // Poll once to completion
    await act(async () => {
      vi.advanceTimersByTime(1100);
    });

    await waitFor(() => {
      expect(result.current.status).toBe("completed");
    });

    const getCallCount = mockApi.get.mock.calls.length;

    // Advance time more - should not trigger additional polls
    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    // Verify no additional API calls were made
    expect(mockApi.get.mock.calls.length).toBe(getCallCount);
  });

  it("throws error when null patientId passed to startAnalysis", async () => {
    const mockApi = {
      post: vi.fn(),
      get: vi.fn(),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis(null));

    let caughtError: Error | null = null;
    await act(async () => {
      try {
        await result.current.startAnalysis();
      } catch (err) {
        caughtError = err as Error;
      }
    });

    expect(caughtError).toBeTruthy();
    expect(result.current.error).toBeTruthy();
    expect(result.current.status).toBe("failed");
  });

  it("getResults returns analysis when completed", { timeout: 15000 }, async () => {
    const mockAnalysis = {
      job_id: "job-123",
      patient_id: "patient-1",
      analysis_type: "comprehensive",
      diagnostic_insights: "Test insights",
      recommendations: ["Rec 1"],
      risk_factors: ["Risk 1"],
      created_at: "2024-01-01T12:00:00Z",
    };

    const mockApi = {
      post: vi.fn().mockResolvedValue({
        job_id: "job-123",
        status: "pending",
      } as AIAnalysisJobResponse),
      get: vi.fn().mockResolvedValue({
        job_id: "job-123",
        status: "completed",
        progress_percent: 100,
        analysis: mockAnalysis,
      } as AIAnalysisJobResponse),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    expect(result.current.getResults()).toBeNull();

    await act(async () => {
      await result.current.startAnalysis();
      vi.advanceTimersByTime(1100);
    });

    await waitFor(() => {
      expect(result.current.getResults()).toEqual(mockAnalysis);
    });
  });
});

