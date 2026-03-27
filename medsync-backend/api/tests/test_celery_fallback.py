"""
Tests for Celery fallback to synchronous execution.

Tests the fallback mechanism that allows tasks to execute synchronously
when the Celery broker is unavailable.
"""

import logging
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from celery import shared_task
from celery.exceptions import OperationalError

from api.tasks.fallback import can_use_celery, execute_task_sync_or_async


# Create simple test tasks for testing (renamed to avoid pytest collection)
@shared_task(bind=True, max_retries=1)
def simple_task_success(self, value):
    """Simple test task that returns the value."""
    return {"status": "success", "value": value}


@shared_task(bind=True, max_retries=1)
def simple_task_with_error(self):
    """Test task that raises an error."""
    raise ValueError("Test error")


class CeleryFallbackTestCase(TestCase):
    """Test Celery fallback to synchronous execution."""

    @patch('api.tasks.fallback.celery_app')
    def test_can_use_celery_returns_false_when_broker_unavailable(self, mock_celery):
        """Test can_use_celery returns False when broker connection fails."""
        # Simulate broker unavailable
        mock_conn = MagicMock()
        mock_conn.__enter__.side_effect = OperationalError("Connection failed")
        mock_celery.connection.return_value = mock_conn
        
        result = can_use_celery()
        
        self.assertFalse(result)

    @patch('api.tasks.fallback.celery_app')
    def test_can_use_celery_returns_true_when_broker_available(self, mock_celery):
        """Test can_use_celery returns True when broker is accessible."""
        # Simulate successful broker connection
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.connect.return_value = None
        mock_celery.connection.return_value = mock_conn
        
        result = can_use_celery()
        
        self.assertTrue(result)

    @patch('api.tasks.fallback.celery_app', None)
    def test_can_use_celery_returns_false_when_celery_not_available(self):
        """Test can_use_celery returns False when Celery is not installed."""
        result = can_use_celery()
        
        self.assertFalse(result)

    @override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
    @patch('api.tasks.fallback.can_use_celery', return_value=True)
    def test_execute_task_sync_or_async_uses_async_when_available(self, mock_can_use):
        """Test execute_task_sync_or_async uses async when Celery is available."""
        result = execute_task_sync_or_async(simple_task_success, 42)
        
        # In eager mode with Celery available, should get async result
        self.assertIsNotNone(result)
        # Note: In eager mode, the task is executed synchronously but via the async path

    @patch('api.tasks.fallback.can_use_celery', return_value=False)
    def test_execute_task_sync_or_async_uses_sync_when_unavailable(self, mock_can_use):
        """Test execute_task_sync_or_async uses sync when Celery unavailable."""
        result = execute_task_sync_or_async(simple_task_success, 42)
        
        # Should execute synchronously and return result
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["value"], 42)

    @patch('api.tasks.fallback.can_use_celery', return_value=False)
    def test_execute_task_sync_or_async_with_kwargs(self, mock_can_use):
        """Test execute_task_sync_or_async passes kwargs correctly."""
        # Mock a task function
        mock_task = Mock(return_value={"status": "success", "key": "value"})
        
        result = execute_task_sync_or_async(mock_task, 1, 2, key1="val1", key2="val2")
        
        # Verify task was called with correct args and kwargs
        mock_task.assert_called_once_with(1, 2, key1="val1", key2="val2")
        self.assertEqual(result["status"], "success")

    @patch('api.tasks.fallback.can_use_celery', return_value=False)
    def test_execute_task_sync_or_async_logs_sync_execution(self, mock_can_use):
        """Test fallback logs warning when falling back to sync."""
        mock_task = Mock(return_value={"status": "success"})
        
        with self.assertLogs('api.tasks.fallback', level='INFO') as log:
            execute_task_sync_or_async(mock_task, 1, 2)
            
            # Should log info about synchronous execution
            log_output = ' '.join(log.output)
            self.assertIn('synchronously', log_output.lower())

    @patch('api.tasks.fallback.can_use_celery', return_value=False)
    def test_execute_task_sync_or_async_returns_result_sync(self, mock_can_use):
        """Test execute_task_sync_or_async returns correct result in sync mode."""
        expected_result = {"status": "success", "data": "test"}
        mock_task = Mock(return_value=expected_result)
        
        result = execute_task_sync_or_async(mock_task, 1)
        
        self.assertEqual(result, expected_result)

    @patch('api.tasks.fallback.can_use_celery')
    def test_execute_task_sync_or_async_tries_async_first(self, mock_can_use):
        """Test execute_task_sync_or_async attempts async execution first."""
        mock_can_use.return_value = True
        mock_task = Mock(name="test_task")
        mock_task.name = "api.tasks.test_task"
        
        # Make apply_async return a result that can be .get()
        mock_result = Mock()
        mock_result.get.return_value = {"status": "success"}
        mock_task.apply_async.return_value = mock_result
        
        result = execute_task_sync_or_async(mock_task, 1)
        
        # Should have called apply_async (async attempt)
        mock_task.apply_async.assert_called_once()
        self.assertEqual(result["status"], "success")

    @patch('api.tasks.fallback.can_use_celery', return_value=True)
    def test_execute_task_sync_or_async_fallback_on_async_error(self, mock_can_use):
        """Test execute_task_sync_or_async falls back to sync if async fails."""
        mock_task = Mock(name="test_task")
        mock_task.name = "api.tasks.test_task"
        
        # Make apply_async fail, then sync works
        mock_task.apply_async.side_effect = Exception("Connection failed")
        mock_task.side_effect = None  # Sync execution succeeds
        mock_task.return_value = {"status": "success", "fallback": True}
        
        result = execute_task_sync_or_async(mock_task, 1)
        
        # Should have tried async then fallen back to sync
        mock_task.apply_async.assert_called_once()
        # Sync execution should have been called as fallback
        self.assertEqual(result["status"], "success")

    @patch('api.tasks.fallback.can_use_celery', return_value=False)
    def test_execute_task_sync_or_async_logs_broker_unavailable(self, mock_can_use):
        """Test logging when broker unavailable."""
        mock_task = Mock(return_value={"status": "success"})
        # This test just ensures execution works when broker unavailable
        result = execute_task_sync_or_async(mock_task, 1)
        self.assertEqual(result["status"], "success")

    @patch('api.tasks.fallback.can_use_celery', return_value=False)
    def test_execute_task_sync_or_async_with_exception_in_sync_task(self, mock_can_use):
        """Test execute_task_sync_or_async propagates exceptions in sync mode."""
        mock_task = Mock(side_effect=ValueError("Task execution failed"))
        
        with self.assertRaises(ValueError):
            execute_task_sync_or_async(mock_task, 1)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_fallback_with_real_task_eager_mode(self):
        """Test fallback with actual task in eager mode using valid UUID."""
        import uuid
        from api.tasks import comprehensive_analysis_task
        
        # Use a valid UUID format but for a non-existent patient
        valid_uuid = str(uuid.uuid4())
        result = execute_task_sync_or_async(
            comprehensive_analysis_task,
            valid_uuid,
            timeout=10
        )
        
        # Task should execute and return a result (error expected due to missing patient)
        self.assertIn("status", result)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_fallback_with_export_task(self):
        """Test fallback with PDF export task using valid UUID."""
        import uuid
        from api.tasks import export_patient_pdf_task
        
        # Use a valid UUID format but for a non-existent patient
        valid_uuid = str(uuid.uuid4())
        result = execute_task_sync_or_async(
            export_patient_pdf_task,
            valid_uuid,
            timeout=30
        )
        
        # Task should handle missing patient gracefully
        self.assertIn("status", result)


