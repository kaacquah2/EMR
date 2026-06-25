import hashlib
import hmac
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django_cryptography.fields import encrypt


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **kwargs):
        if not email:
            raise ValueError("Email required")
        user = self.model(email=self.normalize_email(email), **kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **kwargs):
        kwargs.setdefault("role", "super_admin")
        kwargs.setdefault("account_status", "active")
        kwargs.setdefault("full_name", "Super Admin")
        kwargs.setdefault("hospital", None)
        user = self.create_user(email, password, **kwargs)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class Hospital(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    region = models.CharField(max_length=100)
    nhis_code = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    head_of_facility = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    facility_type = models.CharField(
        max_length=50,
        choices=[
            ("CHPS", "CHPS"),
            ("HEALTH_CENTRE", "Health Centre"),
            ("DISTRICT_HOSPITAL", "District Hospital"),
            ("REGIONAL_HOSPITAL", "Regional Hospital"),
            ("TEACHING_HOSPITAL", "Teaching Hospital"),
        ],
        default="HEALTH_CENTRE",
        help_text="Ghana referral hierarchy level"
    )
    ai_enabled = models.BooleanField(default=True, help_text="Enable/disable AI features for this hospital")
    onboarded_at = models.DateTimeField(auto_now_add=True)
    onboarded_by = models.ForeignKey(
        "User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Soft-delete and archival fields
    is_archived = models.BooleanField(default=False, help_text="Soft-delete: hospital marked for archival but not hard-deleted")
    archived_at = models.DateTimeField(null=True, blank=True, help_text="When hospital was archived")
    archived_by = models.ForeignKey(
        "User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", 
        help_text="Super admin who initiated archival"
    )
    archive_reason = models.CharField(max_length=500, blank=True, help_text="Reason for archival")
    
    # PHASE 2: Device Trust & Adaptive MFA
    # List of CIDR ranges (e.g., ["192.168.1.0/24", "10.0.0.0/8"]) for hospital's network
    ip_subnets = models.JSONField(default=list, blank=True, help_text="List of CIDR ranges for hospital network (e.g., ['192.168.1.0/24'])")

    class Meta:
        indexes = [
            models.Index(fields=['is_archived', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.nhis_code})"

    def archive(self, archived_by, reason=""):
        """Soft-delete: mark hospital as archived without deleting data.
        
        This preserves all patient data and audit history while marking
        the hospital as no longer operational.
        """
        from django.utils import timezone
        from django.db import transaction
        
        with transaction.atomic():
            self.is_archived = True
            self.is_active = False
            self.archived_at = timezone.now()
            self.archived_by = archived_by
            self.archive_reason = reason
            self.save(update_fields=[
                'is_archived', 'is_active', 'archived_at', 'archived_by', 'archive_reason'
            ])
            
            # Audit log the archival
            AuditLog.log_action(
                user=archived_by,
                action="ARCHIVE_HOSPITAL",
                resource_type="Hospital",
                resource_id=str(self.id),
                hospital=self,
                extra_data={"reason": reason}
            )

    def can_delete_safely(self):
        """Check if hospital can be safely deleted (no active patients/records)."""
        from patients.models import Patient, PatientAdmission
        from records.models import MedicalRecord, Encounter
        
        active_patients = Patient.objects.filter(
            registered_at=self,
            is_archived=False
        ).exists()
        
        active_admissions = PatientAdmission.objects.filter(
            hospital=self,
            discharged_at__isnull=True
        ).exists()
        
        active_encounters = Encounter.objects.filter(
            hospital=self,
            status__in=['pending', 'in_progress', 'draft']
        ).exists()
        
        return not (active_patients or active_admissions or active_encounters)



class Ward(models.Model):
    WARD_TYPES = [
        ("general", "General"),
        ("icu", "ICU"),
        ("maternity", "Maternity"),
        ("paediatric", "Paediatric"),
        ("surgical", "Surgical"),
        ("emergency", "Emergency"),
        ("other", "Other"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    ward_name = models.CharField(max_length=120)
    ward_type = models.CharField(max_length=20, choices=WARD_TYPES, default="general")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("hospital", "ward_name")


class Bed(models.Model):
    """Bed-level tracking within a ward (for bed-level management)."""
    STATUS = [
        ("available", "Available"),
        ("occupied", "Occupied"),
        ("reserved", "Reserved"),
        ("maintenance", "Maintenance"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="beds")
    bed_code = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=STATUS, default="available")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("ward", "bed_code")


class Department(models.Model):
    """OPD, Neuro, Pediatrics, Lab, Radiology, etc. Per-hospital for routing and worklists."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("hospital", "name")


class LabUnit(models.Model):
    """Hematology, Chemistry, Microbiology, etc. Routes lab orders to the correct team."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("hospital", "name")


class User(AbstractBaseUser, PermissionsMixin):
    ROLES = [
        ("super_admin", "Super Admin"),
        ("hospital_admin", "Hospital Admin"),
        ("doctor", "Doctor"),
        ("nurse", "Nurse"),
        ("receptionist", "Receptionist"),
        ("lab_technician", "Lab Technician"),
        ("pharmacy_technician", "Pharmacy Technician"),
        ("radiology_technician", "Radiology Technician"),
        ("billing_staff", "Billing Staff"),
        ("ward_clerk", "Ward Clerk"),
    ]
    STATUS = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("suspended", "Suspended"),
        ("locked", "Locked"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.SET_NULL, null=True, blank=True)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLES)
    full_name = models.CharField(max_length=200)
    department = models.CharField(max_length=120, blank=True)
    department_link = models.ForeignKey(
        "Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="users"
    )
    ward = models.ForeignKey(Ward, null=True, blank=True, on_delete=models.SET_NULL)
    lab_unit = models.ForeignKey(
        "LabUnit", null=True, blank=True, on_delete=models.SET_NULL, related_name="technicians"
    )
    account_status = models.CharField(max_length=20, choices=STATUS, default="pending")
    invitation_token = models.CharField(max_length=128, blank=True, null=True)
    invitation_expires_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    is_mfa_enabled = models.BooleanField(default=False)
    mfa_method = models.CharField(
        max_length=20, 
        default="email", 
        choices=[("email", "Email"), ("totp", "Authenticator App"), ("passkey", "Passkey")]
    )
    totp_secret = encrypt(models.CharField(max_length=32, blank=True, null=True))
    totp_grace_period_expires = models.DateTimeField(null=True, blank=True)
    mfa_backup_codes = encrypt(models.TextField(blank=True, null=True))
    gmdc_licence_number = models.CharField(max_length=30, blank=True, null=True)
    licence_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # PHASE 1: Account Lockout (Task 3)
    failed_login_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    # PHASE 7: 3-Tier Password Recovery
    password_reset_token = models.CharField(max_length=128, blank=True, null=True)
    password_reset_expires_at = models.DateTimeField(null=True, blank=True)
    temp_password = models.CharField(max_length=128, blank=True, null=True)
    temp_password_expires_at = models.DateTimeField(null=True, blank=True)
    must_change_password_on_login = models.BooleanField(default=False)
    failed_password_reset_attempts = models.IntegerField(default=0)

    last_role_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["hospital", "role", "account_status"]),
            models.Index(fields=["role"]),
        ]

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def deactivate(self, reason="manual_deactivation"):
        """
        Deactivate user account: invalidate tokens, revoke sessions, reset MFA.
        
        Args:
            reason: Why the user was deactivated (for audit logging)
        
        This is called when:
        - Admin deactivates/suspends/locks the user
        - User is deleted (soft-delete via account_status="inactive")
        """
        from django.utils import timezone
        from django.db import transaction
        
        with transaction.atomic():
            # Mark account as inactive
            self.account_status = "inactive"
            self.save()
            
            # Invalidate MFA
            self.is_mfa_enabled = False
            self.totp_secret = None
            self.mfa_backup_codes = None
            
            # Clear all passkeys
            UserPasskey.objects.filter(user=self).delete()
            
            # Clear MFA sessions (MFASession is in same file, safe to use directly)
            MFASession.objects.filter(user=self).delete()
            
            # Blacklist all active tokens
            try:
                from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
                
                # Find all outstanding tokens for this user
                tokens = OutstandingToken.objects.filter(user=self)
                for token in tokens:
                    # Blacklist each token
                    BlacklistedToken.objects.get_or_create(token=token)
            except ImportError:
                pass
            
            # Log audit trail
            AuditLog.objects.create(
                user=self,
                action='USER_DEACTIVATED',
                resource_type='User',
                resource_id=str(self.id),
                hospital=self.hospital,
                extra_data={'reason': reason}
            )
            
            self.save()



class TrustedDevice(models.Model):
    """
    PHASE 2: Device Trust Model for adaptive MFA.
    
    Stores trusted devices for a user. A device is identified by its fingerprint:
    SHA256(user-agent + screen_resolution + timezone).
    
    On first successful MFA (email OTP) from a new device, a TrustedDevice record is created.
    On subsequent logins, if a matching device exists and is not expired, risk_tier=1 (no MFA).
    Devices auto-refresh expiry on each successful login (30-day sliding window).
    Users can revoke devices explicitly.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trusted_devices')
    
    # Device fingerprint: SHA256(user_agent + screen_resolution + timezone)
    device_fingerprint = models.CharField(max_length=64, db_index=True, help_text="SHA256 fingerprint of device")
    device_label = models.CharField(max_length=200, blank=True, help_text="Optional user-given device name (e.g., 'Main Office Desktop')")
    
    # Lifecycle
    last_verified_at = models.DateTimeField(auto_now=True, help_text="Last successful auth from this device")
    expires_at = models.DateTimeField(help_text="Device trust expires after 30 days of inactivity")
    is_active = models.BooleanField(default=True, help_text="User can revoke devices")
    
    # Metadata
    user_agent = models.TextField(blank=True, help_text="User-Agent header from device")
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="Last known IP from this device")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'device_fingerprint')
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        label = f" ({self.device_label})" if self.device_label else ""
        return f"Device for {self.user.email}{label}"
    
    def is_expired(self):
        """Check if device trust has expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    def refresh_expiry(self, days=30):
        """Refresh device expiry (called on each successful login from this device)."""
        from django.utils import timezone
        from datetime import timedelta
        self.expires_at = timezone.now() + timedelta(days=days)
        self.save(update_fields=['expires_at', 'last_verified_at'])


class StepUpSession(models.Model):
    """
    PHASE 2: Step-Up MFA Session for high-risk actions.
    
    When a user requests step-up verification (e.g., before accessing cross-facility records),
    a StepUpSession is created with:
    - An email OTP sent to the user
    - A session token valid for 5 minutes
    
    On OTP verification, a short-lived step_up_jwt is returned, scoped to an action type.
    The decorator @requires_step_up(action="...") checks for this token in the request header.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='step_up_sessions')
    
    # Session & OTP
    session_token = models.CharField(max_length=128, unique=True, help_text="Token linking request to OTP verification")
    otp_code = models.CharField(max_length=6, help_text="6-digit OTP sent to user email")
    otp_hash = models.CharField(max_length=64, help_text="SHA256 hash of OTP (never store plaintext)")
    
    # Action & verification
    action = models.CharField(
        max_length=50,
        help_text="Action type (e.g., 'cross_facility_access', 'break_glass', 'consent_grant')"
    )
    is_verified = models.BooleanField(default=False, help_text="True after OTP verification")
    verified_at = models.DateTimeField(null=True, blank=True, help_text="When OTP was verified")
    
    # Lifecycle
    expires_at = models.DateTimeField(help_text="Session expires after 5 minutes")
    attempts = models.IntegerField(default=0, help_text="Failed OTP attempts (max 3)")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'action']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        status = "verified" if self.is_verified else "pending"
        return f"StepUp {self.action} for {self.user.email} ({status})"
    
    def is_expired(self):
        """Check if session has expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    def is_rate_limited(self):
        """Check if OTP attempts exceeded (max 3 attempts)."""
        return self.attempts >= 3


class AuditLog(models.Model):
    ACTIONS = [
        ("VIEW", "View"),
        ("VIEW_PATIENT_RECORD", "View Patient Record"),
        ("VIEW_CROSS_FACILITY_RECORD", "View Cross-Facility Record"),
        ("VIEW_AUDIT_LOG", "View Audit Log"),
        ("VIEW_AS_HOSPITAL", "View As Hospital"),
        ("VIEW_VITAL_TRENDS", "View Vital Trends"),
        ("VIEW_WARD_VITALS_DASHBOARD", "View Ward Vitals Dashboard"),
        ("SEARCH_PATIENT", "Search Patient"),
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("DEACTIVATE", "Deactivate"),
        ("EXPORT", "Export"),
        ("EXPORT_DATA", "Export Data"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("LOGIN_FAILED", "Login Failed"),
        ("MFA_VERIFY", "MFA Verify"),
        ("MFA_FAILED", "MFA Failed"),
        ("MFA_ENABLED", "MFA Enabled"),
        ("MFA_DISABLED", "MFA Disabled"),
        ("PASSWORD_RESET_REQUEST", "Password Reset Requested"),
        ("PASSWORD_RESET", "Password Reset Completed"),
        ("PASSWORD_RESET_FAILED", "Password Reset Failed"),
        ("FORCE_PASSWORD_RESET_INITIATED", "Force Password Reset Initiated"),
        ("ROLE_CHANGE", "Role Change"),
        ("HOSPITAL_CHANGE", "Hospital Assignment Changed"),
        ("INVITE_SENT", "Invite Sent"),
        ("ACCOUNT_ACTIVATED", "Account Activated"),
        ("ACCOUNT_LOCKED", "Account Locked"),
        ("ACCOUNT_UNLOCKED", "Account Unlocked"),
        ("EMERGENCY_ACCESS", "Emergency Access"),
        ("BREAK_GLASS_ACCESS", "Break Glass Access"),
        ("BREAK_GLASS_ABUSE_DETECTED", "Break Glass Abuse Detected"),
        ("BREAK_GLASS_EXPIRED_ACCESS", "Break Glass Expired Access"),
        ("ANOMALY_DETECTED", "Anomaly Detected"),
        ("CROSS_FACILITY_ACCESS_REVOKED", "Cross-Facility Access Revoked"),
        ("CROSS_FACILITY_ACCESS", "Cross-Facility Access"),
        ("BULK_IMPORT", "Bulk Import"),
        ("CONSENT_REVOKED", "Consent Revoked"),
        ("NO_SHOW_AUTO_MARKED", "No-show Auto Marked"),
        ("NO_SHOW_OVERRIDE", "No-show Override"),
        ("SEND_REMINDER", "Send Reminder"),
        ("HANDOVER_SUBMITTED", "Handover Submitted"),
        ("HANDOVER_ACKNOWLEDGED", "Handover Acknowledged"),
        ("TRIAGE_ASSIGN", "Triage Assign"),
        ("ED_ROOM_ASSIGN", "ED Room Assign"),
        ("ESCALATE_ALERT", "Escalate Alert"),
        ("ACKNOWLEDGE_CDS_ALERT", "Acknowledge CDS Alert"),
        ("MEDICATION_ADMINISTERED", "Medication Administered"),
        ("MEDICATION_HELD", "Medication Held"),
        ("MEDICATION_DISPENSE", "Medication Dispense"),
        ("DISPENSE_MEDICATION", "Dispense Medication"),
        ("DISPENSE_PRESCRIPTION", "Dispense Prescription"),
        ("ADD_DRUG_STOCK", "Add Drug Stock"),
        ("ADJUST_STOCK", "Adjust Stock"),
        ("NHIS_CLAIM_SUBMIT", "NHIS Claim Submit"),
        ("INVOICE_CREATE", "Invoice Create"),
        ("PAYMENT_RECORD", "Payment Record"),
        ("REFERRAL_ACCEPTED", "Referral Accepted"),
        ("REFERRAL_REJECTED", "Referral Rejected"),
        ("REFERRAL_COMPLETED", "Referral Completed"),
        ("permission_denied", "Permission Denied"),
        ("PUSH_SUBSCRIBE", "Push Subscribe"),
        ("PUSH_RESUBSCRIBE", "Push Resubscribe"),
        ("PUSH_UNSUBSCRIBE", "Push Unsubscribe"),
        ("ARCHIVE_HOSPITAL", "Archive Hospital"),
        ("PASSKEY_REGISTERED", "Passkey Registered"),
        ("PASSKEY_RENAMED", "Passkey Renamed"),
        ("PASSKEY_REMOVED", "Passkey Removed"),
        ("PASSKEY_AUTH_SUCCESS", "Passkey Authentication Success"),
        ("PASSKEY_RESET_BY_ADMIN", "Passkey Reset by Admin"),
        ("USER_CREATED", "User Created"),
        ("USER_DEACTIVATED", "User Deactivated"),
        ("USER_REACTIVATED", "User Reactivated"),
        ("HOSPITAL_CREATED", "Hospital Created"),
        ("HOSPITAL_UPDATED", "Hospital Updated"),
        ("RATE_LIMIT_HIT", "Rate Limit Exceeded"),
        ("PERMISSION_DENIED", "Permission Denied"),
        ("FAILED_OBJECT_ACCESS", "Object Access Denied"),
        ("SUSPICIOUS_ACTIVITY", "Suspicious Activity Detected"),
        ("ERROR", "Application Error"),
        ("AI_ANALYSIS", "AI Analysis"),
        ("AI_ANALYSIS_FAILED", "AI Analysis Failed"),
        ("AI_ANALYSIS_START_ASYNC", "AI Analysis Start Async"),
        ("AI_FEATURE_BLOCKED", "AI Feature Blocked"),
        ("AI_SUGGESTION_IGNORED", "AI Suggestion Ignored"),
        ("AI_RISK_PREDICTION", "AI Risk Prediction"),
        ("AI_CDS", "AI CDS"),
        ("AI_TRIAGE", "AI Triage"),
        ("AI_SIMILARITY_SEARCH", "AI Similarity Search"),
        ("AI_REFERRAL_RECOMMENDATION", "AI Referral Recommendation"),
        ("AI_HISTORY_VIEW", "AI History View"),
        ("AI_ANTIBIOTIC_GUIDANCE", "AI Antibiotic Guidance"),
        ("AI_APPROVAL_GRANT", "AI Approval Grant"),
        ("AI_APPROVAL_REVOKE", "AI Approval Revoke"),
        ("AI_DEPLOYMENT_ENABLED", "AI Deployment Enabled"),
        ("AI_DEPLOYMENT_DISABLED", "AI Deployment Disabled"),
        ("AI_DRIFT_WARNING", "AI Drift Warning"),
        ("AI_DRIFT_CRITICAL", "AI Drift Critical"),
        ("DATA_RESIDENCY_DENIED", "Data Residency Access Denied"),
    ]
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=50, choices=ACTIONS)
    resource_type = models.CharField(max_length=50, blank=True, null=True)
    resource_id = models.CharField(max_length=64, null=True, blank=True)
    hospital = models.ForeignKey(Hospital, null=True, blank=True, on_delete=models.SET_NULL)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    extra_data = models.JSONField(null=True, blank=True)
    chain_hash = models.CharField(max_length=64, editable=False, unique=True)
    signature = models.CharField(max_length=64, editable=False, default="")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # PHASE 2: Adaptive MFA context
    # Risk tier (1=trusted, 2=MFA required, 3=step-up required) — for NIST AAL context
    risk_tier = models.IntegerField(
        choices=[(1, "AAL1: Trusted"), (2, "AAL2: MFA"), (3, "AAL3: Step-Up")],
        null=True,
        blank=True,
        help_text="Authentication Assurance Level: 1=no MFA, 2=email OTP, 3=step-up required"
    )
    # MFA method used (none, email_otp, step_up, totp) — audit context for authentication events
    mfa_method = models.CharField(
        max_length=20,
        choices=[
            ("none", "None"),
            ("email_otp", "Email OTP"),
            ("step_up", "Step-Up MFA"),
            ("totp", "TOTP Authenticator"),
        ],
        null=True,
        blank=True,
        help_text="Authentication factor method used for this action"
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            prev = (
                AuditLog.objects.filter(user=self.user)
                .order_by("-timestamp")
                .first()
            )
            prev_hash = prev.chain_hash if prev else "0"
            data = f"{prev_hash}{self.user_id}{self.action}{self.resource_type or ''}{self.resource_id or ''}"

            # Tamper-evident chain hash
            self.chain_hash = hashlib.sha256(data.encode()).hexdigest()

            # HMAC signature for authenticity
            from django.conf import settings

            key = getattr(settings, "AUDIT_LOG_SIGNING_KEY", None) or "dev-key-change-in-production"
            self.signature = hmac.new(
                key.encode("utf-8"),
                data.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        super().save(*args, **kwargs)

    @classmethod
    def log_action(cls, user, action, resource_type=None, resource_id=None, hospital=None, request=None, extra_data=None, risk_tier=None, mfa_method=None):
        """
        Create a chained audit log entry with tamper-evident chain hashing.
        
        Args:
            risk_tier (int): NIST AAL level (1=trusted, 2=MFA, 3=step-up)
            mfa_method (str): Authentication method used (none, email_otp, step_up, totp)
        """
        from api.utils import sanitize_audit_resource_id, get_client_ip
        
        resource_id = sanitize_audit_resource_id(resource_id)
        ip = get_client_ip(request) if request else "127.0.0.1"
        if ip == "unknown":
            ip = "0.0.0.0"
        ua = (request.META.get("HTTP_USER_AGENT") or "") if request else ""
        
        if not hospital and user and hasattr(user, 'hospital'):
            hospital = user.hospital
            
        return cls.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            hospital=hospital,
            ip_address=ip,
            user_agent=ua,
            extra_data=extra_data,
            risk_tier=risk_tier,
            mfa_method=mfa_method,
        )

    class Meta:
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["hospital", "-timestamp"]),
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["action", "hospital", "-timestamp"]),
            models.Index(fields=['resource_type', 'resource_id'], name='audit_resource_idx'),
        ]


