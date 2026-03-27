# Minimal migration: adds only Encounter (for existing DBs that already have MedicalRecord, etc.)

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0001_blueprint_alerts_encounters'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Encounter',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('encounter_type', models.CharField(choices=[('outpatient', 'Outpatient'), ('inpatient', 'Inpatient'), ('emergency', 'Emergency'), ('follow_up', 'Follow-up'), ('consultation', 'Consultation'), ('other', 'Other')], default='outpatient', max_length=20)),
                ('encounter_date', models.DateTimeField(auto_now_add=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.hospital')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='patients.patient')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['patient', '-encounter_date'], name='records_enc_patient_fa1f48_idx'),
                    models.Index(fields=['hospital', '-encounter_date'], name='records_enc_hospita_878993_idx'),
                ],
            },
        ),
    ]
