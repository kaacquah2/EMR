// ============================================================================
// MedSync EMR — Single source of truth for role strings
// All frontend role checks MUST import from this file.
// Matching backend constants live in shared/constants.py
// ============================================================================

/** Every valid role in the system. */
export const ROLES = {
  SUPER_ADMIN:          "super_admin",
  HOSPITAL_ADMIN:       "hospital_admin",
  DOCTOR:               "doctor",
  NURSE:                "nurse",
  RECEPTIONIST:         "receptionist",
  LAB_TECHNICIAN:       "lab_technician",
  PHARMACY_TECHNICIAN:  "pharmacy_technician",
  RADIOLOGY_TECHNICIAN: "radiology_technician",
  BILLING_STAFF:        "billing_staff",
  WARD_CLERK:           "ward_clerk",
} as const;

export type Role = (typeof ROLES)[keyof typeof ROLES];

// ---------------------------------------------------------------------------
// Role sets — use these instead of inline arrays
// ---------------------------------------------------------------------------

/** hospital_admin + super_admin */
export const ADMIN_ROLES: readonly Role[] = [ROLES.HOSPITAL_ADMIN, ROLES.SUPER_ADMIN];

/** Clinical staff who can interact with patient records */
export const CLINICAL_ROLES: readonly Role[] = [ROLES.DOCTOR, ROLES.NURSE];

/** Roles that can write clinical records */
export const RECORD_CREATE_ROLES: readonly Role[] = [ROLES.DOCTOR, ROLES.NURSE, ROLES.SUPER_ADMIN];

/** Roles that can amend existing records */
export const RECORD_AMEND_ROLES: readonly Role[] = [ROLES.DOCTOR, ROLES.SUPER_ADMIN];

/** Roles that can register new patients */
export const REGISTER_PATIENT_ROLES: readonly Role[] = [
  ROLES.RECEPTIONIST,
  ROLES.HOSPITAL_ADMIN,
  ROLES.SUPER_ADMIN,
];

/** Roles that can assign ED rooms */
export const ROOM_ASSIGN_ROLES: readonly Role[] = [
  ROLES.NURSE,
  ROLES.HOSPITAL_ADMIN,
  ROLES.SUPER_ADMIN,
];

/** Roles that can view the emergency queue */
export const EMERGENCY_QUEUE_ROLES: readonly Role[] = [
  ROLES.DOCTOR,
  ROLES.NURSE,
  ROLES.RECEPTIONIST,
  ROLES.HOSPITAL_ADMIN,
  ROLES.SUPER_ADMIN,
];

/** Roles that can triage patients */
export const TRIAGE_ROLES: readonly Role[] = [ROLES.DOCTOR, ROLES.NURSE];

/** Roles that can dispense medications */
export const DISPENSE_ROLES: readonly Role[] = [
  ROLES.NURSE,
  ROLES.PHARMACY_TECHNICIAN,
  ROLES.SUPER_ADMIN,
];

/** Roles that can manage patients (start consultations, add encounters) */
export const ENCOUNTER_CREATE_ROLES: readonly Role[] = [
  ROLES.DOCTOR,
  ROLES.HOSPITAL_ADMIN,
  ROLES.SUPER_ADMIN,
];

/** Roles with access to admin features */
export const ALL_ADMIN_ROLES: readonly Role[] = [ROLES.HOSPITAL_ADMIN, ROLES.SUPER_ADMIN];

/** Roles that can view analytics */
export const ANALYTICS_ROLES: readonly Role[] = [ROLES.HOSPITAL_ADMIN, ROLES.SUPER_ADMIN];

/** Roles that can view/work the patient search */
export const PATIENT_SEARCH_ROLES: readonly Role[] = [
  ROLES.DOCTOR,
  ROLES.NURSE,
  ROLES.RECEPTIONIST,
  ROLES.LAB_TECHNICIAN,
  ROLES.PHARMACY_TECHNICIAN,
  ROLES.RADIOLOGY_TECHNICIAN,
  ROLES.BILLING_STAFF,
  ROLES.WARD_CLERK,
  ROLES.HOSPITAL_ADMIN,
  ROLES.SUPER_ADMIN,
];

// ---------------------------------------------------------------------------
// Legacy helper (keep for backward compat with existing alert code)
// ---------------------------------------------------------------------------
export const ALERT_RESOLVE_ROLES: readonly Role[] = [ROLES.DOCTOR, ROLES.NURSE];

export function canResolveAlerts(role: string | null | undefined): boolean {
  if (!role) return false;
  return (ALERT_RESOLVE_ROLES as readonly string[]).includes(role);
}

// ---------------------------------------------------------------------------
// Type guards
// ---------------------------------------------------------------------------
export function isValidRole(role: string): role is Role {
  return Object.values(ROLES).includes(role as Role);
}

export function hasRole(userRole: string | null | undefined, allowed: readonly string[]): boolean {
  if (!userRole) return false;
  return (allowed as readonly string[]).includes(userRole);
}
