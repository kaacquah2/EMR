'use client';

/**
 * RoleGate - Centralized role-based access control component
 * 
 * Usage:
 *   <RoleGate roles={['doctor', 'hospital_admin']}>
 *     <ProtectedFeature />
 *   </RoleGate>
 * 
 * With fallback:
 *   <RoleGate 
 *     roles={['super_admin']}
 *     fallback={<Unauthorized />}
 *   >
 *     <SuperAdminPanel />
 *   </RoleGate>
 */

import { useAuth } from '@/lib/auth-context';
import React, { ReactNode } from 'react';

export interface RoleGateProps {
  /** List of roles allowed to see content */
  roles: string[];
  
  /** Component to render if user doesn't have required role (default: null) */
  fallback?: ReactNode;
  
  /** Content to render if user has required role */
  children: ReactNode;
  
  /** Optional: log access denials (default: false) */
  logDenial?: boolean;
}

/**
 * Component that gates content based on user role.
 * 
 * Features:
 * - SSR safe (checks loading state)
 * - Handles missing auth context gracefully
 * - Optional logging for denied access
 * - Type-safe role checking
 */
export function RoleGate({
  roles,
  fallback = null,
  children,
  logDenial = false,
}: RoleGateProps): ReactNode {
  const { user, hydrated } = useAuth();

  // Still loading auth state - render nothing to avoid hydration mismatch
  if (!hydrated) {
    return null;
  }

  // No user or user has no role - deny access
  if (!user) {
    if (logDenial) {
      console.warn(`[RoleGate] Access denied: no authenticated user. Required roles: ${roles.join(', ')}`);
    }
    return <>{fallback}</>;
  }

  // Check if user role is in allowed roles
  if (!roles.includes(user.role)) {
    if (logDenial) {
      console.warn(
        `[RoleGate] Access denied for role "${user.role}". Required roles: ${roles.join(', ')}`
      );
    }
    return <>{fallback}</>;
  }

  // User has required role - render content
  return <>{children}</>;
}

/**
 * Hook to check if current user has any of the specified roles.
 * Useful for conditional rendering without RoleGate component.
 * 
 * Usage:
 *   const hasAccess = useHasRole(['doctor', 'hospital_admin']);
 *   if (hasAccess) { ... }
 */
export function useHasRole(roles: string[]): boolean {
  const { user, hydrated } = useAuth();

  if (!hydrated || !user) {
    return false;
  }

  return roles.includes(user.role);
}

/**
 * Hook to check if current user is super_admin.
 * 
 * Usage:
 *   const isSuperAdmin = useIsSuperAdmin();
 *   if (isSuperAdmin) { ... }
 */
export function useIsSuperAdmin(): boolean {
  const { user, hydrated } = useAuth();

  if (!hydrated || !user) {
    return false;
  }

  return user.role === 'super_admin';
}

/**
 * Hook to check if current user is hospital_admin.
 * 
 * Usage:
 *   const isHospitalAdmin = useIsHospitalAdmin();
 */
export function useIsHospitalAdmin(): boolean {
  const { user, hydrated } = useAuth();

  if (!hydrated || !user) {
    return false;
  }

  return user.role === 'hospital_admin';
}

/**
 * Hook to check if current user is doctor.
 * 
 * Usage:
 *   const isDoctor = useIsDoctor();
 */
export function useIsDoctor(): boolean {
  const { user, hydrated } = useAuth();

  if (!hydrated || !user) {
    return false;
  }

  return user.role === 'doctor';
}

/**
 * Hook to check if current user is nurse.
 * 
 * Usage:
 *   const isNurse = useIsNurse();
 */
export function useIsNurse(): boolean {
  const { user, hydrated } = useAuth();

  if (!hydrated || !user) {
    return false;
  }

  return user.role === 'nurse';
}

/**
 * Hook to check if current user is lab_technician.
 * 
 * Usage:
 *   const isLabTech = useIsLabTech();
 */
export function useIsLabTech(): boolean {
  const { user, hydrated } = useAuth();

  if (!hydrated || !user) {
    return false;
  }

  return user.role === 'lab_technician';
}

/**
 * Hook to check if current user is receptionist.
 * 
 * Usage:
 *   const isReceptionist = useIsReceptionist();
 */
export function useIsReceptionist(): boolean {
  const { user, hydrated } = useAuth();

  if (!hydrated || !user) {
    return false;
  }

  return user.role === 'receptionist';
}

/**
 * Hook to check if current user has administrative privileges.
 * (super_admin or hospital_admin)
 * 
 * Usage:
 *   const isAdmin = useIsAdmin();
 */
export function useIsAdmin(): boolean {
  const { user, hydrated } = useAuth();

  if (!hydrated || !user) {
    return false;
  }

  return ['super_admin', 'hospital_admin'].includes(user.role);
}

/**
 * Hook to check if current user is clinical staff.
 * (doctor, nurse, lab_technician)
 * 
 * Usage:
 *   const isClinical = useIsClinical();
 */
export function useIsClinical(): boolean {
  const { user, hydrated } = useAuth();

  if (!hydrated || !user) {
    return false;
  }

  return ['doctor', 'nurse', 'lab_technician'].includes(user.role);
}
