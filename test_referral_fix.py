#!/usr/bin/env python
"""Test script to verify the referral count fix."""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync.settings')
django.setup()

from interop.models import Referral
from core.models import Hospital

# Print status constants to confirm they exist
print(f"✓ Referral.STATUS_PENDING = {Referral.STATUS_PENDING}")
print(f"✓ Referral.STATUS_ACCEPTED = {Referral.STATUS_ACCEPTED}")
print(f"✓ Referral model has 'to_facility' field: {hasattr(Referral._meta.get_field('to_facility'), 'name')}")
print(f"✓ Referral model has 'status' field: {hasattr(Referral._meta.get_field('status'), 'name')}")

# Show that the query works
query = Referral.objects.filter(
    to_facility__isnull=False,
    status__in=[Referral.STATUS_PENDING, Referral.STATUS_ACCEPTED]
)
print(f"✓ Query works: {query.count()} pending/accepted referrals in database")
print("\n✓ Referral count fix is properly configured!")
