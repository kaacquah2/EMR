import * as React from "react";

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  showCount?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className = "", label, error, showCount, id: idProp, maxLength, value, onChange, ...props }, ref) => {
    const generatedId = React.useId();
    const id = idProp ?? generatedId;
    const currentLength = typeof value === "string" ? value.length : 0;

    return (
      <div className="w-full">
        <div className="flex justify-between items-end mb-1.5">
          {label && (
            <label htmlFor={id} className="block text-xs font-semibold uppercase tracking-wide text-[var(--gray-500)]">
              {label}
            </label>
          )}
          {showCount && maxLength && (
            <span className={`text-[10px] font-medium ${currentLength > maxLength ? "text-[var(--red-600)]" : "text-[var(--gray-400)]"}`}>
              {currentLength} / {maxLength}
            </span>
          )}
        </div>
        <div className="relative">
          <textarea
            ref={ref}
            id={id}
            value={value}
            onChange={onChange}
            maxLength={maxLength}
            aria-invalid={error ? "true" : undefined}
            aria-describedby={error ? `${id}-error` : undefined}
            className={`min-h-[100px] w-full rounded-lg border-[1.5px] border-[var(--gray-300)] bg-white dark:bg-[#0F172A] dark:border-[#334155] px-3 py-2 text-sm text-[var(--gray-900)] dark:text-[var(--gray-100)] placeholder:text-[var(--gray-500)] focus:border-[var(--teal-500)] focus:outline-none focus:ring-[3px] focus:ring-[rgba(11,138,150,0.12)] disabled:cursor-not-allowed disabled:opacity-50 transition-all ${
              error ? "border-[var(--red-600)] focus:border-[var(--red-600)] focus:ring-[rgba(220,38,38,0.12)]" : ""
            } ${className}`}
            {...props}
          />
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

export { Textarea };
