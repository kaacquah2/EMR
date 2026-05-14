import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

type DateFormat = "MM/DD/YYYY" | "DD/MM/YYYY" | "YYYY-MM-DD";

export interface DatePickerProps {
  value?: Date | null;
  onChange: (date: Date | null) => void;
  minDate?: Date;
  maxDate?: Date;
  disabled?: boolean;
  placeholder?: string;
  showTime?: boolean;
  format?: DateFormat;
  className?: string;
  label?: string;
  error?: string;
}

export interface DateRangePickerProps {
  startDate?: Date | null;
  endDate?: Date | null;
  onStartChange: (date: Date | null) => void;
  onEndChange: (date: Date | null) => void;
  minDate?: Date;
  maxDate?: Date;
  format?: DateFormat;
  className?: string;
  label?: string;
  error?: string;
  disabled?: boolean;
}

const monthNames = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

/**
 * Format a Date object to a string based on the specified format
 */
function formatDate(date: Date | null | undefined, format: DateFormat): string {
  if (!date) return "";

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  switch (format) {
    case "DD/MM/YYYY":
      return `${day}/${month}/${year}`;
    case "YYYY-MM-DD":
      return `${year}-${month}-${day}`;
    case "MM/DD/YYYY":
    default:
      return `${month}/${day}/${year}`;
  }
}

/**
 * Parse a date string based on the specified format
 */
function parseDate(dateStr: string, format: DateFormat): Date | null {
  if (!dateStr) return null;

  const parts = dateStr.split(/[\/-]/);
  if (parts.length !== 3) return null;

  let year: number, month: number, day: number;

  switch (format) {
    case "DD/MM/YYYY":
      [day, month, year] = parts.map((p) => parseInt(p, 10));
      break;
    case "YYYY-MM-DD":
      [year, month, day] = parts.map((p) => parseInt(p, 10));
      break;
    case "MM/DD/YYYY":
    default:
      [month, day, year] = parts.map((p) => parseInt(p, 10));
      break;
  }

  if (isNaN(year) || isNaN(month) || isNaN(day)) return null;
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;

  const date = new Date(year, month - 1, day);
  if (date.getMonth() !== month - 1 || date.getDate() !== day) return null;

  return date;
}

/**
 * Get the number of days in a month
 */
function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

/**
 * Get the first day of the week (0-6) for the first day of a month
 */
function getFirstDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 1).getDay();
}

/**
 * Check if two dates are the same day
 */
function isSameDay(date1: Date | null, date2: Date | null): boolean {
  if (!date1 || !date2) return false;
  return (
    date1.getFullYear() === date2.getFullYear() &&
    date1.getMonth() === date2.getMonth() &&
    date1.getDate() === date2.getDate()
  );
}

/**
 * Check if a date is between min and max dates
 */
function isDateInRange(
  date: Date,
  minDate?: Date,
  maxDate?: Date
): boolean {
  if (minDate && date < minDate) return false;
  if (maxDate && date > maxDate) return false;
  return true;
}

/**
 * TimePickerComponent for time selection
 */
interface TimePickerProps {
  value: Date;
  onChange: (date: Date) => void;
  disabled?: boolean;
}

