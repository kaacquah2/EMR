import * as React from "react";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "outline";
  size?: "default" | "sm" | "lg";
  fullWidth?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className = "",
      variant = "primary",
      size = "default",
      fullWidth = false,
      disabled,
      ...props
    },
    ref
  ) => {
    const base =
      "inline-flex items-center justify-center rounded-lg font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-40";
    const variants = {
      primary:
        "bg-[#0B8A96] text-white hover:bg-[#0A7A85] active:bg-[#096B75]",
      secondary:
        "bg-white border-[1.5px] border-[#CBD5E1] text-[#0C1F3D] hover:bg-[#F1F5F9]",
      danger: "bg-[#DC2626] text-white hover:bg-[#B91C1C] active:bg-[#991B1B]",
      ghost: "bg-transparent text-[#0C1F3D] hover:bg-[#F1F5F9]",
      outline: "bg-transparent border border-[#CBD5E1] text-[#0C1F3D] hover:bg-[#F1F5F9]",
    };
    const sizes = {
      default: "h-11 px-4 text-[15px]",
      sm: "h-9 px-3 text-sm",
      lg: "h-12 px-6 text-base",
    };
    return (
      <button
        ref={ref}
        className={`${base} ${variants[variant]} ${sizes[size]} ${fullWidth ? "w-full" : ""} ${className}`}
        disabled={disabled}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button };
