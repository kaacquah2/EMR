"""
PHASE 2-4: Comprehensive Input Validation Module

Centralizes all input validation logic for:
- Patient data (IDs, demographics)
- Medical records (diagnoses, prescriptions)
- User inputs (email, names, phone)
- Numeric fields (age, dosages, quantities)
"""

import uuid as uuid_module
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


# ============================================================================
# PHONE NUMBER VALIDATION
# ============================================================================

GHANA_PHONE_REGEX = re.compile(r'^(\+233|0)[0-9]{9}$')


def validate_phone_number(value):
    """
    Validates Ghana phone numbers.
    Format: +233XXXXXXXXX or 0XXXXXXXXX (10 digits after country/0)
    """
    if not value or not GHANA_PHONE_REGEX.match(str(value).strip()):
        raise ValidationError(
            _('Invalid phone number. Use format: +233XXXXXXXXX or 0XXXXXXXXX'),
            code='invalid_phone',
        )


# ============================================================================
# GHANA HEALTH ID VALIDATION
# ============================================================================

GHANA_HEALTH_ID_REGEX = re.compile(r'^GH-[A-Z0-9]{10}$')


def validate_ghana_health_id(value):
    """
    Validates Ghana Health ID format.
    Example: GH-1234567890
    """
    if not value:
        return  # Allow blank
    if not GHANA_HEALTH_ID_REGEX.match(str(value).strip()):
        raise ValidationError(
            _('Invalid Ghana Health ID. Format: GH-XXXXXXXXXX'),
            code='invalid_ghana_health_id',
        )


# ============================================================================
# NATIONAL ID VALIDATION
# ============================================================================

NATIONAL_ID_REGEX = re.compile(r'^[0-9]{10,13}$')


def validate_national_id(value):
    """
    Validates national ID (passport number, etc.).
    Must be 10-13 digits.
    """
    if not value:
        return  # Allow blank
    if not NATIONAL_ID_REGEX.match(str(value).strip()):
        raise ValidationError(
            _('Invalid national ID. Must be 10-13 digits.'),
            code='invalid_national_id',
        )


# ============================================================================
# NHIS NUMBER VALIDATION
# ============================================================================

NHIS_REGEX = re.compile(r'^[0-9]{10}$')


def validate_nhis_number(value):
    """
    Validates NHIS (National Health Insurance Scheme) number.
    Must be exactly 10 digits.
    """
    if not value:
        return  # Allow blank
    if not NHIS_REGEX.match(str(value).strip()):
        raise ValidationError(
            _('Invalid NHIS number. Must be 10 digits.'),
            code='invalid_nhis',
        )


# ============================================================================
# PASSPORT NUMBER VALIDATION
# ============================================================================

PASSPORT_REGEX = re.compile(r'^[A-Z]{1,2}[0-9]{6,9}$')


def validate_passport_number(value):
    """
    Validates passport number (loose validation for international formats).
    Format: 1-2 letters followed by 6-9 digits.
    """
    if not value:
        return  # Allow blank
    if not PASSPORT_REGEX.match(str(value).strip().upper()):
        raise ValidationError(
            _('Invalid passport number format.'),
            code='invalid_passport',
        )


# ============================================================================
# EMAIL VALIDATION (Extended)
# ============================================================================

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


def validate_email_format(value):
    """
    Validates email format (RFC 5322 simplified).
    """
    if not EMAIL_REGEX.match(str(value).strip().lower()):
        raise ValidationError(
            _('Invalid email format.'),
            code='invalid_email',
        )


# ============================================================================
# NAME VALIDATION
# ============================================================================

def validate_name(value, min_length=2, max_length=200):
    """
    Validates names (allows letters, spaces, hyphens, apostrophes).
    Prevents SQL injection and XSS via character restrictions.
    """
    if not value:
        raise ValidationError(_('Name cannot be empty.'), code='blank')

    value = str(value).strip()

    if len(value) < min_length:
        raise ValidationError(
            _('Name must be at least %(min)d characters.'),
            code='too_short',
            params={'min': min_length},
        )

    if len(value) > max_length:
        raise ValidationError(
            _('Name cannot exceed %(max)d characters.'),
            code='too_long',
            params={'max': max_length},
        )

    # Allow letters (any language), spaces, hyphens, apostrophes only
    if not re.match(r"^[\p{L}\s\-']+$", value, re.UNICODE):
        raise ValidationError(
            _('Name can only contain letters, spaces, hyphens, and apostrophes.'),
            code='invalid_characters',
        )


# ============================================================================
# DOSAGE VALIDATION
# ============================================================================

def validate_dosage(value):
    """
    Validates medication dosage.
    Format: number + unit (e.g., "500mg", "2 tablets", "5ml")
    """
    if not value:
        return  # Allow blank

    value = str(value).strip()

    # Pattern: number (with optional decimal) + space + unit
    pattern = r'^(\d+\.?\d*)\s*([a-zA-Z]+)$'
    if not re.match(pattern, value):
        raise ValidationError(
            _('Invalid dosage format. Use format: number + unit (e.g., "500mg")'),
            code='invalid_dosage',
        )


# ============================================================================
# ICD CODE VALIDATION (Medical Diagnosis Codes)
# ============================================================================