class UserPasswordHistory(models.Model):
    """Stores last N password hashes per user to enforce no-reuse policy."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_history")
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class MFASession(models.Model):
    """
    PHASE 1: MFA Session Persistence (Task 5)
    Persists MFA sessions in the database instead of cache to survive service restarts.
    Includes rate limiting to prevent brute-force attacks on MFA codes.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_sessions")
    token = models.CharField(max_length=128, unique=True, db_index=True)
    failed_attempts = models.IntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    # SHA-256 hex of 6-digit email OTP; null when MFA uses authenticator (dev seed accounts only).
    email_otp_hash = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "MFA Session"
        verbose_name_plural = "MFA Sessions"

    def __str__(self):
        return f"MFA Session for {self.user.email}"


class MFAFailure(models.Model):
    """
    PHASE 1: MFA Rate Limiting (CRITICAL FIX #3)
    Tracks failed MFA attempts across all sessions to prevent brute-force attacks.
    User-level rate limiting: 10 failed attempts in 1 hour = account lockout.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_failures")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]
        verbose_name = "MFA Failure"
        verbose_name_plural = "MFA Failures"
    
    def __str__(self):
        return f"MFA Failure: {self.user.email} at {self.created_at}"


class SuperAdminHospitalAccess(models.Model):
    """
    ⚠️  SECURITY: Tracks which hospitals each super_admin can access via X-View-As-Hospital header.
    Prevents privilege escalation if a super_admin account is compromised.
    """
    super_admin = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="hospital_access",
        limit_choices_to={"role": "super_admin"},
    )
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    granted_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    granted_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", 
        help_text="Who granted this access (another super_admin or system)"
    )

    class Meta:
        unique_together = ("super_admin", "hospital")
        verbose_name_plural = "Super Admin Hospital Access"

    def __str__(self):
        return f"{self.super_admin.email} -> {self.hospital.name}"


class PasswordResetAudit(models.Model):
    """PHASE 7: 3-Tier Password Recovery - Audit trail for all password resets."""
    RESET_TYPES = [
        ("self_service", "User Self-Service"),
        ("admin_link", "Admin-Generated Reset Link"),
        ("temp_password", "Admin-Generated Temp Password"),
        ("super_admin_override", "Super Admin Override"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("expired", "Expired"),
        ("failed", "Failed"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="password_resets")
    reset_type = models.CharField(max_length=20, choices=RESET_TYPES)
    initiated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="password_resets_initiated",
        help_text="Admin or super admin who initiated (null for self-service)"
    )
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reason = models.TextField(blank=True, null=True, help_text="Why reset was initiated (for admin/super-admin resets)")
    
    # Token tracking and lifecycle timestamps
    token_issued_at = models.DateTimeField(auto_now_add=True)
    token_expires_at = models.DateTimeField()
    token_used_at = models.DateTimeField(null=True, blank=True)
    link_clicked_at = models.DateTimeField(null=True, blank=True)
    reset_completed_at = models.DateTimeField(null=True, blank=True)
    failed_validation_attempts = models.IntegerField(default=0)
    
    # Request context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    mfa_verified = models.BooleanField(default=False, help_text="For super admin only")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    failure_reason = models.TextField(blank=True, null=True, help_text="Reason if status=failed")
    
    class Meta:
        indexes = [
            models.Index(fields=["user", "-token_issued_at"]),
            models.Index(fields=["hospital", "-token_issued_at"]),
            models.Index(fields=["status"]),
        ]
        ordering = ["-token_issued_at"]
    
    def __str__(self):
        return f"{self.user.email} - {self.get_reset_type_display()} - {self.get_status_display()}"


class PasswordResetAttempt(models.Model):
    """
    HIGH-5 FIX: Database-backed rate limiting for password reset email requests.
    
    Tracks password reset attempts per email to prevent brute-force attacks.
    If more than 10 requests are made for the same email within 15 minutes,
    subsequent requests are rejected with HTTP 429.
    """
    email = models.EmailField(db_index=True)
    attempted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['email', '-attempted_at']),
        ]
        ordering = ['-attempted_at']
    
    def __str__(self):
        return f"{self.email} at {self.attempted_at}"
    
    @staticmethod
    def check_and_record(email, max_attempts=10, window_minutes=15, ip_address=None):
        """
        Check if email has exceeded rate limit for password resets.
        
        Returns:
            tuple: (allowed: bool, remaining_attempts: int)
            
        If allowed=True, records the attempt and returns remaining slots.
        If allowed=False, does not record (attacker doesn't increment).
        """
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Count recent attempts for this email
        attempt_count = PasswordResetAttempt.objects.filter(
            email__iexact=email,
            attempted_at__gte=window_start,
        ).count()
        
        if attempt_count >= max_attempts:
            return False, 0
        
        # Record this attempt
        PasswordResetAttempt.objects.create(
            email=email.lower(),
            ip_address=ip_address,
        )
        
        remaining = max_attempts - attempt_count - 1
        return True, remaining


class BackupCodeRateLimit(models.Model):
    """
    MEDIUM-1 FIX: Database-backed rate limiting for backup code attempts.
    
    Tracks backup code verification attempts per user with automatic cleanup.
    Replaces cache-based throttling which can be lost on service restart.
    
    Rate limit: 2 attempts per 5 minutes per user.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="backup_code_attempts")
    attempt_count = models.IntegerField(default=0)
    first_attempt_at = models.DateTimeField(auto_now_add=True)
    last_attempt_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["user", "-last_attempt_at"]),
        ]
        verbose_name = "Backup Code Rate Limit"
        verbose_name_plural = "Backup Code Rate Limits"
    
    def __str__(self):
        return f"{self.user.email} - {self.attempt_count} attempts"
    
    @classmethod
    def check_and_record(cls, user, max_attempts=2, window_minutes=5):
        """
        Check if user has exceeded backup code attempt limit.
        
        Returns:
            (allowed: bool, remaining: int)
            
        SECURITY: Uses atomic F() expressions to prevent race conditions where
        concurrent requests could both increment counter without seeing each other's
        updates, allowing more attempts than the limit.
        """
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import F
        
        now = timezone.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Get or create rate limit record
        rate_limit, created = cls.objects.get_or_create(user=user)
        
        # Clean up old attempts (older than window)
        if rate_limit.first_attempt_at < window_start:
            rate_limit.attempt_count = 0
            rate_limit.first_attempt_at = now
            rate_limit.save(update_fields=['attempt_count', 'first_attempt_at'])
        
        # Check if limit exceeded
        if rate_limit.attempt_count >= max_attempts:
            return False, 0
        
        # CRITICAL FIX: Use atomic F() expression to prevent race condition
        # Two concurrent requests will not both increment and bypass the limit
        cls.objects.filter(id=rate_limit.id).update(
            attempt_count=F('attempt_count') + 1,
            last_attempt_at=now
        )
        
        # Refresh to get the updated count
        rate_limit.refresh_from_db()
        remaining = max_attempts - rate_limit.attempt_count
        return True, remaining


