from django.contrib import admin
from .models import (
    GlobalPatient,
    FacilityPatient,
    Consent,
    Referral,
    SharedRecordAccess,
    BreakGlassLog,
    Encounter,
)


@admin.register(GlobalPatient)
class GlobalPatientAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "national_id", "date_of_birth")
    search_fields = ("first_name", "last_name", "national_id", "phone")


@admin.register(FacilityPatient)
class FacilityPatientAdmin(admin.ModelAdmin):
    list_display = ("id", "facility", "global_patient", "local_patient_id")
    list_filter = ("facility",)


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = ("id", "global_patient", "granted_to_facility", "scope", "is_active", "expires_at")
    list_filter = ("is_active", "scope")


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("id", "global_patient", "from_facility", "to_facility", "status", "created_at")
    list_filter = ("status",)


@admin.register(SharedRecordAccess)
class SharedRecordAccessAdmin(admin.ModelAdmin):
    list_display = ("id", "global_patient", "accessing_facility", "accessed_by", "scope", "created_at")
    list_filter = ("scope",)


@admin.register(BreakGlassLog)
class BreakGlassLogAdmin(admin.ModelAdmin):
    list_display = ("id", "global_patient", "facility", "accessed_by", "created_at")


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ("id", "facility_patient", "facility", "created_at")
