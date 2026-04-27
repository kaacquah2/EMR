"""
Tests for AI Clinical Deployment Workflow (Phase 8.3).

Tests the circuit breaker, hospital approval workflow, and metrics validation.
"""

import json
from datetime import datetime, timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from django.utils import timezone

from core.models import Hospital
from api.models import AIDeploymentLog
from api.ai.governance import AIClinicalFeaturesDisabledError

User = get_user_model()


class AIDeploymentLogModelTests(TestCase):
    """Test AIDeploymentLog model methods."""

    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Greater Accra",
            nhis_code="TST001",
            address="123 Test Street, Accra",
            is_active=True
        )
        self.admin_user = User.objects.create_user(
            email="admin@hospital.com",
            password="TempPass123!@#",
            role="hospital_admin",
            hospital=self.hospital,
            account_status="active"
        )

    def test_deployment_log_creation(self):
        """Test creating an AIDeploymentLog record."""
        metrics = {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.88,
            "diseases": {
                "malaria": {"auc_roc": 0.92, "sensitivity": 0.85, "specificity": 0.95}
            },
            "test_data_size": 1000,
            "test_data_source": "MIMIC-IV",
            "training_date": "2026-04-20"
        }

        deployment = AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
            approval_notes="Approved for clinical use"
        )

        self.assertTrue(deployment.enabled)
        self.assertEqual(deployment.model_version, "1.0.0-mimic-iv")
        self.assertEqual(deployment.hospital, self.hospital)
        self.assertIsNone(deployment.disabled_at)

    def test_validate_metrics_pass(self):
        """Test metrics validation when all thresholds are met."""
        metrics = {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.88,
        }

        deployment = AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        is_valid, message = deployment.validate_metrics()
        self.assertTrue(is_valid)
        self.assertIn("meet clinical thresholds", message)

    def test_validate_metrics_auc_roc_too_low(self):
        """Test metrics validation fails when AUC-ROC is below threshold."""
        metrics = {
            "overall_auc_roc": 0.75,  # Below 0.80 threshold
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.88,
        }

        deployment = AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        is_valid, message = deployment.validate_metrics()
        self.assertFalse(is_valid)
        self.assertIn("AUC-ROC", message)

    def test_validate_metrics_sensitivity_too_low(self):
        """Test metrics validation fails when sensitivity is below threshold."""
        metrics = {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.70,  # Below 0.75 threshold
            "overall_specificity": 0.88,
        }

        deployment = AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        is_valid, message = deployment.validate_metrics()
        self.assertFalse(is_valid)
        self.assertIn("Sensitivity", message)

    def test_validate_metrics_specificity_too_low(self):
        """Test metrics validation fails when specificity is below threshold."""
        metrics = {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.80,  # Below 0.85 threshold
        }

        deployment = AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        is_valid, message = deployment.validate_metrics()
        self.assertFalse(is_valid)
        self.assertIn("Specificity", message)

    def test_validate_metrics_no_metrics(self):
        """Test metrics validation fails when metrics are missing."""
        deployment = AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics={},
        )

        is_valid, message = deployment.validate_metrics()
        self.assertFalse(is_valid)
        self.assertIn("No validation metrics", message)

    def test_get_latest_for_hospital(self):
        """Test retrieving the latest deployment for a hospital."""
        # Create two deployments
        metrics = {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.88,
        }

        deployment1 = AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        # Wait a moment to ensure different timestamps
        deployment2 = AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=False,
            model_version="1.1.0-ghana",
            validation_metrics=metrics,
        )

        latest = AIDeploymentLog.get_latest_for_hospital(self.hospital)
        # Should be the most recent one
        self.assertEqual(latest.id, deployment2.id)

    def test_is_clinical_ai_enabled_for_hospital_enabled(self):
        """Test checking if AI is enabled for a hospital."""
        metrics = {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.88,
        }

        AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        is_enabled = AIDeploymentLog.is_clinical_ai_enabled_for_hospital(self.hospital)
        self.assertTrue(is_enabled)

    def test_is_clinical_ai_enabled_for_hospital_disabled(self):
        """Test checking if AI is disabled for a hospital."""
        metrics = {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.88,
        }

        AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=False,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        is_enabled = AIDeploymentLog.is_clinical_ai_enabled_for_hospital(self.hospital)
        self.assertFalse(is_enabled)

    def test_is_clinical_ai_enabled_for_hospital_no_record(self):
        """Test checking AI status when no deployment record exists."""
        is_enabled = AIDeploymentLog.is_clinical_ai_enabled_for_hospital(self.hospital)
        self.assertFalse(is_enabled)