function TimePicker({ value, onChange, disabled }: TimePickerProps) {
  const hours = String(value.getHours()).padStart(2, "0");
  const minutes = String(value.getMinutes()).padStart(2, "0");

  const handleHourChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newHours = parseInt(e.target.value, 10);
    if (!isNaN(newHours) && newHours >= 0 && newHours <= 23) {
      const newDate = new Date(value);
      newDate.setHours(newHours);
      onChange(newDate);
    }
  };

  const handleMinuteChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newMinutes = parseInt(e.target.value, 10);
    if (!isNaN(newMinutes) && newMinutes >= 0 && newMinutes <= 59) {
      const newDate = new Date(value);
      newDate.setMinutes(newMinutes);
      onChange(newDate);
    }
  };

  const incrementHour = () => {
    const newDate = new Date(value);
    newDate.setHours((value.getHours() + 1) % 24);
    onChange(newDate);
  };

  const decrementHour = () => {
    const newDate = new Date(value);
    newDate.setHours((value.getHours() - 1 + 24) % 24);
    onChange(newDate);
  };

  const incrementMinute = () => {
    const newDate = new Date(value);
    newDate.setMinutes((value.getMinutes() + 1) % 60);
    onChange(newDate);
  };

  const decrementMinute = () => {
    const newDate = new Date(value);
    newDate.setMinutes((value.getMinutes() - 1 + 60) % 60);
    onChange(newDate);
  };

  return (
    <div className="flex items-center gap-2 border-t border-[var(--gray-300)] dark:border-[#334155] pt-3">
      <div className="flex flex-col items-center gap-1">
        <button
          onClick={incrementHour}
          disabled={disabled}
          className="rounded p-1 hover:bg-[var(--gray-100)] dark:hover:bg-[#334155] disabled:opacity-50"
          aria-label="Increase hour"
          type="button"
        >
          <ChevronLeft className="h-4 w-4 rotate-90" />
        </button>
        <input
          type="number"
          min="0"
          max="23"
          value={hours}
          onChange={handleHourChange}
          disabled={disabled}
          className="h-10 w-12 rounded border border-[var(--gray-300)] dark:border-[#334155] text-center text-sm font-semibold bg-white dark:bg-slate-900 dark:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-[var(--teal-500)]"
          aria-label="Hour"
        />
        <button
          onClick={decrementHour}
          disabled={disabled}
          className="rounded p-1 hover:bg-[var(--gray-100)] dark:hover:bg-[#334155] disabled:opacity-50"
          aria-label="Decrease hour"
          type="button"
        >
          <ChevronLeft className="h-4 w-4 -rotate-90" />
        </button>
      </div>

      <span className="text-lg font-semibold text-[var(--gray-900)] dark:text-[var(--gray-100)]">
        :
      </span>

      <div className="flex flex-col items-center gap-1">
        <button
          onClick={incrementMinute}
          disabled={disabled}
          className="rounded p-1 hover:bg-[var(--gray-100)] dark:hover:bg-[#334155] disabled:opacity-50"
          aria-label="Increase minute"
          type="button"
        >
          <ChevronLeft className="h-4 w-4 rotate-90" />
        </button>
        <input
          type="number"
          min="0"
          max="59"
          value={minutes}
          onChange={handleMinuteChange}
          disabled={disabled}
          className="h-10 w-12 rounded border border-[var(--gray-300)] dark:border-[#334155] text-center text-sm font-semibold bg-white dark:bg-slate-900 dark:bg-slate-100 focus:outline-none focus:ring-2 focus:ring-[var(--teal-500)]"
          aria-label="Minute"
        />
        <button
          onClick={decrementMinute}
          disabled={disabled}
          className="rounded p-1 hover:bg-[var(--gray-100)] dark:hover:bg-[#334155] disabled:opacity-50"
          aria-label="Decrease minute"
          type="button"
        >
          <ChevronLeft className="h-4 w-4 -rotate-90" />
        </button>
      </div>
    </div>
  );
}

/**
 * CalendarComponent for date selection
 */
interface CalendarProps {
  value: Date | null;
  onChange: (date: Date) => void;
  minDate?: Date;
  maxDate?: Date;
  disabled?: boolean;
  showTime?: boolean;
}

