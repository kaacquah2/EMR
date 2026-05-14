"use client";
import * as React from "react";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  showCount?: boolean;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className = "", label, error, showCount, maxLength, value, onChange, ...props }, ref) => {
    const generatedId = React.useId();
    const id = props.id ?? generatedId;
    
    // Internal state if uncontrolled
    const [internalValue, setInternalValue] = React.useState(props.defaultValue || "");
    const currentLength = (value !== undefined ? String(value) : String(internalValue)).length;

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      if (value === undefined) {
        setInternalValue(e.target.value);
      }
      onChange?.(e);
    };

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={id} className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-500)]">
            {label}
          </label>
        )}
        <div className="relative">
          <textarea
            ref={ref}
            id={id}
            value={value}
            onChange={handleChange}
            maxLength={maxLength}
            className={`min-h-[100px] w-full rounded-lg border-[1.5px] border-[var(--gray-300)] bg-white px-3 py-2 text-sm text-[var(--gray-900)] placeholder:text-[var(--gray-500)] focus:border-[var(--teal-500)] focus:outline-none focus:ring-[3px] focus:ring-[rgba(11,138,150,0.12)] disabled:cursor-not-allowed disabled:opacity-50 dark:bg-slate-900 dark:border-[#334155] dark:text-slate-100 ${
              error ? "border-[var(--red-600)] focus:border-[var(--red-600)] focus:ring-[rgba(220,38,38,0.12)]" : ""
            } ${className}`}
            {...props}
          />
          {showCount && maxLength && (
            <div className="absolute bottom-2 right-2 text-[10px] font-medium text-slate-400">
              {currentLength} / {maxLength}
            </div>
          )}
        </div>
        {error && (
          <p id={`${id}-error`} className="mt-1 text-xs text-[var(--red-600)]" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Textarea.displayName = "Textarea";
