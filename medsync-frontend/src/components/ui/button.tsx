import * as React from "react";
import { LoadingSpinner } from "./loading-spinner";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "outline";
  size?: "default" | "sm" | "lg";
  fullWidth?: boolean;
  loading?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className = "",
      variant = "primary",
      size = "default",
      fullWidth = false,
      loading = false,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const base =
      "inline-flex items-center justify-center rounded-lg font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--teal-500)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-40";
    const variants = {
      primary:
        "bg-[var(--teal-500)] text-white hover:bg-[#0A7A85] active:bg-[#096B75] dark:hover:bg-[#0EAFBE] shadow-sm",
      secondary:
        "bg-white dark:bg-[#1E293B] border-[1.5px] border-[var(--gray-300)] dark:border-[#334155] text-[var(--navy-900)] dark:text-[var(--gray-100)] hover:bg-[var(--gray-100)] dark:hover:bg-[#334155]",
      danger:
        "bg-[var(--red-600)] text-white hover:bg-[#B91C1C] active:bg-[#991B1B] shadow-sm",
      ghost:
        "bg-transparent text-[var(--navy-900)] dark:text-[var(--gray-100)] hover:bg-[var(--gray-100)] dark:hover:bg-[#334155]",
      outline:
        "bg-transparent border border-[var(--gray-300)] dark:border-[#334155] text-[var(--navy-900)] dark:text-[var(--gray-100)] hover:bg-[var(--gray-100)] dark:hover:bg-[#334155]",
    };
    const sizes = {
      default: "h-11 px-4 text-[15px]",
      sm: "h-9 px-3 text-sm",
      lg: "h-12 px-6 text-base",
    };

    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        className={`${base} ${variants[variant]} ${sizes[size]} ${fullWidth ? "w-full" : ""} ${className}`}
        disabled={isDisabled}
        {...props}
      >
        {loading && (
          <LoadingSpinner 
            size="sm" 
            className="mr-2 !border-current !border-t-transparent" 
          />
        )}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";

export { Button };
