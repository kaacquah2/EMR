import hashlib
import hmac
import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


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
    onboarded_at = models.DateTimeField(auto_now_add=True)
    onboarded_by = models.ForeignKey(
        "User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )


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
        ("pharmacist", "Pharmacist"),
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
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, null=True, blank=True)
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
    totp_secret = models.CharField(max_length=32, blank=True, null=True)
    mfa_backup_codes = models.TextField(blank=True, null=True)
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

    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class AuditLog(models.Model):
    ACTIONS = [
        ("VIEW", "View"),
        ("VIEW_PATIENT_RECORD", "View Patient Record"),
        ("VIEW_CROSS_FACILITY_RECORD", "View Cross-Facility Record"),
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DEACTIVATE", "Deactivate"),
        ("EXPORT", "Export"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
        ("LOGIN_FAILED", "Login Failed"),
        ("ROLE_CHANGE", "Role Change"),
        ("INVITE_SENT", "Invite Sent"),
        ("ACCOUNT_ACTIVATED", "Account Activated"),
        ("EMERGENCY_ACCESS", "Emergency Access"),
        ("CROSS_FACILITY_ACCESS_REVOKED", "Cross-Facility Access Revoked"),
        ("BULK_IMPORT", "Bulk Import"),
        ("VIEW_AS_HOSPITAL", "View As Hospital"),
        ("permission_denied", "Permission Denied"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=30, choices=ACTIONS)
    resource_type = models.CharField(max_length=50, blank=True, null=True)
    resource_id = models.CharField(max_length=64, null=True, blank=True)
    hospital = models.ForeignKey(Hospital, null=True, blank=True, on_delete=models.SET_NULL)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, null=True)
    extra_data = models.JSONField(null=True, blank=True)
    chain_hash = models.CharField(max_length=64, editable=False)
    signature = models.CharField(max_length=64, editable=False, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

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

            key = getattr(settings, "AUDIT_LOG_SIGNING_KEY", "dev-key-change-in-production").encode()
            self.signature = hmac.new(key, data.encode(), hashlib.sha256).hexdigest()
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["hospital", "-timestamp"]),
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["action", "hospital", "-timestamp"]),
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_resets")
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
        """
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        window_start = now - timedelta(minutes=window_minutes)
        
        # Get or create rate limit record
        rate_limit, created = cls.objects.get_or_create(user=user)
        
        # Clean up old attempts (older than window)
        if rate_limit.first_attempt_at < window_start:
            rate_limit.attempt_count = 0
            rate_limit.first_attempt_at = now
        
        # Check if limit exceeded
        if rate_limit.attempt_count >= max_attempts:
            return False, 0
        
        # Increment attempt counter
        rate_limit.attempt_count += 1
        rate_limit.last_attempt_at = now
        rate_limit.save()
        
        remaining = max_attempts - rate_limit.attempt_count
        return True, remaining


class TaskSubmission(models.Model):
    """
    Tracks Celery task submissions to enable permission checks and audit logging.
    Allows users to view only their own task status and results.
    """
    TASK_TYPES = [
        ("export_pdf", "PDF Export"),
        ("ai_analysis", "AI Analysis"),
        ("risk_prediction", "Risk Prediction"),
        ("mark_no_shows", "Mark No Shows"),
        ("other", "Other"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    celery_task_id = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="task_submissions")
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, null=True, blank=True)
    task_type = models.CharField(max_length=20, choices=TASK_TYPES, default="other")
    
    # Task context
    resource_type = models.CharField(max_length=50, blank=True, null=True)  # e.g. "patient", "encounter"
    resource_id = models.CharField(max_length=100, blank=True, null=True)  # UUID of the resource
    
    # Lifecycle
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)  # When task result expires (1 hour by default)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["user", "-submitted_at"]),
            models.Index(fields=["hospital", "-submitted_at"]),
            models.Index(fields=["task_type", "-submitted_at"]),
            models.Index(fields=["-expires_at"]),  # For cleanup queries
        ]
        ordering = ["-submitted_at"]
    
    def __str__(self):
        return f"{self.task_type} - {self.user.email} - {self.celery_task_id}"
