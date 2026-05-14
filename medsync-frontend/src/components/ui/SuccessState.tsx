"use client";
import React from "react";
import { CheckCircle2, ArrowRight, Home } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

interface SuccessStateProps {
  title: string;
  description: string;
  actions?: Array<{
    label: string;
    href: string;
    variant?: "primary" | "secondary";
    icon?: React.ElementType;
  }>;
}

export function SuccessState({ title, description, actions }: SuccessStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center animate-in fade-in zoom-in duration-500">
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400">
        <CheckCircle2 className="h-10 w-10" />
      </div>
      
      <h1 className="mb-2 font-sora text-3xl font-bold text-slate-900 dark:text-slate-500">
        {title}
      </h1>
      <p className="mb-10 max-w-md text-lg text-slate-500 dark:text-slate-500">
        {description}
      </p>

      <div className="flex flex-wrap items-center justify-center gap-4">
        {actions?.map((action, idx) => {
          const Icon = action.icon || (idx === 0 ? ArrowRight : undefined);
          return (
            <Link key={idx} href={action.href}>
              <Button
                variant={action.variant === "secondary" ? "secondary" : "primary"}
                size="lg"
                className="gap-2"
              >
                {action.label}
                {Icon && <Icon className="h-4 w-4" />}
              </Button>
            </Link>
          );
        })}
        {!actions && (
          <Link href="/dashboard">
            <Button size="lg" className="gap-2">
              Back to Dashboard
              <Home className="h-4 w-4" />
            </Button>
          </Link>
        )}
      </div>
    </div>
  );
}
