from django.contrib import admin
from .models import Patient, Allergy, PatientAdmission


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("ghana_health_id", "full_name", "date_of_birth", "blood_group")


@admin.register(Allergy)
class AllergyAdmin(admin.ModelAdmin):
    list_display = ("patient", "allergen", "severity", "is_active")


@admin.register(PatientAdmission)
class PatientAdmissionAdmin(admin.ModelAdmin):
    list_display = ("patient", "ward", "admitted_at", "discharged_at")
