"""
Anomaly Detection Middleware

Monitors user behavior and alerts on suspicious patterns.
Rule: Alert if user accesses >200 unique patients in 1 hour.
"""

import time
from collections import defaultdict
from threading import Lock
from django.utils import timezone
from datetime import timedelta
import logging
import re

logger = logging.getLogger(__name__)

# In-memory tracking (in production, use Redis)
_access_tracker = defaultdict(lambda: {'patients': set(), 'window_start': None})
_tracker_lock = Lock()

PATIENT_ACCESS_THRESHOLD = 200
WINDOW_HOURS = 1


def track_patient_access(user_id: str, patient_id: str) -> bool:
    """
    Track patient access and return True if anomaly detected.
    """
    now = timezone.now()
    
    with _tracker_lock:
        tracker = _access_tracker[user_id]
        
        # Reset window if expired
        if tracker['window_start'] is None or (now - tracker['window_start']) > timedelta(hours=WINDOW_HOURS):
            tracker['patients'] = set()
            tracker['window_start'] = now
        
        # Add patient to tracking set
        tracker['patients'].add(patient_id)
        
        # Check threshold
        if len(tracker['patients']) > PATIENT_ACCESS_THRESHOLD:
            return True
    
    return False


def create_anomaly_alert(user, patient_count: int, window_hours: int):
    """
    Create an alert for anomalous behavior.
    """
    from core.models import AuditLog
    
    try:
        AuditLog.objects.create(
            user=user,
            action='ANOMALY_DETECTED',
            resource_type='SecurityAlert',
            resource_id=f'patient_access_{user.id}',
            hospital=getattr(user, 'hospital', None),
            ip_address='system',
            details={
                'alert_type': 'excessive_patient_access',
                'patient_count': patient_count,
                'window_hours': window_hours,
                'threshold': PATIENT_ACCESS_THRESHOLD,
                'message': f'User accessed {patient_count} patients in {window_hours} hour(s)',
            }
        )
        
        logger.warning(
            f"ANOMALY ALERT: User {user.email} accessed {patient_count} patients "
            f"in {window_hours} hour(s) (threshold: {PATIENT_ACCESS_THRESHOLD})"
        )
        
        # In production: send notification to security team / hospital admin
        
    except Exception as e:
        logger.error(f"Failed to create anomaly alert: {e}")


class AnomalyDetectionMiddleware:
    """
    Django middleware to detect anomalous user behavior.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Patient access patterns to monitor
        self.patient_patterns = [
            r'/api/v1/patients/([a-f0-9-]+)',
            r'/api/v1/patients/([a-f0-9-]+)/records',
            r'/api/v1/patients/([a-f0-9-]+)/encounters',
            r'/api/v1/patients/([a-f0-9-]+)/vitals',
        ]
    
    def __call__(self, request):
        # Process before response
        self._track_access(request)
        
        response = self.get_response(request)
        
        return response
    
    def _track_access(self, request):
        """Track patient access patterns."""
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return
        
        path = request.path
        
        for pattern in self.patient_patterns:
            match = re.search(pattern, path)
            if match:
                patient_id = match.group(1)
                user_id = str(request.user.id)
                
                is_anomaly = track_patient_access(user_id, patient_id)
                
                if is_anomaly:
                    with _tracker_lock:
                        patient_count = len(_access_tracker[user_id]['patients'])
                    
                    create_anomaly_alert(request.user, patient_count, WINDOW_HOURS)
                    
                    # Reset after alert to avoid repeated alerts
                    with _tracker_lock:
                        _access_tracker[user_id] = {'patients': set(), 'window_start': None}
                
                break
