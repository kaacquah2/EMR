export type UserRole =
  | "super_admin"
  | "hospital_admin"
  | "doctor"
  | "nurse"
  | "receptionist"
  | "lab_technician"
  | "pharmacy_technician";

export type AccountStatus = "pending" | "active" | "inactive";

export interface User {
  user_id: string;
  hospital_id: string | null;
  email: string;
  role: UserRole;
  full_name: string;
  department?: string;
  department_id?: string | null;
  department_name?: string | null;
  ward_id?: string | null;
  lab_unit_id?: string | null;
  lab_unit_name?: string | null;
  account_status: AccountStatus;
  gmdc_licence_number?: string | null;
  licence_verified?: boolean;
  hospital_name?: string;
  ward_name?: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  role: UserRole;
  hospital_id: string | null;
  user_profile: User;
}

export interface Patient {
  patient_id: string;
  ghana_health_id: string;
  full_name: string;
  date_of_birth: string;
  gender: "male" | "female" | "other" | "unknown";
  blood_group: string;
  phone?: string;
  national_id?: string;
  nhis_number?: string | null;
  passport_number?: string | null;
  registered_at: string;
  allergies?: Allergy[];
  /** Set when this patient is linked to a global patient (interop). */
  global_patient_id?: string | null;
}

export interface Allergy {
  allergy_id: string;
  allergen: string;
  reaction_type: string;
  severity: "mild" | "moderate" | "severe" | "life_threatening";
  is_active: boolean;
  created_at: string;
}

export interface Diagnosis {
  diagnosis_id: string;
  record_id: string;
  icd10_code: string;
  icd10_description: string;
  severity: "mild" | "moderate" | "severe" | "critical";
  onset_date?: string;
  notes?: string;
  is_chronic: boolean;
  created_at: string;
  created_by_name?: string;
  hospital_name?: string;
}

export interface Prescription {
  prescription_id: string;
  record_id: string;
  drug_name: string;
  dosage: string;
  frequency: string;
  duration_days?: number;
  route: string;
  dispense_status: "pending" | "dispensed" | "cancelled";
  allergy_conflict?: boolean;
  created_at: string;
}

export interface LabResult {
  lab_result_id: string;
  record_id: string;
  test_name: string;
  result_value?: string;
  reference_range?: string;
  result_date: string;
  status: "pending" | "resulted" | "verified";
  created_at: string;
}

export interface Vital {
  vital_id: string;
  record_id: string;
  temperature_c?: number;
  pulse_bpm?: number;
  resp_rate?: number;
  bp_systolic?: number;
  bp_diastolic?: number;
  spo2_percent?: number;
  weight_kg?: number;
  height_cm?: number;
  bmi?: number;
  created_at: string;
}

export interface MedicalRecord {
  record_id: string;
  patient_id: string;
  hospital_id: string;
  record_type:
    | "diagnosis"
    | "prescription"
    | "lab_result"
    | "vital_signs"
    | "nursing_note"
    | "allergy";
  created_by: string;
  created_at: string;
  is_amended?: boolean;
  amended_record_id?: string;
  amendment_reason?: string;
  diagnosis?: Diagnosis;
  prescription?: Prescription;
  lab_result?: LabResult;
  vital?: Vital;
}

export interface PaginatedResponse<T> {
  data: T[];
  next_cursor?: string;
  has_more: boolean;
}

export interface ApiError {
  error: string;
  message: string;
  detail?: Record<string, unknown>;
}

// ---- Interop: global patient registry, consent, referral, break-glass ----

export type ConsentScope = "SUMMARY" | "FULL_RECORD";

export type ReferralStatus = "PENDING" | "ACCEPTED" | "REJECTED" | "COMPLETED";

export interface GlobalPatient {
  global_patient_id: string;
  national_id: string | null;
  first_name: string;
  last_name: string;
  full_name: string;
  date_of_birth: string;
  gender: string;
  blood_group: string;
  phone: string | null;
  email: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  facility_ids?: string[];
  facility_names?: string[];
}

