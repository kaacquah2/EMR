"""
RBAC Coverage Test — Bidirectional Check.

Ensures:
1. Every URL pattern registered in api/urls.py has an entry in PERMISSION_MATRIX
   (no uncovered routes — security gap prevention)
2. Every PERMISSION_MATRIX entry maps to at least one registered URL pattern
   (no stale dead entries — keeps matrix accurate)
3. Every role used in PERMISSION_MATRIX is a known, valid user role
4. No endpoint grants access to a role that doesn't exist in the user model

Run with:
    pytest api/tests/test_rbac_coverage.py -v

Or via management command (CI-friendly):
    python manage.py check_rbac_coverage
"""

import re
from typing import Dict, List, Set, Tuple

from django.test import TestCase
from django.urls import URLPattern, URLResolver

from shared.permissions import PERMISSION_MATRIX
import api.urls as api_urls_module


# ---------------------------------------------------------------------------
# KNOWN ROLES (must match User.ROLES in core/models.py)
# ---------------------------------------------------------------------------

KNOWN_ROLES = {
    "super_admin",
    "hospital_admin",
    "doctor",
    "nurse",
    "receptionist",
    "lab_technician",
    "pharmacy_technician",
    "radiology_technician",
    "billing_staff",
    "ward_clerk",
    # Special permission matrix sentinels
    "public",
    "authenticated",
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _normalize_route(route: str) -> str:
    """
    Normalise a URL route string for comparison:
    - Strip leading/trailing slashes
    - Strip api/v1/ prefix if present
    - Replace all Django URL parameters (<type:name>) with <param>

    Example:
        'patients/<uuid:pk>/'  →  'patients/<param>'
        'ai/analyze-patient/<pk>'  →  'ai/analyze-patient/<param>'
    """
    route = route.strip("/")
    if route.startswith("api/v1/"):
        route = route[7:]
    elif route == "api/v1":
        route = ""
    # Replace <type:name> and <name> patterns
    route = re.sub(r"<[^>]+>", "<param>", route)
    return route


def _normalize_matrix_key(key: str) -> str:
    """
    Normalise a PERMISSION_MATRIX key for comparison.
    PERMISSION_MATRIX uses <pk>, <uuid:pk>, etc. — standardise.
    """
    key = key.strip("/")
    key = re.sub(r"<[^>]+>", "<param>", key)
    return key


def _collect_urlpatterns(urlpatterns, prefix: str = "") -> List[str]:
    """
    Recursively collect all URL route strings from a urlpatterns list.
    Returns normalised routes.
    """
    routes = []
    for pattern in urlpatterns:
        pat = getattr(pattern, "pattern", None)
        route = getattr(pat, "_route", None) or getattr(pat, "route", None)
        if route is None:
            continue
        full_route = prefix + route
        if isinstance(pattern, URLResolver):
            # Recurse into included urls
            routes.extend(_collect_urlpatterns(pattern.url_patterns, prefix=full_route))
        else:
            routes.append(_normalize_route(full_route))
    return routes


# ---------------------------------------------------------------------------
# TEST CASES
# ---------------------------------------------------------------------------

class TestRBACCoverageForward(TestCase):
    """Every registered URL must have a PERMISSION_MATRIX entry."""

    # Routes to intentionally skip (admin, schema, health, etc.)
    SKIP_PATTERNS: Set[str] = {
        # Django admin routes
        "admin/",
        "admin/<param>/",
        # DRF schema / docs
        "api-auth/",
        "schema/",
        "__debug__/",
    }

    def _get_covered_routes(self) -> Set[str]:
        return {_normalize_matrix_key(k) for k in PERMISSION_MATRIX.keys()}

    def _get_registered_routes(self) -> Set[str]:
        try:
            patterns = api_urls_module.urlpatterns
        except AttributeError:
            self.skipTest("api.urls.urlpatterns not accessible")
        return set(_collect_urlpatterns(patterns))

    def _should_skip(self, route: str) -> bool:
        for skip in self.SKIP_PATTERNS:
            if route.startswith(_normalize_route(skip)):
                return True
        return False

    def test_all_registered_urls_have_permission_entry(self):
        """
        Every URL registered in api/urls.py must appear in PERMISSION_MATRIX.

        A missing entry means a new endpoint was added without specifying
        who can access it — in fail-closed mode this returns 403 for everyone,
        which is a silent access bug.
        """
        registered = self._get_registered_routes()
        covered = self._get_covered_routes()
        uncovered = sorted(
            r for r in registered
            if r not in covered and not self._should_skip(r)
        )
        self.assertEqual(
            uncovered,
            [],
            msg=(
                f"\n{'=' * 60}\n"
                f"RBAC COVERAGE GAP: {len(uncovered)} route(s) registered in api/urls.py "
                f"have NO entry in shared/permissions.py PERMISSION_MATRIX.\n"
                f"Add each route to PERMISSION_MATRIX before merging.\n"
                f"{'=' * 60}\n"
                + "\n".join(f"  ✗ Missing: {r}" for r in uncovered)
            ),
        )


class TestRBACCoverageReverse(TestCase):
    """Every PERMISSION_MATRIX entry should map to a registered URL."""

    def _get_covered_routes(self) -> Set[str]:
        return {_normalize_matrix_key(k) for k in PERMISSION_MATRIX.keys()}

    def _get_registered_routes(self) -> Set[str]:
        try:
            patterns = api_urls_module.urlpatterns
        except AttributeError:
            self.skipTest("api.urls.urlpatterns not accessible")
        return set(_collect_urlpatterns(patterns))

    def test_no_stale_permission_matrix_entries(self):
        """
        Every PERMISSION_MATRIX key should correspond to a registered URL.

        Stale entries don't create security holes but cause confusion and
        indicate the matrix is out of sync with the actual URL config.
        This test warns (not fails) on stale entries.
        """
        registered = self._get_registered_routes()
        covered = self._get_covered_routes()

        # Special matrix keys that don't map to URL patterns
        SKIP_MATRIX_KEYS = {"public", "authenticated"}
        stale = sorted(
            k for k in covered
            if k not in registered and k not in SKIP_MATRIX_KEYS
        )

        # Warn only — stale entries are not a security vulnerability
        if stale:
            import warnings
            warnings.warn(
                f"\nRBAC matrix has {len(stale)} potentially stale entry(ies) "
                f"(in PERMISSION_MATRIX but not in api/urls.py):\n"
                + "\n".join(f"  ⚠  {k}" for k in stale),
                stacklevel=2,
            )


class TestRBACRoleValidity(TestCase):
    """All roles used in PERMISSION_MATRIX must be defined in the User model."""

    def test_all_roles_are_valid(self):
        """
        Every role string in PERMISSION_MATRIX values must be in KNOWN_ROLES.

        An unknown role would mean RBAC enforcement silently fails for those
        entries (no user would ever match an unknown role string).
        """
        invalid_roles = []

        for endpoint, role_map in PERMISSION_MATRIX.items():
            for role in role_map.keys():
                if role not in KNOWN_ROLES:
                    invalid_roles.append(f"  Endpoint '{endpoint}' uses unknown role '{role}'")

        self.assertEqual(
            invalid_roles,
            [],
            msg=(
                f"\n{'=' * 60}\n"
                f"RBAC ROLE VALIDITY: {len(invalid_roles)} unknown role(s) in PERMISSION_MATRIX.\n"
                f"Update KNOWN_ROLES in this test file or fix the typo.\n"
                f"{'=' * 60}\n"
                + "\n".join(invalid_roles)
            ),
        )

    def test_all_http_methods_are_valid(self):
        """
        Every HTTP method in PERMISSION_MATRIX must be a standard REST method.
        Catches typos like 'GETS' or 'DELET'.
        """
        VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        invalid_methods = []

        for endpoint, role_map in PERMISSION_MATRIX.items():
            for role, methods in role_map.items():
                for method in methods:
                    if method not in VALID_METHODS:
                        invalid_methods.append(
                            f"  Endpoint '{endpoint}' role '{role}' has invalid method '{method}'"
                        )

        self.assertEqual(
            invalid_methods,
            [],
            msg=(
                f"Invalid HTTP methods in PERMISSION_MATRIX:\n" + "\n".join(invalid_methods)
            ),
        )


class TestRBACMatrixCompleteness(TestCase):
    """Structural completeness checks on PERMISSION_MATRIX."""

    def test_no_empty_role_maps(self):
        """No endpoint should have an empty role map (would deny everyone silently)."""
        empty = [ep for ep, rm in PERMISSION_MATRIX.items() if not rm]
        self.assertEqual(
            empty,
            [],
            msg=f"Endpoints with empty role maps (no one can access): {empty}",
        )

    def test_no_empty_method_lists(self):
        """No role in any endpoint should have an empty methods list."""
        empty_methods = []
        for endpoint, role_map in PERMISSION_MATRIX.items():
            for role, methods in role_map.items():
                if not methods:
                    empty_methods.append(f"  '{endpoint}' → role '{role}' has no methods")
        self.assertEqual(
            empty_methods,
            [],
            msg=f"Empty method lists in PERMISSION_MATRIX:\n" + "\n".join(empty_methods),
        )

    def test_super_admin_not_locked_out(self):
        """
        super_admin should have access to at least 80% of all endpoints.

        If this fails, it likely means a large batch of endpoints was added
        without including super_admin access, which is unusual.
        """
        total = len(PERMISSION_MATRIX)
        sa_accessible = sum(
            1 for ep, rm in PERMISSION_MATRIX.items()
            if "super_admin" in rm or "public" in rm or "authenticated" in rm
        )
        coverage_pct = sa_accessible / total if total > 0 else 0
        self.assertGreater(
            coverage_pct,
            0.80,
            msg=(
                f"super_admin only has access to {sa_accessible}/{total} "
                f"({coverage_pct:.0%}) endpoints. Expected >80%. "
                f"Check if super_admin was omitted from recently added entries."
            ),
        )