class Announcement(models.Model):
    """
    Hospital-wide announcement broadcast.
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    TARGET_CHOICES = [
        ('all', 'All Staff'),
        ('doctors', 'Doctors Only'),
        ('nurses', 'Nurses Only'),
        ('clinical', 'Clinical Staff'),
        ('admin', 'Admin Staff'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey('Hospital', on_delete=models.CASCADE)
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    target_audience = models.CharField(max_length=20, choices=TARGET_CHOICES, default='all')
    
    created_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True)
    
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.hospital.name}"


class UserPasskey(models.Model):
    """
    WebAuthn/Passkey credential storage per user.
    Stores public key information needed to verify passkey signatures during authentication.
    Includes platform detection for multi-device support (desktop, mobile).
    
    Fields:
    - credential_id: Unique WebAuthn credential identifier (binary)
    - public_key: Public key bytes for signature verification
    - sign_count: Counter to detect replayed assertions (must increase monotonically)
    - device_name: User-friendly device identifier (e.g. "iPhone 15", "Ward Tablet")
    - platform: Detected OS (windows, macos, linux, android, ios, unknown)
    - transports: JSON array of transports (e.g. ["internal"], ["hybrid"], etc.)
    - last_ip_address: IP address when passkey was last used
    - is_synced: True if passkey synced across devices (Apple/Google/Microsoft)
    - created_at: When the passkey was registered
    - last_used_at: When the passkey was last used successfully for authentication
    """
    PLATFORM_CHOICES = [
        ('windows', 'Windows'),
        ('macos', 'macOS'),
        ('linux', 'Linux'),
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('unknown', 'Unknown'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='passkeys')
    
    credential_id = models.BinaryField(unique=True, db_index=True)
    public_key = models.BinaryField()
    sign_count = models.IntegerField(default=0)
    
    device_name = models.CharField(max_length=100, blank=True, default='')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='unknown')
    transports = models.JSONField(default=list, blank=True)
    last_ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_synced = models.BooleanField(default=False, help_text="True if synced via Apple/Google/Microsoft")
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'credential_id']),
            models.Index(fields=['user', '-last_used_at']),
            models.Index(fields=['user', 'platform']),
        ]
        verbose_name = "User Passkey"
        verbose_name_plural = "User Passkeys"
    
    def __str__(self):
        return f"Passkey for {self.user.email} ({self.device_name or 'Unknown device'}) - {self.get_platform_display()}"


class ClientCookie(models.Model):
    """
    PHASE 3: HttpOnly Cookie Session Tracking
    
    Server-side tracking of HTTP-only session cookies to enable:
    - Immediate token revocation (cookies can be revoked without client knowledge)
    - Encrypted JWT storage (JWTs stored server-side, not in cookie value)
    - Device/IP context for security auditing
    - Transparent session invalidation on logout
    
    The medsync_session cookie contains an opaque, random token. The actual JWT
    is stored encrypted in this model. On each request, we decrypt the JWT and
    validate it.
    
    Rationale: Replaces sessionStorage token storage (XSS-vulnerable) with
    HttpOnly SameSite=Strict cookies + server-side JWT encryption.
    
    Fields:
    - user: FK to User who owns this session
    - cookie_token: SHA256 hash of the cookie value sent to browser
    - access_token_jwt: Encrypted access JWT (15-minute TTL)
    - refresh_token_jwt: Encrypted refresh JWT (7-day TTL)
    - device_fingerprint: SHA256 of user-agent + screen resolution + timezone
    - client_metadata: JSON dict with user-agent, IP address, device name
    - created_at: When session was created (login time)
    - expires_at: When access token expires (15 minutes from login/refresh)
    - last_used_at: Last time this cookie was used (auto-updated)
    - is_revoked: Soft-delete flag for immediate revocation (logout)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_cookies')
    
    # Opaque cookie token (SHA256 hash; never contains JWT directly)
    cookie_token = models.CharField(max_length=255, unique=True, db_index=True)
    
    # Encrypted JWTs stored server-side
    access_token_jwt = models.TextField()  # Encrypted JSON-serialized access token
    refresh_token_jwt = models.TextField()  # Encrypted JSON-serialized refresh token
    
    # Device tracking and context
    device_fingerprint = models.CharField(max_length=256, null=True, blank=True)
    client_metadata = models.JSONField(default=dict)  # { "user_agent": "...", "ip_addr": "...", "device_name": "..." }
    
    # Lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # When access token expires (15 min)
    last_used_at = models.DateTimeField(auto_now=True)
    is_revoked = models.BooleanField(default=False, db_index=True)  # Soft-delete on logout
    
    class Meta:
       indexes = [
           models.Index(fields=['user', 'is_revoked']),
           models.Index(fields=['cookie_token', 'is_revoked']),
           models.Index(fields=['expires_at']),  # For cleanup/expiry queries
           models.Index(fields=['-created_at']),
       ]
       verbose_name = "Client Cookie Session"
       verbose_name_plural = "Client Cookie Sessions"
       ordering = ['-created_at']
    
    def __str__(self):
       return f"Session for {self.user.email} (expires: {self.expires_at}, revoked: {self.is_revoked})"
    
    @property
    def is_expired(self):
       """Check if session has expired."""
       from django.utils import timezone
       return timezone.now() > self.expires_at

