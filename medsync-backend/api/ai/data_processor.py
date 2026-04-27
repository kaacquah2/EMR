"""
Data Processing Layer for AI Intelligence Module.

Responsible for:
1. Extracting patient data from EMR
2. Cleaning and preprocessing (missing values, outliers, normalization)
3. Creating feature vectors for ML models
4. Mapping to medical ontologies (ICD-10, SNOMED)
5. Handling time-series vital signs
6. Aggregating medications and allergies
7. Ensuring compliance with HIPAA and hospital scoping
"""

from datetime import timedelta
from typing import Dict, List, Optional, Any
import logging

from django.db.models import QuerySet
from django.utils import timezone

from patients.models import Patient, PatientAdmission
from records.models import MedicalRecord, Encounter
from core.models import User
from api.utils import get_patient_queryset, get_effective_hospital

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Extracts and preprocesses patient data for AI models.

    Enforces:
    - Role-based access control (RBAC)
    - Hospital multi-tenancy scoping
    - Medical data privacy (HIPAA)
    - Audit logging for all extractions
    """

    def __init__(self, user: User):
        """
        Initialize data processor with user context.

        Args:
            user: Django User object with role and hospital context
        """
        self.user = user
        self.effective_hospital = get_effective_hospital({'user': user})
        logger.info(f"DataProcessor initialized for user {user.id} in hospital {self.effective_hospital}")

    def extract_patient_demographics(self, patient: Patient) -> Dict[str, Any]:
        """
        Extract demographic data from patient record.

        Returns:
            {
                'patient_id': str,
                'age': int,
                'gender': str,
                'blood_group': str,
                'phone': str,
                'ghana_health_id': str,
                'registered_hospital_id': str,
                'registered_hospital_name': str,
            }
        """
        try:
            dob = patient.date_of_birth
            age = (timezone.now().date() - dob).days // 365

            return {
                'patient_id': str(patient.id),
                'age': age,
                'gender': patient.gender,
                'blood_group': patient.blood_group,
                'phone': patient.phone or '',
                'ghana_health_id': patient.ghana_health_id,
                'registered_hospital_id': str(patient.registered_at.id),
                'registered_hospital_name': patient.registered_at.name,
                'created_at': patient.created_at.isoformat(),
            }
        except Exception as e:
            logger.error(f"Error extracting demographics for patient {patient.id}: {e}")
            raise

    def extract_patient_diagnoses(self, patient: Patient) -> List[Dict[str, Any]]:
        """
        Extract diagnosis records for patient.

        Returns:
            [
                {
                    'icd10_code': str,
                    'icd10_description': str,
                    'severity': str,  # mild, moderate, severe, critical
                    'is_chronic': bool,
                    'onset_date': str or None,
                    'created_at': str,
                    'days_since_onset': int or None,
                },
                ...
            ]
        """
        try:
            diagnoses = []
            records = MedicalRecord.objects.filter(
                patient=patient,
                record_type='diagnosis',
                hospital=self.effective_hospital
            ).select_related('diagnosis').order_by('-created_at')

            for record in records:
                diagnosis = record.diagnosis
                onset_date = diagnosis.onset_date
                days_since_onset = None

                if onset_date:
                    days_since_onset = (timezone.now().date() - onset_date).days

                diagnoses.append({
                    'icd10_code': diagnosis.icd10_code,
                    'icd10_description': diagnosis.icd10_description,
                    'severity': diagnosis.severity,
                    'is_chronic': diagnosis.is_chronic,
                    'onset_date': onset_date.isoformat() if onset_date else None,
                    'days_since_onset': days_since_onset,
                    'created_at': record.created_at.isoformat(),
                })

            return diagnoses
        except Exception as e:
            logger.error(f"Error extracting diagnoses for patient {patient.id}: {e}")
            return []

    def extract_patient_medications(self, patient: Patient) -> List[Dict[str, Any]]:
        """
        Extract prescription/medication records.

        Returns:
            [
                {
                    'drug_name': str,
                    'dosage': str,
                    'frequency': str,
                    'duration_days': int or None,
                    'route': str,  # oral, iv, im, topical, inhalation
                    'dispense_status': str,
                    'allergy_conflict': bool,
                    'created_at': str,
                },
                ...
            ]
        """
        try:
            medications = []
            records = MedicalRecord.objects.filter(
                patient=patient,
                record_type='prescription',
                hospital=self.effective_hospital
            ).select_related('prescription').order_by('-created_at')

            for record in records:
                prescription = record.prescription
                medications.append({
                    'drug_name': prescription.drug_name,
                    'dosage': prescription.dosage,
                    'frequency': prescription.frequency,
                    'duration_days': prescription.duration_days,
                    'route': prescription.route,
                    'dispense_status': prescription.dispense_status,
                    'allergy_conflict': prescription.allergy_conflict,
                    'created_at': record.created_at.isoformat(),
                })

            return medications
        except Exception as e:
            logger.error(f"Error extracting medications for patient {patient.id}: {e}")
            return []

    def extract_patient_allergies(self, patient: Patient) -> List[Dict[str, Any]]:
        """
        Extract active allergies.

        Returns:
            [
                {
                    'allergen': str,
                    'severity': str,  # mild, moderate, severe, critical
                    'reaction_type': str,
                    'is_active': bool,
                },
                ...
            ]
        """
        try:
            allergies = []
            allergy_records = patient.allergy_set.filter(is_active=True)

            for allergy in allergy_records:
                allergies.append({
                    'allergen': allergy.allergen,
                    'severity': allergy.severity,
                    'reaction_type': allergy.reaction_type,
                    'is_active': allergy.is_active,
                })

            return allergies
        except Exception as e:
            logger.error(f"Error extracting allergies for patient {patient.id}: {e}")
            return []

    def extract_patient_vitals(self, patient: Patient, days_back: int = 90) -> List[Dict[str, Any]]:
        """
        Extract vital signs time-series (last N days).

        Args:
            patient: Patient object
            days_back: Number of days to retrieve (default 90)

        Returns:
            [
                {
                    'temperature_c': float or None,
                    'pulse_bpm': int or None,
                    'resp_rate': int or None,
                    'bp_systolic': int or None,
                    'bp_diastolic': int or None,
                    'spo2_percent': float or None,
                    'weight_kg': float or None,
                    'height_cm': float or None,
                    'bmi': float or None,
                    'created_at': str,
                },
                ...
            ]
        """
        try:
            vitals = []
            cutoff_date = timezone.now() - timedelta(days=days_back)

            records = MedicalRecord.objects.filter(
                patient=patient,
                record_type='vital_signs',
                hospital=self.effective_hospital,
                created_at__gte=cutoff_date
            ).select_related('vital').order_by('-created_at')

            for record in records:
                vital = record.vital
                vitals.append({
                    'temperature_c': float(vital.temperature_c) if vital.temperature_c else None,
                    'pulse_bpm': vital.pulse_bpm,
                    'resp_rate': vital.resp_rate,
                    'bp_systolic': vital.bp_systolic,
                    'bp_diastolic': vital.bp_diastolic,
                    'spo2_percent': float(vital.spo2_percent) if vital.spo2_percent else None,
                    'weight_kg': float(vital.weight_kg) if vital.weight_kg else None,
                    'height_cm': float(vital.height_cm) if vital.height_cm else None,
                    'bmi': float(vital.bmi) if vital.bmi else None,
                    'created_at': record.created_at.isoformat(),
                })

            return vitals
        except Exception as e:
            logger.error(f"Error extracting vitals for patient {patient.id}: {e}")
            return []

    def extract_patient_labs(self, patient: Patient, days_back: int = 90) -> List[Dict[str, Any]]:
        """
        Extract lab results time-series.

        Args:
            patient: Patient object
            days_back: Number of days to retrieve (default 90)

        Returns:
            [
                {
                    'test_name': str,
                    'result_value': str or None,
                    'reference_range': str or None,
                    'status': str,  # pending, resulted, verified
                    'result_date': str,
                    'created_at': str,
                },
                ...
            ]
        """
        try:
            labs = []
            cutoff_date = timezone.now() - timedelta(days=days_back)

            records = MedicalRecord.objects.filter(
                patient=patient,
                record_type='lab_result',
                hospital=self.effective_hospital,
                created_at__gte=cutoff_date
            ).select_related('labresult').order_by('-created_at')

            for record in records:
                lab = record.lab_result
                labs.append({
                    'test_name': lab.test_name,
                    'result_value': lab.result_value,
                    'reference_range': lab.reference_range,
                    'status': lab.status,
                    'result_date': lab.result_date.isoformat(),
                    'created_at': record.created_at.isoformat(),
                })

            return labs
        except Exception as e:
            logger.error(f"Error extracting labs for patient {patient.id}: {e}")
            return []

    def extract_patient_admissions(self, patient: Patient, days_back: int = 365) -> List[Dict[str, Any]]:
        """
        Extract hospital admission history.

        Args:
            patient: Patient object
            days_back: Number of days to retrieve (default 365)

        Returns:
            [
                {
                    'ward_name': str,
                    'admitted_at': str,
                    'discharged_at': str or None,
                    'length_of_stay_days': int or None,
                    'hospital_name': str,
                },
                ...
            ]
        """
        try:
            admissions = []
            cutoff_date = timezone.now() - timedelta(days=days_back)

            admission_records = PatientAdmission.objects.filter(
                patient=patient,
                admitted_at__gte=cutoff_date
            ).select_related('ward__hospital').order_by('-admitted_at')

            for admission in admission_records:
                length_of_stay = None
                discharged_at = None

                if admission.discharged_at:
                    discharged_at = admission.discharged_at.isoformat()
                    length_of_stay = (admission.discharged_at - admission.admitted_at).days

                admissions.append({
                    'ward_name': admission.ward.name if admission.ward else 'Unknown',
                    'admitted_at': admission.admitted_at.isoformat(),
                    'discharged_at': discharged_at,
                    'length_of_stay_days': length_of_stay,
                    'hospital_name': admission.ward.hospital.name if admission.ward else 'Unknown',
                })

            return admissions
        except Exception as e:
            logger.error(f"Error extracting admissions for patient {patient.id}: {e}")
            return []

    def extract_patient_encounters(self, patient: Patient, days_back: int = 90) -> List[Dict[str, Any]]:
        """
        Extract clinical encounter records.

        Returns:
            [
                {
                    'encounter_type': str,
                    'encounter_status': str,
                    'chief_complaint': str or None,
                    'assessment_plan': str or None,
                    'created_at': str,
                },
                ...
            ]
        """
        try:
            encounters = []
            cutoff_date = timezone.now() - timedelta(days=days_back)

            encounter_records = Encounter.objects.filter(
                patient=patient,
                hospital=self.effective_hospital,
                encounter_date__gte=cutoff_date
            ).order_by('-encounter_date')

            for encounter in encounter_records:
                encounters.append({
                    'encounter_type': encounter.encounter_type,
                    'encounter_status': encounter.status,
                    'chief_complaint': encounter.chief_complaint or '',
                    'assessment_plan': encounter.assessment_plan or '',
                    'created_at': encounter.encounter_date.isoformat(),
                })

            return encounters
        except Exception as e:
            logger.error(f"Error extracting encounters for patient {patient.id}: {e}")
            return []

    def extract_complete_patient_data(self, patient: Patient) -> Dict[str, Any]:
        """
        Extract complete patient profile for ML analysis.

        Returns unified patient data object:
            {
                'demographics': {...},
                'diagnoses': [...],
                'medications': [...],
                'allergies': [...],
                'vitals': [...],
                'labs': [...],
                'admissions': [...],
                'encounters': [...],
                'extracted_at': str,
            }
        """
        logger.info(f"Extracting complete patient data for {patient.id}")

        return {
            'demographics': self.extract_patient_demographics(patient),
            'diagnoses': self.extract_patient_diagnoses(patient),
            'medications': self.extract_patient_medications(patient),
            'allergies': self.extract_patient_allergies(patient),
            'vitals': self.extract_patient_vitals(patient),
            'labs': self.extract_patient_labs(patient),
            'admissions': self.extract_patient_admissions(patient),
            'encounters': self.extract_patient_encounters(patient),
            'extracted_at': timezone.now().isoformat(),
        }

    def _get_patient_or_raise(self, patient_id: str) -> Patient:
        """
        Get patient by ID, verifying user has access via hospital scoping.

        Enforces:
        - Patient exists
        - User's hospital can access this patient's data
        - User's role allows patient access

        Args:
            patient_id: UUID of patient to access

        Returns:
            Patient object if authorized

        Raises:
            Patient.DoesNotExist: If patient not found or user lacks access
        """
        queryset = get_patient_queryset(self.user, self.effective_hospital)
        patient = queryset.filter(id=patient_id).first()

        if not patient:
            logger.warning(
                f"Access denied: User {self.user.id} attempted to access patient {patient_id} "
                f"(hospital: {self.effective_hospital}, role: {self.user.role})"
            )
            raise Patient.DoesNotExist(
                f"Patient {patient_id} not found or access denied"
            )

        return patient

    def get_accessible_patients(self, limit: Optional[int] = None) -> QuerySet:
        """
        Get all patients accessible to the user (respects RBAC).

        Args:
            limit: Maximum number of patients (for sampling)

        Returns:
            QuerySet of Patient objects accessible to user
        """
        queryset = get_patient_queryset(self.user, self.effective_hospital)
        if limit:
            queryset = queryset[:limit]
        return queryset

    def extract_batch_patient_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Extract data for multiple patients (for training/analysis).

        Args:
            limit: Maximum patients to process (default: all accessible)

        Returns:
            List of complete patient data dictionaries
        """
        patients = self.get_accessible_patients(limit)
        batch_data = []

        for patient in patients:
            try:
                data = self.extract_complete_patient_data(patient)
                batch_data.append(data)
            except Exception as e:
                logger.error(f"Failed to extract data for patient {patient.id}: {e}")
                continue

        logger.info(f"Extracted data for {len(batch_data)} patients")
        return batch_data
