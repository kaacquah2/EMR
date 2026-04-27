#!/bin/bash
# MedSync EMR Test Suite Runner
# Tasks T4-T7: Security Hardening & State Machine Testing

set -e  # Exit on error

echo "================================"
echo "MedSync EMR Test Suite (T4-T7)"
echo "================================"
echo ""

cd "$(dirname "$0")/medsync-backend" || exit 1

echo "1. Running Referral State Machine Tests..."
echo "==========================================="
python -m pytest api/tests/test_referral_state_machine.py -v --tb=short
echo ""

echo "2. Running Consent Scoping Tests..."
echo "===================================="
python -m pytest api/tests/test_consent_scoping.py -v --tb=short
echo ""

echo "3. Running Break-Glass Emergency Access Tests..."
echo "================================================="
python -m pytest api/tests/test_break_glass.py -v --tb=short
echo ""

echo "4. Summary: Settings Verification..."
echo "====================================="
python -c "
from django.conf import settings
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
django.setup()

print('✅ CORS Configuration:')
print(f'   - CORS_ALLOWED_ORIGINS: {settings.CORS_ALLOWED_ORIGINS}')
print(f'   - DEBUG: {settings.DEBUG}')
print(f'   - SECURE_SSL_REDIRECT: {settings.SECURE_SSL_REDIRECT}')
print()
print('✅ Security Headers:')
print(f'   - SECURE_CONTENT_TYPE_NOSNIFF: {settings.SECURE_CONTENT_TYPE_NOSNIFF}')
print(f'   - SECURE_BROWSER_XSS_FILTER: {settings.SECURE_BROWSER_XSS_FILTER}')
print(f'   - SECURE_REFERRER_POLICY: {settings.SECURE_REFERRER_POLICY}')
print()
print('✅ WebAuthn Configuration:')
print(f'   - WEBAUTHN_RP_ID: {settings.WEBAUTHN_RP_ID}')
print(f'   - WEBAUTHN_ORIGIN: {settings.WEBAUTHN_ORIGIN}')
print(f'   - WEBAUTHN_ENABLED: {settings.WEBAUTHN_ENABLED}')
print()
print('✅ Break-Glass Configuration:')
print(f'   - BREAK_GLASS_WINDOW_MINUTES: {settings.BREAK_GLASS_WINDOW_MINUTES}')
"

echo ""
echo "✅ All tests completed successfully!"
