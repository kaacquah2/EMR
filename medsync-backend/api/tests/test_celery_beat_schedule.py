"""
Tests for Celery Beat periodic task scheduling.

Verifies that the mark_no_shows_task is properly registered and scheduled
to run every 15 minutes via Celery Beat.
"""
from django.test import TestCase, override_settings
from django.conf import settings
from celery import current_app
from celery.schedules import crontab
import re


class CeleryBeatScheduleTestCase(TestCase):
    """Test Celery Beat schedule configuration."""

    def test_celery_beat_schedule_configured(self):
        """Test that CELERY_BEAT_SCHEDULE is properly configured."""
        beat_schedule = settings.CELERY_BEAT_SCHEDULE
        self.assertIsNotNone(beat_schedule)
        self.assertIsInstance(beat_schedule, dict)
        self.assertGreater(len(beat_schedule), 0)

    def test_mark_no_shows_task_in_beat_schedule(self):
        """Test that mark_no_shows_task is registered in beat schedule."""
        beat_schedule = settings.CELERY_BEAT_SCHEDULE
        self.assertIn('mark-no-shows-every-15-minutes', beat_schedule)

    def test_mark_no_shows_task_name_is_correct(self):
        """Test that task name points to correct function."""
        beat_schedule = settings.CELERY_BEAT_SCHEDULE
        task_config = beat_schedule['mark-no-shows-every-15-minutes']
        
        self.assertEqual(
            task_config['task'],
            'api.tasks.appointment_tasks.mark_no_shows_task'
        )

    def test_mark_no_shows_schedule_is_every_15_minutes(self):
        """Test that schedule is set to every 15 minutes."""
        beat_schedule = settings.CELERY_BEAT_SCHEDULE
        task_config = beat_schedule['mark-no-shows-every-15-minutes']
        schedule = task_config['schedule']
        
        # Verify it's a crontab schedule
        self.assertIsInstance(schedule, crontab)
        
        # Check that minute pattern is */15 (every 15 minutes)
        # crontab minute attribute is a set of allowed minutes
        minute_pattern = schedule.minute
        # */15 means minutes 0, 15, 30, 45
        expected_minutes = {0, 15, 30, 45}
        self.assertEqual(minute_pattern, expected_minutes)

    def test_mark_no_shows_task_expiry_is_set(self):
        """Test that task has expiry time (10 minutes)."""
        beat_schedule = settings.CELERY_BEAT_SCHEDULE
        task_config = beat_schedule['mark-no-shows-every-15-minutes']
        
        self.assertIn('options', task_config)
        self.assertIn('expires', task_config['options'])
        self.assertEqual(task_config['options']['expires'], 600)  # 10 minutes

    def test_mark_no_shows_task_can_be_imported(self):
        """Test that the task can be imported successfully."""
        try:
            from api.tasks.appointment_tasks import mark_no_shows_task
            self.assertIsNotNone(mark_no_shows_task)
            self.assertTrue(callable(mark_no_shows_task))
        except ImportError as e:
            self.fail(f"Failed to import mark_no_shows_task: {e}")

    def test_celery_beat_scheduler_available(self):
        """Test that django-celery-beat is installed and available."""
        from django.apps import apps
        from django_celery_beat.apps import BeatConfig
        
        # Check that django_celery_beat app is installed
        self.assertIn('django_celery_beat', settings.INSTALLED_APPS)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_mark_no_shows_task_is_discoverable(self):
        """Test that Celery can discover the mark_no_shows_task."""
        tasks = current_app.tasks
        task_name = 'api.tasks.appointment_tasks.mark_no_shows_task'
        
        # The task should be registered in Celery
        self.assertIn(task_name, tasks)

    def test_schedule_documentation_comment_exists(self):
        """Test that CELERY_BEAT_SCHEDULE has proper documentation comments."""
        # Read the settings file to verify documentation
        import inspect
        import medsync_backend.settings as settings_module
        
        source = inspect.getsource(settings_module)
        # Check that documentation about 15-minute interval exists
        self.assertIn('15 minutes', source)
        self.assertIn('CELERY_BEAT_SCHEDULE', source)

    def test_crontab_schedule_pattern_validity(self):
        """Test that the crontab schedule pattern is valid."""
        beat_schedule = settings.CELERY_BEAT_SCHEDULE
        task_config = beat_schedule['mark-no-shows-every-15-minutes']
        schedule = task_config['schedule']
        
        # Verify that the schedule will fire on valid times
        # Check that it fires at minute 0 (start of hour)
        self.assertIn(0, schedule.minute)
        # Check that it fires at minute 15
        self.assertIn(15, schedule.minute)
        # Check that it fires at minute 30
        self.assertIn(30, schedule.minute)
        # Check that it fires at minute 45
        self.assertIn(45, schedule.minute)

    def test_no_show_grace_period_setting_exists(self):
        """Test that NO_SHOW_GRACE_PERIOD_MINUTES setting is configured."""
        grace_period = getattr(settings, 'NO_SHOW_GRACE_PERIOD_MINUTES', None)
        self.assertIsNotNone(grace_period)
        self.assertEqual(grace_period, 15)

    def test_schedule_options_are_valid(self):
        """Test that schedule options are properly formatted."""
        beat_schedule = settings.CELERY_BEAT_SCHEDULE
        task_config = beat_schedule['mark-no-shows-every-15-minutes']
        
        # Verify options dict structure
        options = task_config['options']
        self.assertIsInstance(options, dict)
        
        # Verify expires is a positive integer (seconds)
        expires = options['expires']
        self.assertIsInstance(expires, int)
        self.assertGreater(expires, 0)
        self.assertEqual(expires, 600)  # 10 minutes in seconds
