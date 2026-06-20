import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Utility to merge Tailwind classes safely using clsx and tailwind-merge.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Formats a date string into a localized readable format using Africa/Accra timezone.
 */
export function formatDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date
  return d.toLocaleDateString("en-GH", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Africa/Accra",
  })
}

/**
 * Formats a date and time string into a localized readable format using Africa/Accra timezone.
 */
export function formatDateTime(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date
  return d.toLocaleString("en-GH", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Africa/Accra",
  })
}

/**
 * Formats a time string into a localized readable format using Africa/Accra timezone.
 */
export function formatTime(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date
  return d.toLocaleTimeString("en-GH", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Africa/Accra",
  })
}

/**
 * Calculates age from date of birth.
 */
export function calculateAge(dob: string): number {
  const birthDate = new Date(dob)
  const today = new Date()
  let age = today.getFullYear() - birthDate.getFullYear()
  const m = today.getMonth() - birthDate.getMonth()
  if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
    age--
  }
  return age
}
