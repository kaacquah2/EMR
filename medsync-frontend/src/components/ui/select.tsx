import * as React from "react";

export interface SelectProps
  extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ className = "", label, error, children, id: idProp, ...props }, ref) => {
    const generatedId = React.useId();
    const id = idProp ?? generatedId;

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={id} className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-500)]">
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            id={id}
            aria-invalid={error ? "true" : undefined}
            aria-describedby={error ? `${id}-error` : undefined}
            className={`h-11 w-full appearance-none rounded-lg border-[1.5px] border-[var(--gray-300)] bg-white dark:bg-[#0F172A] dark:border-[#334155] px-3 py-2 text-sm text-[var(--gray-900)] dark:text-[var(--gray-100)] focus:border-[var(--teal-500)] focus:outline-none focus:ring-[3px] focus:ring-[rgba(11,138,150,0.12)] disabled:cursor-not-allowed disabled:opacity-50 transition-all ${
              error ? "border-[var(--red-600)] focus:border-[var(--red-600)] focus:ring-[rgba(220,38,38,0.12)]" : ""
            } ${className}`}
            {...props}
          >
            {children}
          </select>
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-[var(--gray-500)]">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
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
Select.displayName = "Select";

export { Select };