function Calendar({
  value,
  onChange,
  minDate,
  maxDate,
  disabled,
  showTime,
}: CalendarProps) {
  const [currentMonth, setCurrentMonth] = React.useState(() => {
    if (value) return new Date(value);
    return new Date();
  });

  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();

  const daysInMonth = getDaysInMonth(year, month);
  const firstDayOfMonth = getFirstDayOfMonth(year, month);

  const today = new Date();
  const days: (number | null)[] = [];

  for (let i = 0; i < firstDayOfMonth; i++) {
    days.push(null);
  }

  for (let i = 1; i <= daysInMonth; i++) {
    days.push(i);
  }

  const handleDayClick = (day: number) => {
    const newDate = new Date(year, month, day);
    if (isDateInRange(newDate, minDate, maxDate)) {
      if (value && showTime) {
        newDate.setHours(value.getHours(), value.getMinutes());
      }
      onChange(newDate);
    }
  };

  const handlePrevMonth = () => {
    setCurrentMonth(new Date(year, month - 1));
  };

  const handleNextMonth = () => {
    setCurrentMonth(new Date(year, month + 1));
  };


  return (
    <div
      className="w-80 rounded-lg border border-[var(--gray-300)] dark:border-[#334155] bg-white dark:bg-slate-900 dark:bg-slate-100 p-4 shadow-lg"
      role="application"
    >
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrevMonth}
            disabled={disabled}
            className="rounded p-1 hover:bg-[var(--gray-100)] dark:hover:bg-[#334155] disabled:opacity-50"
            aria-label="Previous month"
            type="button"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
        </div>

        <div className="flex flex-1 flex-col items-center">
          <h2 className="text-sm font-semibold text-[var(--gray-900)] dark:text-[var(--gray-100)]">
            {monthNames[month]}
          </h2>
          <button
            onClick={(e) => {
              e.stopPropagation();
              // Toggle year selector or just show the year
            }}
            className="text-xs text-[var(--gray-500)] hover:text-[var(--gray-900)] dark:hover:text-[var(--gray-100)] cursor-pointer"
            type="button"
          >
            {year}
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleNextMonth}
            disabled={disabled}
            className="rounded p-1 hover:bg-[var(--gray-100)] dark:hover:bg-[#334155] disabled:opacity-50"
            aria-label="Next month"
            type="button"
          >
            <ChevronRight className="h-5 w-5" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 gap-1 mb-3">
        {dayNames.map((day) => (
          <div
            key={day}
            className="h-8 flex items-center justify-center text-xs font-semibold text-[var(--gray-500)]"
          >
            {day}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {days.map((day, index) => {
          if (day === null) {
            return (
              <div
                key={`empty-${index}`}
                className="h-8 rounded cursor-default"
              />
            );
          }

          const date = new Date(year, month, day);
          const isToday = isSameDay(date, today);
          const isSelected = isSameDay(date, value);
          const isDisabledDate = !isDateInRange(date, minDate, maxDate) || disabled;

          return (
            <button
              key={day}
              onClick={() => handleDayClick(day)}
              disabled={isDisabledDate}
              className={`
                h-8 rounded text-sm font-medium transition-colors
                ${isSelected
                  ? "bg-[var(--teal-500)] text-white"
                  : isToday
                    ? "border border-[var(--teal-500)] text-[var(--teal-500)]"
                    : "text-[var(--gray-900)] dark:text-[var(--gray-100)]"
                }
                ${!isDisabledDate
                  ? "hover:bg-[var(--gray-100)] dark:hover:bg-[#334155] cursor-pointer"
                  : "opacity-30 cursor-not-allowed"
                }
              `}
              aria-pressed={isSelected}
              aria-disabled={isDisabledDate}
              type="button"
            >
              {day}
            </button>
          );
        })}
      </div>

      {showTime && value && (
        <TimePicker value={value} onChange={onChange} disabled={disabled} />
      )}
    </div>
  );
}

/**
 * DatePicker component - supports date only, date + time, and date range selection
 *
 * @example
 * ```tsx
 * <DatePicker
 *   value={appointmentDate}
 *   onChange={setAppointmentDate}
 *   showTime
 *   format="MM/DD/YYYY"
 *   minDate={new Date()}
 * />
 * ```
 */
const DatePicker = React.forwardRef<HTMLDivElement, DatePickerProps>(
  (
    {
      value,
      onChange,
      minDate,
      maxDate,
      disabled = false,
      placeholder = "Select date",
      showTime = false,
      format = "MM/DD/YYYY",
      className = "",
      label,
      error,
    },
    ref
  ) => {
    const [isOpen, setIsOpen] = React.useState(false);
    const [inputValue, setInputValue] = React.useState(formatDate(value, format));
    const inputRef = React.useRef<HTMLInputElement>(null);
    const containerRef = React.useRef<HTMLDivElement>(null);

    // Update input value when value prop changes
    React.useEffect(() => {
      setInputValue(formatDate(value, format));
    }, [value, format]);

    // Handle outside clicks
    React.useEffect(() => {
      function handleClickOutside(event: MouseEvent) {
        if (
          containerRef.current &&
          !containerRef.current.contains(event.target as Node)
        ) {
          setIsOpen(false);
        }
      }

      if (isOpen) {
        document.addEventListener("mousedown", handleClickOutside);
        return () =>
          document.removeEventListener("mousedown", handleClickOutside);
      }
    }, [isOpen]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setInputValue(e.target.value);

      const parsed = parseDate(e.target.value, format);
      if (parsed && isDateInRange(parsed, minDate, maxDate)) {
        onChange(parsed);
      }
    };

    const handleCalendarChange = (date: Date) => {
      onChange(date);
      setInputValue(formatDate(date, format));
      if (!showTime) {
        setIsOpen(false);
      }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      } else if (e.key === "Enter" && !isOpen) {
        setIsOpen(true);
      }
    };

    const idProp = React.useId();

    return (
      <div className="w-full" ref={ref}>
        {label && (
          <label
            htmlFor={idProp}
            className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-500)]"
          >
            {label}
          </label>
        )}
        <div className="relative" ref={containerRef}>
          <input
            ref={inputRef}
            id={idProp}
            type="text"
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onFocus={() => setIsOpen(true)}
            placeholder={placeholder}
            disabled={disabled}
            aria-invalid={error ? "true" : undefined}
            aria-describedby={error ? `${idProp}-error` : undefined}
            className={`h-11 w-full rounded-lg border-[1.5px] border-[var(--gray-300)] dark:border-[#334155] bg-white dark:bg-slate-900 dark:bg-slate-100 px-3 py-2 text-sm text-[var(--gray-900)] dark:text-[var(--gray-100)] placeholder:text-[var(--gray-500)] focus:border-[var(--teal-500)] focus:outline-none focus:ring-[3px] focus:ring-[rgba(11,138,150,0.12)] disabled:cursor-not-allowed disabled:opacity-50 ${
              error
                ? "border-[var(--red-600)] focus:border-[var(--red-600)] focus:ring-[rgba(220,38,38,0.12)]"
                : ""
            } ${className}`}
          />

          {isOpen && !disabled && (
            <div className="absolute top-full left-0 mt-2 z-50">
              <Calendar
                value={value || null}
                onChange={handleCalendarChange}
                minDate={minDate}
                maxDate={maxDate}
                disabled={disabled}
                showTime={showTime}
              />
            </div>
          )}
        </div>

        {error && (
          <p
            id={`${idProp}-error`}
            className="mt-1 text-xs text-[var(--red-600)]"
            role="alert"
          >
            {error}
          </p>
        )}
      </div>
    );
  }
);

