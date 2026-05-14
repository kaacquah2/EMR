"use client";

import Link from "next/link";

export type BreadcrumbItem = { label: string; href?: string };

export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  if (!items.length) return null;
  return (
    <nav aria-label="Breadcrumb" className="text-sm text-slate-500 dark:text-slate-500">
      <ol className="flex flex-wrap items-center gap-1">
        {items.map((item, i) => {
          const isLast = i === items.length - 1;
          return (
            <li key={i} className="flex items-center gap-1">
              {i > 0 && <span className="text-[#94A3B8]">/</span>}
              {item.href && !isLast ? (
                <Link
                  href={item.href}
                  className="text-[#0EAFBE] hover:underline"
                >
                  {item.label}
                </Link>
              ) : (
                <span className={isLast ? "font-medium text-slate-900 dark:text-slate-100" : undefined}>
                  {item.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