export interface FacilityPatient {
  facility_patient_id: string;
  facility_id: string;
  facility_name: string;
  global_patient_id: string;
  local_patient_id: string;
  patient_id: string | null;
  created_at: string;
}

export interface Facility {
  facility_id: string;
  name: string;
  region: string;
  nhis_code: string;
  address?: string;
  phone?: string;
  email?: string;
  is_active?: boolean;
}

export interface ClinicalAlert {
  id: string;
  patient_id: string;
  patient_name: string;
  ghana_health_id: string;
  severity: "low" | "medium" | "high" | "critical";
  message: string;
  status: "active" | "resolved" | "dismissed";
  created_at: string;
  resolved_at: string | null;
}

export type VisitStatus =
  | "registered"
  | "waiting_triage"
  | "waiting_doctor"
  | "in_consultation"
  | "sent_to_lab"
  | "admitted"
  | "discharged";

export interface Encounter {
  id: string;
  encounter_type: string;
  encounter_date: string;
  notes: string | null;
  created_by?: string;
  assigned_department_id?: string | null;
  assigned_department_name?: string | null;
  assigned_doctor_id?: string | null;
  assigned_doctor_name?: string | null;
  status?: "waiting" | "in_consultation" | "completed";
  visit_status?: VisitStatus;
  chief_complaint?: string | null;
  hpi?: string | null;
  examination_findings?: string | null;
  assessment_plan?: string | null;
  discharge_summary?: string | null;
}

export interface EncounterDraft {
  id: string;
  encounter_id?: string | null;
  patient_id: string;
  hospital_id: string;
  draft_data: {
    patient_id: string;
    encounter_id?: string;
    soap?: {
      subjective?: string;
      objective?: string;
      assessment?: string;
      plan?: string;
    };
    [key: string]: unknown;
  };
  created_at: string;
  last_saved_at: string;
}

export interface Consent {
  consent_id: string;
  global_patient_id: string;
  granted_to_facility_id: string;
  granted_to_facility_name: string;
  granted_by_user_id: string;
  scope: ConsentScope;
  expires_at: string | null;
  is_active: boolean;
  created_at: string;
}

export interface Referral {
  referral_id: string;
  global_patient_id: string;
  from_facility_id: string;
  from_facility_name: string;
  to_facility_id: string;
  to_facility_name: string;
  reason: string;
  status: ReferralStatus;
  created_at: string;
  updated_at: string;
}

export interface BreakGlassLog {
  break_glass_id: string;
  global_patient_id: string;
  facility_id: string;
  accessed_by_user_id: string;
  reason: string;
  created_at: string;
}

export interface CrossFacilityRecordsResponse {
  demographics: GlobalPatient;
  scope: string;
  facilities: { facility_id: string; name: string }[];
  records: MedicalRecord[];
  read_only: boolean;
}

// ---- AI Async Analysis (Celery) ----

export interface AIAnalysisJob {
  job_id: string;
  patient_id: string;
  status: "pending" | "processing" | "completed" | "failed" | "cancelled";
  progress_percent: number; // 0-99 while processing, 100 when complete
  current_step: string;
  celery_task_id: string;
  created_at: string;
  updated_at: string;
}

export interface AIAnalysis {
  job_id: string;
  patient_id: string;
  analysis_type: string;
  diagnostic_insights: string;
  recommendations: string[];
  risk_factors: string[];
  created_at: string;
}

export interface AIAnalysisJobResponse extends AIAnalysisJob {
  analysis?: AIAnalysis; // Only populated when status='completed'
}

// ---- Shift Handover (SBAR) ----

export interface ShiftHandover {
  id: string;
  shift_id: string;
  outgoing_nurse_id: string;
  incoming_nurse_id: string;
  situation: string;
  background: string;
  assessment: string;
  recommendation: string;
  outgoing_signed_at: string;
  incoming_acknowledged_at: string | null;
  status: "pending" | "acknowledged";
  created_at: string;
}
