"use client"

import * as React from "react"

const DropdownMenu = ({ children }: { children: React.ReactNode }) => {
  return <div className="relative inline-block text-left">{children}</div>
}

const DropdownMenuTrigger = ({ asChild, children }: { asChild?: boolean, children: React.ReactNode }) => {
  if (asChild && React.isValidElement(children)) {
    return children
  }
  return <button>{children}</button>
}

const DropdownMenuContent = ({ align = "end", className = "", children }: { align?: "start" | "end", className?: string, children: React.ReactNode }) => {
  const alignClass = align === "end" ? "right-0" : "left-0"
  return (
    <div className={`absolute ${alignClass} z-50 mt-2 w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none dark:bg-slate-800 ${className}`}>
      <div className="py-1">{children}</div>
    </div>
  )
}

const DropdownMenuItem = ({ className = "", children }: { className?: string, children: React.ReactNode }) => {
  return (
    <button
      className={`flex w-full items-center px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-200 dark:hover:bg-slate-700 dark:hover:text-slate-50 ${className}`}
    >
      {children}
    </button>
  )
}

export { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem }
