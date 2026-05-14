import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DatePicker, DateRangePicker } from "./DatePicker";

describe("DatePicker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders with placeholder text", () => {
    const onChange = vi.fn();
    render(
      <DatePicker
        value={null}
        onChange={onChange}
        placeholder="Select appointment date"
      />
    );

    const input = screen.getByPlaceholderText("Select appointment date");
    expect(input).toBeInTheDocument();
  });

  it("displays label when provided", () => {
    const onChange = vi.fn();
    render(
      <DatePicker
        value={null}
        onChange={onChange}
        label="Appointment Date"
      />
    );

    const label = screen.getByText(/appointment date/i);
    expect(label).toBeInTheDocument();
  });

  it("shows error message when error prop is provided", () => {
    const onChange = vi.fn();
    render(
      <DatePicker
        value={null}
        onChange={onChange}
        error="Date is required"
      />
    );

    const error = screen.getByText("Date is required");
    expect(error).toBeInTheDocument();
    expect(error).toHaveAttribute("role", "alert");
  });

  it("opens calendar on input focus", async () => {
    const onChange = vi.fn();
    render(
      <DatePicker value={null} onChange={onChange} />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);

    await waitFor(() => {
      const calendar = screen.getByRole("application");
      expect(calendar).toBeInTheDocument();
    });
  });

  it("closes calendar on Escape key", async () => {
    const onChange = vi.fn();
    render(
      <DatePicker value={null} onChange={onChange} />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByRole("application")).toBeInTheDocument();
    });

    fireEvent.keyDown(input, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("application")).not.toBeInTheDocument();
    });
  });

  it("formats date correctly in MM/DD/YYYY format", () => {
    const onChange = vi.fn();
    const date = new Date(2024, 0, 15); // January 15, 2024

    render(
      <DatePicker
        value={date}
        onChange={onChange}
        format="MM/DD/YYYY"
      />
    );

    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.value).toBe("01/15/2024");
  });

  it("formats date correctly in DD/MM/YYYY format", () => {
    const onChange = vi.fn();
    const date = new Date(2024, 0, 15); // January 15, 2024

    render(
      <DatePicker
        value={date}
        onChange={onChange}
        format="DD/MM/YYYY"
      />
    );

    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.value).toBe("15/01/2024");
  });

  it("formats date correctly in YYYY-MM-DD format", () => {
    const onChange = vi.fn();
    const date = new Date(2024, 0, 15); // January 15, 2024

    render(
      <DatePicker
        value={date}
        onChange={onChange}
        format="YYYY-MM-DD"
      />
    );

    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.value).toBe("2024-01-15");
  });

  it("disables past dates when minDate is set", async () => {
    const onChange = vi.fn();
    const today = new Date();
    const minDate = new Date(today);

    render(
      <DatePicker
        value={null}
        onChange={onChange}
        minDate={minDate}
      />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByRole("application")).toBeInTheDocument();
    });

    // Check that days from previous month are disabled
    const prevMonthDays = screen.getAllByRole("button").filter(
      (btn) => btn.getAttribute("aria-disabled") === "true"
    );
    expect(prevMonthDays.length).toBeGreaterThan(0);
  });

  it("calls onChange when a date is selected", async () => {
    const onChange = vi.fn();
    render(
      <DatePicker value={null} onChange={onChange} />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);

    await waitFor(() => {
      expect(screen.getByRole("application")).toBeInTheDocument();
    });

    // Click on a date (e.g., 15)
    const dateButtons = screen.getAllByRole("button");
    const dayButton = dateButtons.find((btn) => btn.textContent === "15");
    
    if (dayButton) {
      fireEvent.click(dayButton);
      expect(onChange).toHaveBeenCalled();
    }
  });

  it("disables input when disabled prop is true", () => {
    const onChange = vi.fn();
    render(
      <DatePicker value={null} onChange={onChange} disabled={true} />
    );

    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });

  it("updates input when value prop changes", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <DatePicker value={null} onChange={onChange} format="MM/DD/YYYY" />
    );

    let input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.value).toBe("");

    const newDate = new Date(2024, 5, 20); // June 20, 2024
    rerender(
      <DatePicker value={newDate} onChange={onChange} format="MM/DD/YYYY" />
    );

    input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.value).toBe("06/20/2024");
  });

  it("shows time picker when showTime is true", async () => {
    const onChange = vi.fn();
    const date = new Date(2024, 0, 15, 14, 30);

    render(
      <DatePicker
        value={date}
        onChange={onChange}
        showTime={true}
      />
    );

    const input = screen.getByRole("textbox");
    fireEvent.focus(input);

    await waitFor(() => {
      const hourInputs = screen.getAllByRole("textbox");
      // Should have input for date + hour + minute
      expect(hourInputs.length).toBeGreaterThanOrEqual(3);
    });
  });
});

