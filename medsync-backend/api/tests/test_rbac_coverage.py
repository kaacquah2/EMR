import re

from django.test import TestCase

from api.permissions import PERMISSION_MATRIX
from api.urls import urlpatterns


class TestAllRoutesHavePermissions(TestCase):
    """Every API route shape must have permission matrix coverage."""

    def test_every_url_has_permission_entry(self):
        def normalize(route: str) -> str:
            return re.sub(r"<[^>]+>", "<param>", route.strip("/"))

        registered_routes = set()
        for pattern in urlpatterns:
            route = getattr(getattr(pattern, "pattern", None), "route", None)
            if route:
                registered_routes.add(normalize(route))

        covered_routes = {normalize(route) for route in PERMISSION_MATRIX.keys()}
        uncovered = sorted(registered_routes - covered_routes)

        self.assertEqual(
            uncovered,
            [],
            "Routes missing permission coverage:\n" + "\n".join(f"  - {route}" for route in uncovered),
        )
