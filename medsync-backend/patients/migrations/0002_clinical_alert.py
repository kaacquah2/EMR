# Minimal migration: adds only ClinicalAlert (for existing DBs that already have Patient, Allergy, PatientAdmission)

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_blueprint_alerts_encounters'),
        ('patients', '0001_blueprint_alerts_encounters'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ClinicalAlert',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('severity', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], default='medium', max_length=20)),
                ('message', models.TextField()),
                ('status', models.CharField(choices=[('active', 'Active'), ('resolved', 'Resolved'), ('dismissed', 'Dismissed')], default='active', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('resource_type', models.CharField(blank=True, max_length=50, null=True)),
                ('resource_id', models.UUIDField(blank=True, null=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='core.hospital')),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='patients.patient')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['hospital', 'status', '-created_at'], name='patients_cl_hospita_d255b0_idx'),
                ],
            },
        ),
    ]
