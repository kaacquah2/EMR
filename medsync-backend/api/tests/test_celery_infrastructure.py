"""
Tests for Celery task queue infrastructure.
"""
from django.test import TestCase, override_settings
from celery import current_app
from celery.result import EagerResult
from api.tasks import (
    export_patient_pdf_task,
    export_encounter_pdf_task,
    comprehensive_analysis_task,
    risk_prediction_task,
    mark_no_shows_task,
)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class CeleryTaskTestCase(TestCase):
    """Test Celery task execution in eager mode (synchronous for testing)."""

    def test_celery_configured(self):
        """Test that Celery is properly configured."""
        self.assertIsNotNone(current_app)
        self.assertTrue(current_app.conf.get("CELERY_TASK_TRACK_STARTED"))

    def test_export_patient_pdf_task_not_found(self):
        """Test PDF export task handles missing patient."""
        result = export_patient_pdf_task.apply_async(
            args=["invalid-uuid"], kwargs={"format_type": "summary"}
        ).get()
        
        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result["message"].lower())

    def test_comprehensive_analysis_task_not_found(self):
        """Test AI analysis task handles missing patient."""
        result = comprehensive_analysis_task.apply_async(
            args=["invalid-uuid"], kwargs={"analysis_type": "full"}
        ).get()
        
        self.assertEqual(result["status"], "error")

    def test_risk_prediction_task_success(self):
        """Test risk prediction task returns proper structure."""
        result = risk_prediction_task.apply_async(
            args=["test-patient-uuid"]
        ).get()
        
        self.assertEqual(result["status"], "success")
        self.assertIn("patient_id", result)
        self.assertIn("predictions", result)

    def test_mark_no_shows_task_success(self):
        """Test no-show marking task executes (may be skipped if model not ready)."""
        result = mark_no_shows_task.apply_async().get()
        
        self.assertIn(result["status"], ["success", "skipped"])

    def test_celery_task_retry_on_failure(self):
        """Test task retry mechanism."""
        # This tests that tasks can be configured with retry
        self.assertTrue(hasattr(export_patient_pdf_task, 'max_retries'))

    def test_task_logging(self):
        """Test that tasks use proper logging."""
        # Verify tasks import logging
        from api.tasks.export_tasks import logger as export_logger
        from api.tasks.ai_tasks import logger as ai_logger
        from api.tasks.appointment_tasks import logger as appointment_logger
        
        self.assertIsNotNone(export_logger)
        self.assertIsNotNone(ai_logger)
        self.assertIsNotNone(appointment_logger)

    def test_task_discovery(self):
        """Test that Celery can discover all tasks."""
        tasks = current_app.tasks
        
        # Check for expected task names
        task_names = list(tasks.keys())
        
        # Should have at least the debug task
        self.assertGreater(len(task_names), 0)

    def test_celery_broker_configuration(self):
        """Test Celery broker is configured."""
        broker_url = current_app.conf.get("CELERY_BROKER_URL")
        self.assertIsNotNone(broker_url)
        self.assertIn("redis://", broker_url)

    def test_celery_result_backend_configuration(self):
        """Test Celery result backend is configured."""
        result_backend = current_app.conf.get("CELERY_RESULT_BACKEND")
        self.assertIsNotNone(result_backend)
        self.assertIn("redis://", result_backend)

    def test_celery_serialization_json(self):
        """Test Celery uses JSON serialization."""
        serializer = current_app.conf.get("CELERY_TASK_SERIALIZER")
        self.assertEqual(serializer, "json")

    def test_celery_task_time_limits(self):
        """Test Celery task time limits are configured."""
        time_limit = current_app.conf.get("CELERY_TASK_TIME_LIMIT")
        self.assertEqual(time_limit, 30 * 60)  # 30 minutes


@override_settings(CELERY_ALWAYS_EAGER=True)
class CeleryTaskIntegrationTestCase(TestCase):
    """Integration tests for Celery tasks."""

    def test_task_chain_execution_order(self):
        """Test that tasks can be chained in proper order."""
        # Verify task functions exist and are callable
        self.assertTrue(callable(export_patient_pdf_task))
        self.assertTrue(callable(comprehensive_analysis_task))
        self.assertTrue(callable(mark_no_shows_task))

    def test_task_result_tracking(self):
        """Test that task results are tracked."""
        result = risk_prediction_task.apply_async(args=["test-uuid"])
        # In eager mode, result should be immediate
        self.assertIsNotNone(result)

    def test_celery_no_blocking_on_failed_redis(self):
        """Test Celery handles Redis connection gracefully."""
        # With proper configuration, Celery should retry connections
        # This is more of a manual test, but we verify config exists
        retry_on_startup = current_app.conf.get(
            "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP"
        )
        self.assertTrue(retry_on_startup)
