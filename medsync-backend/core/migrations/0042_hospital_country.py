"""
Add Hospital.country (ISO 3166-1 alpha-2, default "GH").

This field is required for NDPA 2012 data-residency enforcement:
can_access_cross_facility() and cross_facility_records() compare
facility.country against GlobalPatient.data_residency_country to decide
whether a cross-facility or cross-border access is permitted.

Previously both enforcement paths read a non-existent attribute
(Hospital.country / Hospital.country_code), causing one path to always
hard-deny and the other to always no-op.  This migration makes the field
real and sets every existing facility to "GH" (Ghana) as the correct default.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_delete_userpushsubscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="hospital",
            name="country",
            field=models.CharField(
                default="GH",
                max_length=2,
                help_text=(
                    "ISO 3166-1 alpha-2 country code for this facility (e.g. 'GH' for Ghana). "
                    "Used for NDPA data-residency enforcement."
                ),
            ),
        ),
    ]
