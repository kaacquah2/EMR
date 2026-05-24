"""
Django management command: check_rbac_coverage

CI-friendly check that all API URL patterns have PERMISSION_MATRIX coverage.
Exits non-zero on coverage gaps so CI pipelines can catch missing permissions.

Usage:
    python manage.py check_rbac_coverage
    python manage.py check_rbac_coverage --strict    # also fails on stale entries
    python manage.py check_rbac_coverage --format json

Output:
    On success:  "✓ RBAC coverage OK — N routes covered"
    On failure:  Lists uncovered routes, exits 1

CI integration (GitHub Actions example):
    - name: RBAC coverage check
      run: python manage.py check_rbac_coverage --strict
"""

from __future__ import annotations

import json
import re
import sys
from typing import Dict, List, Optional, Set

from django.core.management.base import BaseCommand

from shared.permissions import PERMISSION_MATRIX


KNOWN_ROLES = {
    "super_admin", "hospital_admin", "doctor", "nurse", "receptionist",
    "lab_technician", "pharmacy_technician", "radiology_technician",
    "billing_staff", "ward_clerk",
    "public", "authenticated",
}

SKIP_URL_PREFIXES = {"admin/", "api-auth/", "schema/", "__debug__/"}


def _normalize(route: str) -> str:
    """Normalise route for comparison: strip slashes, replace path params."""
    route = route.strip("/")
    if route.startswith("api/v1/"):
        route = route[7:]
    elif route == "api/v1":
        route = ""
    route = re.sub(r"<[^>]+>", "<param>", route)
    return route


def _collect_routes(urlpatterns, prefix: str = "") -> List[str]:
    """Recursively collect normalised URL routes."""
    from django.urls import URLResolver
    routes = []
    for pattern in urlpatterns:
        pat = getattr(pattern, "pattern", None)
        route = getattr(pat, "_route", None) or getattr(pat, "route", None)
        if route is None:
            continue
        full = prefix + route
        if isinstance(pattern, URLResolver):
            routes.extend(_collect_routes(pattern.url_patterns, prefix=full))
        else:
            routes.append(_normalize(full))
    return routes


class Command(BaseCommand):
    help = (
        "Check RBAC coverage: verify every API URL has a PERMISSION_MATRIX entry. "
        "Exit code 0 = OK, 1 = gaps found."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Also fail on stale PERMISSION_MATRIX entries (not mapped to any URL)",
        )
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--fix-hint",
            action="store_true",
            help="Print suggested PERMISSION_MATRIX entries for uncovered routes",
        )

    def handle(self, *args, **options):
        import api.urls as api_urls_module

        try:
            patterns = api_urls_module.urlpatterns
        except AttributeError:
            self.stderr.write(self.style.ERROR("Cannot import api.urls.urlpatterns"))
            sys.exit(1)

        registered: Set[str] = set(_collect_routes(patterns))
        covered: Set[str] = {_normalize(k) for k in PERMISSION_MATRIX.keys()}

        # --- Forward: routes missing from PERMISSION_MATRIX ---
        uncovered = sorted(
            r for r in registered
            if r not in covered and not any(r.startswith(_normalize(s)) for s in SKIP_URL_PREFIXES)
        )

        # --- Reverse: stale PERMISSION_MATRIX entries ---
        stale = sorted(r for r in covered if r not in registered)

        # --- Role validity ---
        unknown_roles: List[str] = []
        for endpoint, role_map in PERMISSION_MATRIX.items():
            for role in role_map.keys():
                if role not in KNOWN_ROLES:
                    unknown_roles.append(f"{endpoint} → role '{role}'")

        # --- Decide outcome ---
        has_errors = bool(uncovered or unknown_roles)
        has_warnings = bool(stale)
        exit_code = 0

        if has_errors:
            exit_code = 1
        if options["strict"] and has_warnings:
            exit_code = 1

        # --- Output ---
        if options["format"] == "json":
            result = {
                "ok": exit_code == 0,
                "registered_routes": len(registered),
                "covered_routes": len(covered),
                "uncovered": uncovered,
                "stale": stale,
                "unknown_roles": unknown_roles,
            }
            self.stdout.write(json.dumps(result, indent=2))
        else:
            self._text_output(uncovered, stale, unknown_roles, registered, covered, options)

        sys.exit(exit_code)

    def _text_output(
        self,
        uncovered: List[str],
        stale: List[str],
        unknown_roles: List[str],
        registered: Set[str],
        covered: Set[str],
        options: dict,
    ):
        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write(self.style.HTTP_INFO("  MedSync RBAC Coverage Report"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"  Registered URL routes : {len(registered)}")
        self.stdout.write(f"  PERMISSION_MATRIX keys: {len(covered)}")
        self.stdout.write("")

        if not uncovered and not unknown_roles and not stale:
            self.stdout.write(self.style.SUCCESS(
                f"  [OK] RBAC coverage OK -- all {len(registered)} routes are covered"
            ))
            self.stdout.write("")
            return

        if uncovered:
            self.stdout.write(self.style.ERROR(
                f"  [FAIL] {len(uncovered)} route(s) MISSING from PERMISSION_MATRIX:"
            ))
            for route in uncovered:
                self.stdout.write(self.style.ERROR(f"      - {route}"))
                if options.get("fix_hint"):
                    # Suggest a template entry
                    hint = (
                        f'    "{route}": {{\n'
                        f'        "hospital_admin": ["GET"],\n'
                        f'        "super_admin": ["GET"],\n'
                        f'    }},'
                    )
                    self.stdout.write(self.style.WARNING(f"    Suggested entry:\n{hint}"))
            self.stdout.write("")

        if unknown_roles:
            self.stdout.write(self.style.ERROR(
                f"  [FAIL] {len(unknown_roles)} unknown role(s) in PERMISSION_MATRIX:"
            ))
            for entry in unknown_roles:
                self.stdout.write(self.style.ERROR(f"      - {entry}"))
            self.stdout.write("")

        if stale:
            style = self.style.WARNING
            prefix = "  [WARN]" if not options["strict"] else "  [FAIL]"
            label = "WARNING" if not options["strict"] else "ERROR"
            self.stdout.write(style(
                f"{prefix} {len(stale)} stale entry(ies) in PERMISSION_MATRIX "
                f"(not mapped to any URL) [{label}]:"
            ))
            for entry in stale:
                self.stdout.write(style(f"      - {entry}"))
            self.stdout.write("")

        self.stdout.write("=" * 60)
        if not uncovered and not unknown_roles:
            self.stdout.write(self.style.SUCCESS("  Result: PASS (warnings only)"))
        else:
            self.stdout.write(self.style.ERROR(
                "  Result: FAIL -- fix uncovered routes before merging"
            ))
        self.stdout.write("")
