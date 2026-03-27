#!/usr/bin/env python
"""Grant super admin access to all hospitals (for development)."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
django.setup()

from core.models import User, Hospital, SuperAdminHospitalAccess

admin = User.objects.filter(email='admin@medsync.gh').first()
if admin:
    hospitals = Hospital.objects.filter(is_active=True)
    count = 0
    for h in hospitals:
        _, created = SuperAdminHospitalAccess.objects.get_or_create(
            super_admin=admin,
            hospital=h,
            defaults={"granted_by": None}
        )
        if created:
            count += 1
            print(f"  Granted access to: {h.name}")
    
    total_access = SuperAdminHospitalAccess.objects.filter(super_admin=admin).count()
    print(f"\nAdmin now has access to {total_access} hospitals")
else:
    print("Admin not found!")