def validate_icd_code(value):
    """
    Validates ICD-10 diagnosis code format.
    Format: A00-Z99 (letter + two digits + optional decimal + digits)
    Example: E11.9, I10, A00.0
    """
    if not value:
        return  # Allow blank

    value = str(value).strip().upper()

    # ICD-10 pattern
    if not re.match(r'^[A-Z][0-9]{2}(\.[0-9]{1,2})?$', value):
        raise ValidationError(
            _('Invalid ICD-10 code. Format: A00-Z99 with optional decimal (e.g., E11.9)'),
            code='invalid_icd',
        )


# ============================================================================
# SAFE STRING VALIDATION (Prevents XSS/Injection)
# ============================================================================

def validate_safe_string(value, max_length=5000):
    """
    Validates that a string is safe from XSS/injection attacks.
    Allows alphanumeric, spaces, punctuation, but no HTML/script tags.
    """
    if not value:
        return

    value = str(value).strip()

    if len(value) > max_length:
        raise ValidationError(
            _('Text exceeds maximum length of %(max)d characters.'),
            code='too_long',
            params={'max': max_length},
        )

    # Detect HTML tags or script tags
    if re.search(r'<[^>]*>', value) or 'script' in value.lower():
        raise ValidationError(
            _('Text contains invalid characters or tags.'),
            code='invalid_content',
        )


# ============================================================================
# UUID VALIDATION (Database IDs)
# ============================================================================


def validate_uuid(value):
    """
    Validates UUID v4 format.
    """
    if not value:
        return

    try:
        uuid_module.UUID(str(value))
    except (ValueError, AttributeError):
        raise ValidationError(
            _('Invalid UUID format.'),
            code='invalid_uuid',
        )


# ============================================================================
# NUMERIC RANGE VALIDATION
# ============================================================================

def validate_numeric_range(value, min_value=None, max_value=None):
    """
    Validates numeric values are within acceptable range.
    Used for age, heart rate, blood pressure, etc.
    """
    if value is None:
        return

    try:
        num = float(value)
    except (ValueError, TypeError):
        raise ValidationError(
            _('Value must be numeric.'),
            code='not_numeric',
        )

    if min_value is not None and num < min_value:
        raise ValidationError(
            _('Value must be at least %(min)d.'),
            code='too_small',
            params={'min': min_value},
        )

    if max_value is not None and num > max_value:
        raise ValidationError(
            _('Value must not exceed %(max)d.'),
            code='too_large',
            params={'max': max_value},
        )


# ============================================================================
# BLOOD GROUP VALIDATION
# ============================================================================

BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']


def validate_blood_group(value):
    """
    Validates blood group is one of valid types.
    """
    if not value:
        return

    if value not in BLOOD_GROUPS:
        raise ValidationError(
            _('Invalid blood group. Must be one of: %(choices)s'),
            code='invalid_blood_group',
            params={'choices': ', '.join(BLOOD_GROUPS)},
        )


# ============================================================================
# GENDER VALIDATION
# ============================================================================

VALID_GENDERS = ['M', 'F', 'Other']


def validate_gender(value):
    """
    Validates gender field.
    """
    if not value:
        return

    if value not in VALID_GENDERS:
        raise ValidationError(
            _('Invalid gender. Must be one of: %(choices)s'),
            code='invalid_gender',
            params={'choices': ', '.join(VALID_GENDERS)},
        )


# ============================================================================
# BATCH VALIDATION (Multiple fields)
# ============================================================================

def validate_patient_demographics(data):
    """
    PHASE 2: Validates entire patient demographic object.
    Called from serializers before save.
    """
    errors = {}

    # Full name validation
    if 'full_name' in data:
        try:
            validate_name(data['full_name'])
        except ValidationError as e:
            errors['full_name'] = e

    # Phone validation
    if 'phone' in data and data['phone']:
        try:
            validate_phone_number(data['phone'])
        except ValidationError as e:
            errors['phone'] = e

    # Ghana Health ID
    if 'ghana_health_id' in data:
        try:
            validate_ghana_health_id(data['ghana_health_id'])
        except ValidationError as e:
            errors['ghana_health_id'] = e

    # National ID
    if 'national_id' in data:
        try:
            validate_national_id(data['national_id'])
        except ValidationError as e:
            errors['national_id'] = e

    # NHIS number
    if 'nhis_number' in data:
        try:
            validate_nhis_number(data['nhis_number'])
        except ValidationError as e:
            errors['nhis_number'] = e

    # Passport
    if 'passport_number' in data:
        try:
            validate_passport_number(data['passport_number'])
        except ValidationError as e:
            errors['passport_number'] = e

    # Blood group
    if 'blood_group' in data:
        try:
            validate_blood_group(data['blood_group'])
        except ValidationError as e:
            errors['blood_group'] = e

    # Gender
    if 'gender' in data:
        try:
            validate_gender(data['gender'])
        except ValidationError as e:
            errors['gender'] = e

    if errors:
        raise ValidationError(errors)


def validate_medical_record(data):
    """
    PHASE 2: Validates medical record data (diagnosis, prescription, etc.).
    """
    errors = {}

    # Diagnosis code
    if 'icd_code' in data:
        try:
            validate_icd_code(data['icd_code'])
        except ValidationError as e:
            errors['icd_code'] = e

    # Dosage
    if 'dosage' in data:
        try:
            validate_dosage(data['dosage'])
        except ValidationError as e:
            errors['dosage'] = e

    # Clinical notes
    if 'clinical_notes' in data:
        try:
            validate_safe_string(data['clinical_notes'], max_length=5000)
        except ValidationError as e:
            errors['clinical_notes'] = e

    if errors:
        raise ValidationError(errors)