class AIDeploymentAPITests(TestCase):
    """Test AI deployment API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Greater Accra",
            nhis_code="TST001",
            address="123 Test Street, Accra",is_active=True
        )
        self.admin_user = User.objects.create_user(
            email="admin@hospital.com",
            password="TempPass123!@#",
            role="hospital_admin",
            hospital=self.hospital,
            account_status="active"
        )
        self.doctor_user = User.objects.create_user(
            email="doctor@hospital.com",
            password="TempPass123!@#",
            role="doctor",
            hospital=self.hospital,
            account_status="active"
        )

    def test_enable_clinical_ai_success(self):
        """Test hospital admin enabling clinical AI with valid metrics."""
        self.client.force_authenticate(user=self.admin_user)

        payload = {
            "model_version": "1.0.0-mimic-iv",
            "validation_metrics": {
                "overall_auc_roc": 0.85,
                "overall_sensitivity": 0.78,
                "overall_specificity": 0.88,
                "test_data_size": 1000,
                "test_data_source": "MIMIC-IV",
                "training_date": "2026-04-20"
            },
            "approval_notes": "Validated on MIMIC-IV ICU data. Meets all thresholds."
        }

        response = self.client.post(
            "/api/v1/admin/ai/enable",
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["deployment"]["hospital"], "Test Hospital")
        self.assertTrue(data["deployment"]["enabled"])

    def test_enable_clinical_ai_metrics_too_low(self):
        """Test hospital admin cannot enable AI with metrics below thresholds."""
        self.client.force_authenticate(user=self.admin_user)

        payload = {
            "model_version": "1.0.0-mimic-iv",
            "validation_metrics": {
                "overall_auc_roc": 0.75,  # Below threshold
                "overall_sensitivity": 0.78,
                "overall_specificity": 0.88,
            },
            "approval_notes": "Attempted approval with low metrics"
        }

        response = self.client.post(
            "/api/v1/admin/ai/enable",
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("do not meet clinical thresholds", data["error"])

    def test_enable_clinical_ai_missing_metrics(self):
        """Test hospital admin cannot enable AI without metrics."""
        self.client.force_authenticate(user=self.admin_user)

        payload = {
            "model_version": "1.0.0-mimic-iv",
            "approval_notes": "Missing metrics"
        }

        response = self.client.post(
            "/api/v1/admin/ai/enable",
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("validation_metrics is required", data["error"])

    def test_get_ai_deployment_status(self):
        """Test getting current AI deployment status."""
        self.client.force_authenticate(user=self.admin_user)

        # First enable AI
        metrics = {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.88,
        }
        AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        # Then check status
        response = self.client.get("/api/v1/admin/ai/status")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["enabled"])
        self.assertEqual(data["model_version"], "1.0.0-mimic-iv")

    def test_get_ai_deployment_status_no_deployment(self):
        """Test getting AI status when no deployment exists."""
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/v1/admin/ai/status")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["enabled"])
        self.assertIn("No AI deployment", data["message"])

    def test_disable_clinical_ai(self):
        """Test hospital admin disabling clinical AI."""
        self.client.force_authenticate(user=self.admin_user)

        # First enable AI
        metrics = {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.88,
        }
        AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        # Then disable it
        response = self.client.post(
            "/api/v1/admin/ai/disable",
            data=json.dumps({"reason": "Model retraining required"}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("disabled", data["message"].lower())

        # Verify it's actually disabled
        deployment = AIDeploymentLog.get_latest_for_hospital(self.hospital)
        self.assertFalse(deployment.enabled)
        self.assertIsNotNone(deployment.disabled_at)

    def test_get_ai_deployment_history(self):
        """Test getting deployment history."""
        self.client.force_authenticate(user=self.admin_user)

        # Create multiple deployments
        metrics = {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.88,
        }

        AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=True,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        AIDeploymentLog.objects.create(
            hospital=self.hospital,
            enabled_by=self.admin_user,
            enabled=False,
            model_version="1.0.0-mimic-iv",
            validation_metrics=metrics,
        )

        response = self.client.get("/api/v1/admin/ai/history")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["history"]), 2)

    def test_doctor_cannot_enable_ai(self):
        """Test that doctors cannot enable clinical AI (only hospital_admin)."""
        self.client.force_authenticate(user=self.doctor_user)

        payload = {
            "model_version": "1.0.0-mimic-iv",
            "validation_metrics": {
                "overall_auc_roc": 0.85,
                "overall_sensitivity": 0.78,
                "overall_specificity": 0.88,
            },
            "approval_notes": "Should fail"
        }

        response = self.client.post(
            "/api/v1/admin/ai/enable",
            data=json.dumps(payload),
            content_type="application/json"
        )

        # Should be forbidden or require hospital_admin role
        self.assertIn(response.status_code, [403, 401])


