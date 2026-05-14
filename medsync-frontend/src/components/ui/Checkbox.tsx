"use client";
import * as React from "react";
import { Check } from "lucide-react";

export interface CheckboxProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, error, ...props }, ref) => {
    const id = React.useId();
    return (
      <div className="checkbox-container flex flex-col gap-1.5">
        <label
          htmlFor={id}
          className="checkbox-label group flex cursor-pointer items-start gap-2.5 text-sm font-medium leading-tight text-slate-700 dark:text-slate-100 peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
        >
          <div className="checkbox-box relative flex h-5 w-5 shrink-0 items-center justify-center rounded border border-slate-300 bg-white transition-all group-hover:border-[var(--teal-500)] dark:border-slate-700 dark:bg-slate-900 group-active:scale-95">
            <input
              type="checkbox"
              id={id}
              ref={ref}
              className="peer absolute inset-0 cursor-pointer opacity-0"
              {...props}
            />
            <div className="flex h-full w-full items-center justify-center rounded bg-[var(--teal-500)] opacity-0 transition-opacity peer-checked:opacity-100">
              <Check className="h-3.5 w-3.5 text-white stroke-[3]" />
            </div>
          </div>
          {label && <span className="pt-0.5">{label}</span>}
        </label>
        {error && (
          <p className="ml-7 text-xs text-[var(--red-600)]" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Checkbox.displayName = "Checkbox";
