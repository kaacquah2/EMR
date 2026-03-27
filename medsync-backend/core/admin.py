from django.contrib import admin
from .models import Hospital, Ward, Bed, User, AuditLog


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "nhis_code", "is_active")


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ("ward_name", "hospital", "ward_type")


@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ("bed_code", "ward", "status", "is_active")
    list_filter = ("status", "ward__hospital")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "full_name", "role", "hospital", "account_status")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "resource_type", "timestamp")
