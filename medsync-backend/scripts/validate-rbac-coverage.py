#!/usr/bin/env python
"""
Validate RBAC Coverage Before Commit

This script checks that all API endpoints in api/urls.py are present in
the PERMISSION_MATRIX in shared/permissions.py. It's designed to be used
as a pre-commit hook to prevent accidentally committing new endpoints
without corresponding RBAC permission definitions.

Usage:
    python scripts/validate-rbac-coverage.py
    
Exit Codes:
    0 = All endpoints have permission entries (coverage 100%)
    1 = Some endpoints missing from PERMISSION_MATRIX
    2 = Internal error (can't run validation)

See: shared/permissions.py for PERMISSION_MATRIX structure
See: api/urls.py for registered API routes
"""

import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')

try:
    django.setup()
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    print("   Cannot validate RBAC coverage without Django.")
    sys.exit(2)

def main():
    """Run RBAC coverage test."""
    try:
        from api.tests.test_rbac_coverage import TestAllRoutesHavePermissions
        
        print("🔍 Validating RBAC coverage...")
        test = TestAllRoutesHavePermissions()
        test.test_every_url_has_permission_entry()
        
        print("✅ RBAC coverage valid (100%)")
        print("   All API endpoints have permission matrix entries.")
        return 0
        
    except AssertionError as e:
        print(f"❌ RBAC coverage incomplete:")
        print(f"   {e}")
        print()
        print("   To fix:")
        print("   1. Check api/urls.py for new endpoints")
        print("   2. Add each to PERMISSION_MATRIX in shared/permissions.py")
        print("   3. Use format: 'endpoint/<pk>': { 'GET': ['role1', 'role2'], ... }")
        print("   4. Consult shared/permissions.py for examples")
        print()
        print("   Example:")
        print("   'my-new-endpoint/<pk>': {")
        print("       'GET': ['doctor', 'nurse'],")
        print("       'POST': ['doctor'],")
        print("       'PATCH': ['doctor'],")
        print("   }")
        return 1
        
    except Exception as e:
        print(f"❌ Error validating RBAC coverage:")
        print(f"   {e}")
        print("   This may indicate a problem with the test infrastructure.")
        print("   Run: python manage.py test api.tests.test_rbac_coverage -v 2")
        return 2

if __name__ == '__main__':
    sys.exit(main())
