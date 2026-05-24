from django.test import TestCase, override_settings
from api.ai.safety_gates import validate_ai_confidence_threshold

class AISafetyGateTests(TestCase):
    """Tests for AI safety gates and confidence thresholds."""

    @override_settings(AI_CONFIDENCE_THRESHOLD_CLINICAL=0.80)
    def test_clinical_threshold_enforced(self):
        """Should return False for confidence below 80% in clinical mode."""
        self.assertFalse(validate_ai_confidence_threshold(0.79, is_clinical=True))
        self.assertFalse(validate_ai_confidence_threshold(0.50, is_clinical=True))
        self.assertTrue(validate_ai_confidence_threshold(0.80, is_clinical=True))
        self.assertTrue(validate_ai_confidence_threshold(0.95, is_clinical=True))

    @override_settings(AI_CONFIDENCE_THRESHOLD_DEV=0.70)
    def test_dev_threshold_enforced(self):
        """Should return False for confidence below 70% in non-clinical mode."""
        self.assertFalse(validate_ai_confidence_threshold(0.69, is_clinical=False))
        self.assertTrue(validate_ai_confidence_threshold(0.70, is_clinical=False))
        self.assertTrue(validate_ai_confidence_threshold(0.75, is_clinical=False))

    @override_settings(AI_CONFIDENCE_THRESHOLD_CLINICAL=0.90)
    def test_custom_clinical_threshold(self):
        """Should respect custom settings for clinical threshold."""
        self.assertFalse(validate_ai_confidence_threshold(0.85, is_clinical=True))
        self.assertTrue(validate_ai_confidence_threshold(0.91, is_clinical=True))
