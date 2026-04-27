"""
Shared pytest fixtures for all API tests.
Provides standardized setup for users, hospitals, and common test data.

Usage:
    from api.tests.conftest import hospital_a, doctor_a, patient_a
    
    def test_something(hospital_a, doctor_a):
        assert doctor_a.hospital_id == hospital_a.id
"""

import pytest
from django.utils import timezone
from core.models import User, Hospital, Ward
from patients.models import Patient
from records.models import Encounter


# ============================================================================
# HOSPITALS
# ============================================================================

@pytest.fixture
def hospital_a(db):
    """Create Hospital A for testing."""
    return Hospital.objects.create(
        name="Hospital A",
        region="Region A",
        nhis_code="HA_TEST_001",
        is_active=True,
    )


@pytest.fixture
def hospital_b(db):
    """Create Hospital B for testing."""
    return Hospital.objects.create(
        name="Hospital B",
        region="Region B",
        nhis_code="HB_TEST_001",
        is_active=True,
    )


# ============================================================================
# WARDS
# ============================================================================

@pytest.fixture
def ward_a1(db, hospital_a):
    """Create Ward A1 in Hospital A."""
    return Ward.objects.create(
        hospital=hospital_a,
        ward_name="Ward A1",
        ward_code="WA1",
        is_active=True,
    )


@pytest.fixture
def ward_a2(db, hospital_a):
    """Create Ward A2 in Hospital A."""
    return Ward.objects.create(
        hospital=hospital_a,
        ward_name="Ward A2",
        ward_code="WA2",
        is_active=True,
    )


@pytest.fixture
def ward_b1(db, hospital_b):
    """Create Ward B1 in Hospital B."""
    return Ward.objects.create(
        hospital=hospital_b,
        ward_name="Ward B1",
        ward_code="WB1",
        is_active=True,
    )


# ============================================================================
# USERS - HOSPITAL A
# ============================================================================

@pytest.fixture
def doctor_a(db, hospital_a):
    """Create Doctor user in Hospital A."""
    return User.objects.create_user(
        email="doctor_a@test.medsync.gh",
        password="SecurePass123!@#",
        role="doctor",
        hospital=hospital_a,
        account_status="active",
    )


@pytest.fixture
def doctor_a2(db, hospital_a):
    """Create second Doctor user in Hospital A."""
    return User.objects.create_user(
        email="doctor_a2@test.medsync.gh",
        password="SecurePass123!@#",
        role="doctor",
        hospital=hospital_a,
        account_status="active",
    )


@pytest.fixture
def nurse_a(db, hospital_a, ward_a1):
    """Create Nurse user in Hospital A assigned to Ward A1."""
    user = User.objects.create_user(
        email="nurse_a@test.medsync.gh",
        password="SecurePass123!@#",
        role="nurse",
        hospital=hospital_a,
        ward=ward_a1,
        account_status="active",
    )
    return user


@pytest.fixture
def lab_tech_a(db, hospital_a):
    """Create Lab Technician user in Hospital A."""
    return User.objects.create_user(
        email="lab_tech_a@test.medsync.gh",
        password="SecurePass123!@#",
        role="lab_technician",
        hospital=hospital_a,
        account_status="active",
    )


@pytest.fixture
def hospital_admin_a(db, hospital_a):
    """Create Hospital Admin user for Hospital A."""
    return User.objects.create_user(
        email="admin_a@test.medsync.gh",
        password="SecurePass123!@#",
        role="hospital_admin",
        hospital=hospital_a,
        account_status="active",
    )


@pytest.fixture
def receptionist_a(db, hospital_a):
    """Create Receptionist user in Hospital A."""
    return User.objects.create_user(
        email="receptionist_a@test.medsync.gh",
        password="SecurePass123!@#",
        role="receptionist",
        hospital=hospital_a,
        account_status="active",
    )


# ============================================================================
# USERS - HOSPITAL B
# ============================================================================

@pytest.fixture
def doctor_b(db, hospital_b):
    """Create Doctor user in Hospital B."""
    return User.objects.create_user(
        email="doctor_b@test.medsync.gh",
        password="SecurePass123!@#",
        role="doctor",
        hospital=hospital_b,
        account_status="active",
    )


@pytest.fixture
def nurse_b(db, hospital_b, ward_b1):
    """Create Nurse user in Hospital B assigned to Ward B1."""
    user = User.objects.create_user(
        email="nurse_b@test.medsync.gh",
        password="SecurePass123!@#",
        role="nurse",
        hospital=hospital_b,
        ward=ward_b1,
        account_status="active",
    )
    return user


@pytest.fixture
def hospital_admin_b(db, hospital_b):
    """Create Hospital Admin user for Hospital B."""
    return User.objects.create_user(
        email="admin_b@test.medsync.gh",
        password="SecurePass123!@#",
        role="hospital_admin",
        hospital=hospital_b,
        account_status="active",
    )


# ============================================================================
# SUPER ADMIN
# ============================================================================

@pytest.fixture
def super_admin(db):
    """Create Super Admin user (no hospital assigned)."""
    return User.objects.create_user(
        email="superadmin@test.medsync.gh",
        password="SecurePass123!@#",
        role="super_admin",
        account_status="active",
    )


@pytest.fixture
def super_admin_with_hospital(db, hospital_a):
    """Create Super Admin user with Hospital A assigned."""
    return User.objects.create_user(
        email="superadmin_ha@test.medsync.gh",
        password="SecurePass123!@#",
        role="super_admin",
        hospital=hospital_a,
        account_status="active",
    )


# ============================================================================
# PATIENTS
# ============================================================================

@pytest.fixture
def patient_a(db, hospital_a):
    """Create Patient in Hospital A."""
    return Patient.objects.create(
        ghana_health_id="GHI_A_001",
        registered_at=hospital_a,
        full_name="John Doe",
        date_of_birth="1990-01-15",
        gender="male",
    )


@pytest.fixture
def patient_a2(db, hospital_a):
    """Create second Patient in Hospital A."""
    return Patient.objects.create(
        ghana_health_id="GHI_A_002",
        registered_at=hospital_a,
        full_name="Jane Smith",
        date_of_birth="1985-06-20",
        gender="female",
    )


@pytest.fixture
def patient_b(db, hospital_b):
    """Create Patient in Hospital B."""
    return Patient.objects.create(
        ghana_health_id="GHI_B_001",
        registered_at=hospital_b,
        full_name="Alice Johnson",
        date_of_birth="1995-03-10",
        gender="female",
    )


# ============================================================================
# ENCOUNTERS
# ============================================================================

@pytest.fixture
def encounter_a(db, hospital_a, patient_a, doctor_a):
    """Create Encounter for Patient A with Doctor A."""
    return Encounter.objects.create(
        patient=patient_a,
        hospital=hospital_a,
        provider=doctor_a,
        chief_complaint="Fever and cough",
        status="active",
        created_at=timezone.now(),
    )


@pytest.fixture
def encounter_b(db, hospital_b, patient_b, doctor_b):
    """Create Encounter for Patient B with Doctor B."""
    return Encounter.objects.create(
        patient=patient_b,
        hospital=hospital_b,
        provider=doctor_b,
        chief_complaint="Back pain",
        status="active",
        created_at=timezone.now(),
    )
