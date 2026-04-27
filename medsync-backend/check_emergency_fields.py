#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
django.setup()

from patients.models import Appointment

print("Appointment model fields:")
for field in Appointment._meta.get_fields():
    if any(keyword in field.name for keyword in ['triage', 'ed_', 'chief_complaint']):
        print(f"  - {field.name}: {type(field).__name__}")

# Try to check all fields
all_fields = [f.name for f in Appointment._meta.get_fields()]
print(f"\nTotal fields: {len(all_fields)}")
print("\nLast 10 fields:")
for fname in sorted(all_fields)[-10:]:
    print(f"  - {fname}")
