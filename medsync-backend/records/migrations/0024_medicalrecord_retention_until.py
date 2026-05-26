# Ghana MoH clinical record retention enforcement

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0023_prescription_dispense_workflow"),
    ]

    operations = [
        migrations.AddField(
            model_name="medicalrecord",
            name="retention_until",
            field=models.DateTimeField(
                blank=True,
                help_text="Ghana MoH minimum retention end date (10y adult / 25y paediatric).",
                null=True,
            ),
        ),
    ]