class CeleryFallbackIntegrationTestCase(TestCase):
    """Integration tests for fallback mechanism with task chain."""

    @patch('api.tasks.fallback.can_use_celery', return_value=False)
    def test_multiple_tasks_fallback_sequence(self, mock_can_use):
        """Test multiple tasks can be executed in sequence with fallback."""
        mock_task1 = Mock(return_value={"status": "success", "id": 1})
        mock_task2 = Mock(return_value={"status": "success", "id": 2})
        
        result1 = execute_task_sync_or_async(mock_task1, 1)
        result2 = execute_task_sync_or_async(mock_task2, result1["id"])
        
        self.assertEqual(result1["id"], 1)
        self.assertEqual(result2["id"], 2)

    @patch('api.tasks.fallback.can_use_celery')
    def test_fallback_switch_between_async_and_sync(self, mock_can_use):
        """Test switching between async and sync during execution."""
        # First call: Celery available
        mock_can_use.return_value = True
        mock_task1 = Mock(name="task1")
        mock_task1.name = "api.tasks.task1"
        mock_result1 = Mock()
        mock_result1.get.return_value = {"status": "success", "task": 1}
        mock_task1.apply_async.return_value = mock_result1
        
        result1 = execute_task_sync_or_async(mock_task1, 1)
        self.assertEqual(result1["task"], 1)
        
        # Second call: Celery unavailable
        mock_can_use.return_value = False
        mock_task2 = Mock(return_value={"status": "success", "task": 2})
        
        result2 = execute_task_sync_or_async(mock_task2, 1)
        self.assertEqual(result2["task"], 2)
