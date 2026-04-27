# Generated migration for EncounterDraft model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0009_laborder_state_machine_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='EncounterDraft',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('draft_data', models.JSONField(default=dict)),
                ('last_saved_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='draft_encounters', to=settings.AUTH_USER_MODEL)),
                ('encounter', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='draft', to='records.encounter')),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.hospital')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='encounter_drafts', to='patients.patient')),
            ],
            options={
                'db_table': 'records_encounter_draft',
            },
        ),
        migrations.AddIndex(
            model_name='encounterdraft',
            index=models.Index(fields=['patient', 'hospital'], name='records_enc_patient_hospital_idx'),
        ),
        migrations.AddIndex(
            model_name='encounterdraft',
            index=models.Index(fields=['created_by', 'last_saved_at'], name='records_enc_user_saved_idx'),
        ),
    ]