DatePicker.displayName = "DatePicker";

/**
 * DateRangePicker component - for selecting start and end dates
 *
 * @example
 * ```tsx
 * <DateRangePicker
 *   startDate={startDate}
 *   endDate={endDate}
 *   onStartChange={setStartDate}
 *   onEndChange={setEndDate}
 *   format="MM/DD/YYYY"
 * />
 * ```
 */
const DateRangePicker = React.forwardRef<HTMLDivElement, DateRangePickerProps>(
  (
    {
      startDate,
      endDate,
      onStartChange,
      onEndChange,
      minDate,
      maxDate,
      format = "MM/DD/YYYY",
      className = "",
      label,
      error,
      disabled = false,
    },
    ref
  ) => {
    const [isStartOpen, setIsStartOpen] = React.useState(false);
    const [isEndOpen, setIsEndOpen] = React.useState(false);
    const [startInputValue, setStartInputValue] = React.useState(
      formatDate(startDate, format)
    );
    const [endInputValue, setEndInputValue] = React.useState(
      formatDate(endDate, format)
    );
    const startInputRef = React.useRef<HTMLInputElement>(null);
    const endInputRef = React.useRef<HTMLInputElement>(null);
    const containerRef = React.useRef<HTMLDivElement>(null);

    // Update input values when props change
    React.useEffect(() => {
      setStartInputValue(formatDate(startDate, format));
    }, [startDate, format]);

    React.useEffect(() => {
      setEndInputValue(formatDate(endDate, format));
    }, [endDate, format]);

    // Handle outside clicks
    React.useEffect(() => {
      function handleClickOutside(event: MouseEvent) {
        if (
          containerRef.current &&
          !containerRef.current.contains(event.target as Node)
        ) {
          setIsStartOpen(false);
          setIsEndOpen(false);
        }
      }

      if (isStartOpen || isEndOpen) {
        document.addEventListener("mousedown", handleClickOutside);
        return () =>
          document.removeEventListener("mousedown", handleClickOutside);
      }
    }, [isStartOpen, isEndOpen]);

    const handleStartInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setStartInputValue(e.target.value);

      const parsed = parseDate(e.target.value, format);
      if (parsed && isDateInRange(parsed, minDate, maxDate)) {
        onStartChange(parsed);
      }
    };

    const handleEndInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setEndInputValue(e.target.value);

      const parsed = parseDate(e.target.value, format);
      if (parsed && isDateInRange(parsed, minDate, maxDate)) {
        onEndChange(parsed);
      }
    };

    const handleStartCalendarChange = (date: Date) => {
      onStartChange(date);
      setStartInputValue(formatDate(date, format));
      setIsStartOpen(false);
    };

    const handleEndCalendarChange = (date: Date) => {
      onEndChange(date);
      setEndInputValue(formatDate(date, format));
      setIsEndOpen(false);
    };

    const idProp = React.useId();
    const startIdProp = `${idProp}-start`;
    const endIdProp = `${idProp}-end`;

    return (
      <div className="w-full" ref={ref}>
        {label && (
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-500)]">
            {label}
          </label>
        )}
        <div
          className={`flex flex-col gap-2 sm:flex-row sm:gap-3 ${className}`}
          ref={containerRef}
        >
          <div className="flex-1 relative">
            <label
              htmlFor={startIdProp}
              className="mb-1 block text-xs font-medium text-[var(--gray-500)]"
            >
              Start Date
            </label>
            <input
              ref={startInputRef}
              id={startIdProp}
              type="text"
              value={startInputValue}
              onChange={handleStartInputChange}
              onFocus={() => setIsStartOpen(true)}
              placeholder="Start date"
              disabled={disabled}
              aria-invalid={error ? "true" : undefined}
              aria-describedby={error ? `${idProp}-error` : undefined}
              className={`h-11 w-full rounded-lg border-[1.5px] border-[var(--gray-300)] dark:border-[#334155] bg-white dark:bg-slate-900 dark:bg-slate-100 px-3 py-2 text-sm text-[var(--gray-900)] dark:text-[var(--gray-100)] placeholder:text-[var(--gray-500)] focus:border-[var(--teal-500)] focus:outline-none focus:ring-[3px] focus:ring-[rgba(11,138,150,0.12)] disabled:cursor-not-allowed disabled:opacity-50 ${
                error
                  ? "border-[var(--red-600)] focus:border-[var(--red-600)] focus:ring-[rgba(220,38,38,0.12)]"
                  : ""
              }`}
            />

            {isStartOpen && !disabled && (
              <div className="absolute top-full left-0 mt-2 z-50">
                <Calendar
                  value={startDate || null}
                  onChange={handleStartCalendarChange}
                  minDate={minDate}
                  maxDate={endDate || maxDate}
                  disabled={disabled}
                  showTime={false}
                />
              </div>
            )}
          </div>

          <div className="flex-1 relative">
            <label
              htmlFor={endIdProp}
              className="mb-1 block text-xs font-medium text-[var(--gray-500)]"
            >
              End Date
            </label>
            <input
              ref={endInputRef}
              id={endIdProp}
              type="text"
              value={endInputValue}
              onChange={handleEndInputChange}
              onFocus={() => setIsEndOpen(true)}
              placeholder="End date"
              disabled={disabled}
              aria-invalid={error ? "true" : undefined}
              aria-describedby={error ? `${idProp}-error` : undefined}
              className={`h-11 w-full rounded-lg border-[1.5px] border-[var(--gray-300)] dark:border-[#334155] bg-white dark:bg-slate-900 dark:bg-slate-100 px-3 py-2 text-sm text-[var(--gray-900)] dark:text-[var(--gray-100)] placeholder:text-[var(--gray-500)] focus:border-[var(--teal-500)] focus:outline-none focus:ring-[3px] focus:ring-[rgba(11,138,150,0.12)] disabled:cursor-not-allowed disabled:opacity-50 ${
                error
                  ? "border-[var(--red-600)] focus:border-[var(--red-600)] focus:ring-[rgba(220,38,38,0.12)]"
                  : ""
              }`}
            />

            {isEndOpen && !disabled && (
              <div className="absolute top-full left-0 mt-2 z-50">
                <Calendar
                  value={endDate || null}
                  onChange={handleEndCalendarChange}
                  minDate={startDate || minDate}
                  maxDate={maxDate}
                  disabled={disabled}
                  showTime={false}
                />
              </div>
            )}
          </div>
        </div>

        {error && (
          <p
            id={`${idProp}-error`}
            className="mt-1 text-xs text-[var(--red-600)]"
            role="alert"
          >
            {error}
          </p>
        )}
      </div>
    );
  }
);

DateRangePicker.displayName = "DateRangePicker";

export { DatePicker, DateRangePicker, Calendar, TimePicker };
