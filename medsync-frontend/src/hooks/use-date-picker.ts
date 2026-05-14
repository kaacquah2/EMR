import { useState, useCallback } from "react";

/**
 * Hook for managing DatePicker state
 * Provides convenient methods for date selection with optional validation
 */
export function useDatePicker(initialDate?: Date | null) {
  const [date, setDate] = useState<Date | null>(initialDate ?? null);

  const setDateFromValue = useCallback((newDate: Date | null) => {
    setDate(newDate);
  }, []);

  const reset = useCallback(() => {
    setDate(initialDate ?? null);
  }, [initialDate]);

  const clear = useCallback(() => {
    setDate(null);
  }, []);

  return {
    date,
    setDate: setDateFromValue,
    reset,
    clear,
    isEmpty: date === null,
    dateString: date ? date.toISOString().split("T")[0] : "",
  };
}

/**
 * Hook for managing DateRangePicker state
 * Provides convenient methods for date range selection
 */
export function useDateRangePicker(
  initialStartDate?: Date | null,
  initialEndDate?: Date | null
) {
  const [startDate, setStartDate] = useState<Date | null>(
    initialStartDate ?? null
  );
  const [endDate, setEndDate] = useState<Date | null>(initialEndDate ?? null);

  const setRange = useCallback(
    (start: Date | null, end: Date | null) => {
      setStartDate(start);
      setEndDate(end);
    },
    []
  );

  const reset = useCallback(() => {
    setStartDate(initialStartDate ?? null);
    setEndDate(initialEndDate ?? null);
  }, [initialStartDate, initialEndDate]);

  const clear = useCallback(() => {
    setStartDate(null);
    setEndDate(null);
  }, []);

  const isValid = startDate && endDate ? startDate <= endDate : true;

  return {
    startDate,
    endDate,
    setStartDate,
    setEndDate,
    setRange,
    reset,
    clear,
    isEmpty: !startDate && !endDate,
    isValid,
    duration: startDate && endDate ? endDate.getTime() - startDate.getTime() : 0,
    durationDays:
      startDate && endDate
        ? Math.ceil(
            (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)
          )
        : 0,
  };
}