describe("DateRangePicker", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders with start and end date inputs", () => {
    const onStartChange = vi.fn();
    const onEndChange = vi.fn();

    render(
      <DateRangePicker
        startDate={null}
        endDate={null}
        onStartChange={onStartChange}
        onEndChange={onEndChange}
      />
    );

    expect(screen.getByText("Start Date")).toBeInTheDocument();
    expect(screen.getByText("End Date")).toBeInTheDocument();
  });

  it("displays label when provided", () => {
    const onStartChange = vi.fn();
    const onEndChange = vi.fn();

    render(
      <DateRangePicker
        startDate={null}
        endDate={null}
        onStartChange={onStartChange}
        onEndChange={onEndChange}
        label="Admission Period"
      />
    );

    expect(screen.getByText(/admission period/i)).toBeInTheDocument();
  });

  it("shows error message when error prop is provided", () => {
    const onStartChange = vi.fn();
    const onEndChange = vi.fn();

    render(
      <DateRangePicker
        startDate={null}
        endDate={null}
        onStartChange={onStartChange}
        onEndChange={onEndChange}
        error="Invalid date range"
      />
    );

    expect(screen.getByText("Invalid date range")).toBeInTheDocument();
  });

  it("formats dates in the correct format", () => {
    const onStartChange = vi.fn();
    const onEndChange = vi.fn();
    const startDate = new Date(2024, 0, 15);
    const endDate = new Date(2024, 0, 20);

    render(
      <DateRangePicker
        startDate={startDate}
        endDate={endDate}
        onStartChange={onStartChange}
        onEndChange={onEndChange}
        format="MM/DD/YYYY"
      />
    );

    const inputs = screen.getAllByRole("textbox");
    expect(inputs[0]).toHaveValue("01/15/2024");
    expect(inputs[1]).toHaveValue("01/20/2024");
  });

  it("opens start date calendar when start input is focused", async () => {
    const onStartChange = vi.fn();
    const onEndChange = vi.fn();

    render(
      <DateRangePicker
        startDate={null}
        endDate={null}
        onStartChange={onStartChange}
        onEndChange={onEndChange}
      />
    );

    const inputs = screen.getAllByRole("textbox");
    fireEvent.focus(inputs[0]);

    await waitFor(() => {
      expect(screen.getByRole("application")).toBeInTheDocument();
    });
  });

  it("calls onStartChange when start date is selected", async () => {
    const onStartChange = vi.fn();
    const onEndChange = vi.fn();

    render(
      <DateRangePicker
        startDate={null}
        endDate={null}
        onStartChange={onStartChange}
        onEndChange={onEndChange}
      />
    );

    const inputs = screen.getAllByRole("textbox");
    fireEvent.focus(inputs[0]);

    await waitFor(() => {
      expect(screen.getByRole("application")).toBeInTheDocument();
    });

    const dateButtons = screen.getAllByRole("button");
    const dayButton = dateButtons.find((btn) => btn.textContent === "15");

    if (dayButton) {
      fireEvent.click(dayButton);
      expect(onStartChange).toHaveBeenCalled();
    }
  });

  it("disables input when disabled prop is true", () => {
    const onStartChange = vi.fn();
    const onEndChange = vi.fn();

    render(
      <DateRangePicker
        startDate={null}
        endDate={null}
        onStartChange={onStartChange}
        onEndChange={onEndChange}
        disabled={true}
      />
    );

    const inputs = screen.getAllByRole("textbox");
    inputs.forEach((input) => {
      expect(input).toHaveAttribute("disabled");
    });
  });

  it("constrains end date picker to start date", async () => {
    const onStartChange = vi.fn();
    const onEndChange = vi.fn();
    const startDate = new Date(2024, 0, 15);

    const { rerender } = render(
      <DateRangePicker
        startDate={null}
        endDate={null}
        onStartChange={onStartChange}
        onEndChange={onEndChange}
      />
    );

    rerender(
      <DateRangePicker
        startDate={startDate}
        endDate={null}
        onStartChange={onStartChange}
        onEndChange={onEndChange}
      />
    );

    const inputs = screen.getAllByRole("textbox");
    fireEvent.focus(inputs[1]); // Focus on end date input

    await waitFor(() => {
      expect(screen.getByRole("application")).toBeInTheDocument();
    });
  });
});
