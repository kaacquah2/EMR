import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useShiftHandover, ShiftHandover } from "@/hooks/use-shift-handover";

// Mock useApi
vi.mock("@/hooks/use-api", () => ({
  useApi: vi.fn(),
}));

import { useApi } from "@/hooks/use-api";

describe("useShiftHandover", () => {
  const mockHandover: ShiftHandover = {
    id: "h1",
    shift_id: "s1",
    outgoing_nurse_id: "n1",
    incoming_nurse_id: "n2",
    situation: "Patient stable",
    background: "History of HTN",
    assessment: "BP controlled",
    recommendation: "Continue current therapy",
    outgoing_signed_at: "2025-01-01T10:00:00Z",
    incoming_acknowledged_at: null,
    status: "pending",
    created_at: "2025-01-01T10:00:00Z",
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should initialize with correct default state", () => {
    const mockApi = {
      get: vi.fn(),
      post: vi.fn(),
    };
    (useApi as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useShiftHandover());

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(null);
    expect(result.current.handover).toBe(null);
  });

  it("should submit handover successfully and return data", async () => {
    const mockApi = {
      get: vi.fn(),
      post: vi.fn().mockResolvedValueOnce(mockHandover),
    };
    (useApi as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useShiftHandover());

    const payload = {
      shift_id: "s1",
      situation: "Patient stable",
      background: "History of HTN",
      assessment: "BP controlled",
      recommendation: "Continue current therapy",
      incoming_nurse_id: "n2",
    };

    let submitResult: ShiftHandover | undefined;
    await act(async () => {
      submitResult = await result.current.submitHandover(payload);
    });

    expect(mockApi.post).toHaveBeenCalledWith("/nurse/shift/s1/handover", {
      situation: "Patient stable",
      background: "History of HTN",
      assessment: "BP controlled",
      recommendation: "Continue current therapy",
      incoming_nurse_id: "n2",
    });

    expect(submitResult).toEqual(mockHandover);
    expect(result.current.handover).toEqual(mockHandover);
    expect(result.current.error).toBe(null);
    expect(result.current.loading).toBe(false);
  });

  it("should acknowledge handover and update status", async () => {
    const acknowledgedHandover: ShiftHandover = {
      ...mockHandover,
      incoming_acknowledged_at: "2025-01-01T11:00:00Z",
      status: "acknowledged",
    };

    const mockApi = {
      get: vi.fn(),
      post: vi.fn().mockResolvedValueOnce(acknowledgedHandover),
    };
    (useApi as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useShiftHandover());

    let ackResult: ShiftHandover | undefined;
    await act(async () => {
      ackResult = await result.current.acknowledgeHandover("h1", {
        acknowledgement: "I acknowledge receipt of this handover",
      });
    });

    expect(mockApi.post).toHaveBeenCalledWith("/nurse/shift-handover/h1/acknowledge", {
      acknowledgement: "I acknowledge receipt of this handover",
    });

    expect(ackResult?.status).toBe("acknowledged");
    expect(result.current.handover?.status).toBe("acknowledged");
  });

  it("should handle errors when submitting handover", async () => {
    const error = new Error("Failed to submit");
    const mockApi = {
      get: vi.fn(),
      post: vi.fn().mockRejectedValueOnce(error),
    };
    (useApi as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useShiftHandover());

    const payload = {
      shift_id: "s1",
      situation: "Test",
      background: "Test",
      assessment: "Test",
      recommendation: "Test",
      incoming_nurse_id: "n2",
    };

    let submitError: Error | undefined;
    try {
      await act(async () => {
        await result.current.submitHandover(payload);
      });
    } catch (err) {
      submitError = err as Error;
    }

    // Should throw the error
    expect(submitError).toBeDefined();
  });

  it("should handle errors when acknowledging handover", async () => {
    const error = new Error("Handover not found");
    const mockApi = {
      get: vi.fn(),
      post: vi.fn().mockRejectedValueOnce(error),
    };
    (useApi as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useShiftHandover());

    let ackError: Error | undefined;
    try {
      await act(async () => {
        await result.current.acknowledgeHandover("invalid-id", {
          acknowledgement: "Test",
        });
      });
    } catch (err) {
      ackError = err as Error;
    }

    // Should throw the error
    expect(ackError).toBeDefined();
  });

  it("should call correct API endpoint with proper payload structure", async () => {
    const mockApi = {
      get: vi.fn(),
      post: vi.fn().mockResolvedValueOnce(mockHandover),
    };
    (useApi as unknown as ReturnType<typeof vi.fn>).mockReturnValue(mockApi);

    const { result } = renderHook(() => useShiftHandover());

    const payload = {
      shift_id: "shift-123",
      situation: "S content",
      background: "B content",
      assessment: "A content",
      recommendation: "R content",
      incoming_nurse_id: "nurse-456",
    };

    await act(async () => {
      await result.current.submitHandover(payload);
    });

    // Verify the exact API call
    expect(mockApi.post).toHaveBeenCalledWith("/nurse/shift/shift-123/handover", {
      situation: "S content",
      background: "B content",
      assessment: "A content",
      recommendation: "R content",
      incoming_nurse_id: "nurse-456",
    });
  });
});
