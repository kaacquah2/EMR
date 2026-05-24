import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useAsyncAIAnalysis } from "@/hooks/use-async-ai-analysis";
import type { AIAnalysisJobResponse, AIAnalysis } from "@/lib/types";

// Mock createApiClient
vi.mock("@/lib/api-client", () => ({
  createApiClient: vi.fn(),
}));

// Mock useAuth
vi.mock("@/lib/auth-context", () => ({
  useAuth: vi.fn(() => ({
    user: { id: "user-123", hospital_id: "hospital-123" },
    token: "mock-token",
    getAccessToken: vi.fn(() => "mock-token"),
  })),
}));

import { createApiClient } from "@/lib/api-client";

describe("useAsyncAIAnalysis", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  const mockAnalysis: AIAnalysis = {
    job_id: "job-123",
    patient_id: "patient-1",
    analysis_type: "comprehensive",
    diagnostic_insights: "Test insights",
    recommendations: ["Rec 1"],
    risk_factors: ["Risk 1"],
    created_at: "2024-01-01T12:00:00Z",
  };

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
        data: {
          job_id: "job-123",
          status: "pending",
          progress_percent: 0,
          current_step: "",
        }
      } as { data: AIAnalysisJobResponse }),
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
  });

  it("pollStatus updates progress and currentStep", async () => {
    const mockApi = {
      post: vi.fn().mockResolvedValue({
        data: {
          job_id: "job-123",
          status: "pending",
        }
      } as { data: AIAnalysisJobResponse }),
      get: vi.fn()
        .mockResolvedValueOnce({
          data: {
            job_id: "job-123",
            status: "processing",
            progress_percent: 25,
            current_step: "Step 1",
          }
        } as { data: AIAnalysisJobResponse })
        .mockResolvedValue({
          data: {
            job_id: "job-123",
            status: "processing",
            progress_percent: 50,
            current_step: "Step 2",
          }
        } as { data: AIAnalysisJobResponse }),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    await act(async () => {
      await result.current.startAnalysis();
    });

    // Wait for initial poll (immediate)
    await waitFor(() => {
      expect(result.current.progressPercent).toBe(25);
    }, { timeout: 5000 });

    // Wait for next poll (after 1s)
    await waitFor(() => {
      expect(result.current.progressPercent).toBe(50);
    }, { timeout: 5000 });
  });

  it("completes analysis and populates results", async () => {
    const mockApi = {
      post: vi.fn().mockResolvedValue({
        data: {
          job_id: "job-123",
          status: "pending",
        }
      } as { data: AIAnalysisJobResponse }),
      get: vi.fn()
        .mockResolvedValueOnce({
          data: {
            job_id: "job-123",
            status: "processing",
            progress_percent: 75,
          }
        } as { data: AIAnalysisJobResponse })
        .mockResolvedValue({
          data: {
            job_id: "job-123",
            status: "completed",
            progress_percent: 100,
            analysis: mockAnalysis,
          }
        } as { data: AIAnalysisJobResponse }),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    await act(async () => {
      await result.current.startAnalysis();
    });

    await waitFor(() => {
      expect(result.current.status).toBe("completed");
      expect(result.current.analysis).toEqual(mockAnalysis);
    }, { timeout: 5000 });
  });

  it("handles 404 error and sets cancelled status", async () => {
    const mockApi = {
      post: vi.fn().mockResolvedValue({
        data: {
          job_id: "job-123",
          status: "pending",
        }
      } as { data: AIAnalysisJobResponse }),
      get: vi.fn().mockRejectedValue(new Error("404 Not Found")),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    await act(async () => {
      await result.current.startAnalysis();
    });

    await waitFor(() => {
      expect(result.current.status).toBe("cancelled");
    }, { timeout: 5000 });
  });

  it("cancels job stops polling", async () => {
    const mockApi = {
      post: vi.fn()
        .mockResolvedValueOnce({
          data: {
            job_id: "job-123",
            status: "pending",
          }
        } as { data: AIAnalysisJobResponse })
        .mockResolvedValueOnce({}), // cancel
      get: vi.fn().mockResolvedValue({
        data: {
          job_id: "job-123",
          status: "processing",
        }
      } as { data: AIAnalysisJobResponse }),
    };
    (createApiClient as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useAsyncAIAnalysis("patient-1"));

    await act(async () => {
      await result.current.startAnalysis();
    });

    await act(async () => {
      await result.current.cancelJob();
    });

    expect(result.current.status).toBe("cancelled");
    expect(result.current.jobId).toBeNull();
  });
});
