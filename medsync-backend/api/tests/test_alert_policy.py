from django.test import TestCase

from api.permissions import ALERT_RESOLVE_ROLES, PERMISSION_MATRIX


class TestAlertPolicyConsistency(TestCase):
    def test_alert_resolve_roles_match_permission_matrix(self):
        map_roles = set(PERMISSION_MATRIX.get("alerts/<pk>/resolve", {}).keys())
        self.assertEqual(
            ALERT_RESOLVE_ROLES,
            map_roles,
            "ALERT_RESOLVE_ROLES and PERMISSION_MATRIX['alerts/<pk>/resolve'] are out of sync",
        )
