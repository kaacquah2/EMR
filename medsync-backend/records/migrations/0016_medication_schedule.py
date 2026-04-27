# Generated migration for Medication Administration Record (MAR) Schedule System

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0015_pharmacy_dispensing'),
        ('core', '0001_initial'),
        ('patients', '0001_blueprint_alerts_encounters'),
    ]

    operations = [
        migrations.CreateModel(
            name='MedicationSchedule',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('scheduled_time', models.DateTimeField(help_text='When medication should be given')),
                ('actual_time', models.DateTimeField(null=True, blank=True, help_text='When medication was actually administered')),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('scheduled', 'Scheduled'),
                        ('administered', 'Administered'),
                        ('missed', 'Missed'),
                        ('held', 'Held'),
                        ('refused', 'Refused'),
                    ],
                    default='scheduled',
                    help_text='Current status of the scheduled dose'
                )),
                ('hold_reason', models.TextField(null=True, blank=True, help_text='Reason for holding the medication')),
                ('refused_reason', models.TextField(null=True, blank=True, help_text='Reason patient refused medication')),
                ('notes', models.TextField(null=True, blank=True, help_text='Additional administration notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('prescription', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='schedules',
                    to='records.prescription'
                )),
                ('patient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='medication_schedules',
                    to='patients.patient'
                )),
                ('hospital', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='medication_schedules',
                    to='core.hospital'
                )),
                ('administered_by', models.ForeignKey(
                    null=True,
                    blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='administered_schedules',
                    to='core.user'
                )),
            ],
            options={
                'db_table': 'records_medication_schedule',
                'ordering': ['scheduled_time'],
            },
        ),
        migrations.AddIndex(
            model_name='medicationschedule',
            index=models.Index(
                fields=['hospital', 'scheduled_time', 'status'],
                name='mar_hospital_sched_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='medicationschedule',
            index=models.Index(
                fields=['patient', 'scheduled_time'],
                name='mar_patient_sched_idx'
            ),
        ),
    ]
