from django.contrib import admin
from .models import MedicalRecord, Diagnosis, Prescription, LabOrder, LabResult, Vital, NursingNote


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ("patient", "record_type", "created_at", "created_by")


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ("record", "icd10_code", "icd10_description", "severity")


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("record", "drug_name", "dosage", "dispense_status")


@admin.register(LabOrder)
class LabOrderAdmin(admin.ModelAdmin):
    list_display = ("record", "test_name", "urgency", "assigned_to")


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ("record", "test_name", "status", "result_date")


@admin.register(Vital)
class VitalAdmin(admin.ModelAdmin):
    list_display = ("record", "temperature_c", "pulse_bpm", "bp_systolic")


@admin.register(NursingNote)
class NursingNoteAdmin(admin.ModelAdmin):
    list_display = ("record", "content")[:50]
