import * as React from "react";

export interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: string;
  error?: string;
  size?: "default" | "lg";
}

const EyeIcon = () => (
  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
  </svg>
);

const EyeOffIcon = () => (
  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
  </svg>
);

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className = "", label, error, type, size = "default", id: idProp, ...props }, ref) => {
    const generatedId = React.useId();
    const id = idProp ?? generatedId;
    const [revealed, setRevealed] = React.useState(false);
    const isPassword = type === "password";
    const inputType = isPassword && revealed ? "text" : type;

    const sizeClasses = size === "lg" ? "h-12 px-4 text-base" : "h-11 px-3 text-sm";

    return (
      <div className="w-full">
        {label && (
          <label htmlFor={id} className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-500)]">
            {label}
          </label>
        )}
        <div className="relative">
          <input
            ref={ref}
            id={id}
            type={inputType}
            aria-invalid={error ? "true" : undefined}
            aria-describedby={error ? `${id}-error` : undefined}
            className={`${sizeClasses} w-full rounded-lg border-[1.5px] border-[var(--gray-300)] bg-white dark:bg-slate-900 dark:border-[#334155] py-2 text-[var(--gray-900)] dark:text-slate-100 placeholder:text-[var(--gray-500)] focus:border-[var(--teal-500)] focus:outline-none focus:ring-[3px] focus:ring-[rgba(11,138,150,0.12)] disabled:cursor-not-allowed disabled:opacity-50 ${
              isPassword ? "pr-11" : ""
            } ${
              error ? "border-[var(--red-600)] focus:border-[var(--red-600)] focus:ring-[rgba(220,38,38,0.12)]" : ""
            } ${className}`}
            {...props}
          />
          {isPassword && (
            <button
              type="button"
              onClick={() => setRevealed((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-[var(--gray-500)] hover:bg-[var(--gray-100)] dark:hover:bg-[#334155] hover:text-[var(--gray-900)] focus:outline-none focus:ring-2 focus:ring-[var(--teal-500)] focus:ring-offset-1"
              tabIndex={-1}
              aria-label={revealed ? "Hide password" : "Show password"}
            >
              {revealed ? <EyeOffIcon /> : <EyeIcon />}
            </button>
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
Input.displayName = "Input";

export { Input };
