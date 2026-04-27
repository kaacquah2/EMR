import * as React from "react";

export interface LoadingSpinnerProps {
  size?: "sm" | "default" | "lg";
  className?: string;
}

const sizeClasses = {
  sm: "h-6 w-6 border-2",
  default: "h-8 w-8 border-2",
  lg: "h-10 w-10 border-2",
};

export function LoadingSpinner({
  size = "default",
  className = "",
}: LoadingSpinnerProps) {
  return (
    <div
      className={`animate-spin rounded-full border-[var(--teal-500)] border-t-transparent ${sizeClasses[size]} ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
}

export function LoadingScreen({
  minHeight = "40vh",
  size = "lg",
}: {
  minHeight?: string;
  size?: "sm" | "default" | "lg";
}) {
  return (
    <div
      className="flex items-center justify-center"
      style={{ minHeight }}
    >
      <LoadingSpinner size={size} />
    </div>
  );
}
