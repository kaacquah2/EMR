# Generated migration for Emergency Department Triage System

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0010_add_walkin_fields'),
    ]

    operations = [
        # Add triage color code to Appointment
        migrations.AddField(
            model_name='appointment',
            name='triage_color',
            field=models.CharField(
                max_length=10,
                choices=[
                    ('red', 'Red - Immediate'),
                    ('yellow', 'Yellow - Urgent'),
                    ('green', 'Green - Less Urgent'),
                    ('blue', 'Blue - Non-Urgent'),
                ],
                null=True,
                blank=True,
                help_text='Emergency triage color code'
            ),
        ),
        # Add triage assessment time
        migrations.AddField(
            model_name='appointment',
            name='triage_assessed_at',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='When triage assessment was performed'
            ),
        ),
        # Add triaged_by nurse/doctor
        migrations.AddField(
            model_name='appointment',
            name='triaged_by',
            field=models.ForeignKey(
                to='core.User',
                null=True,
                blank=True,
                on_delete=models.SET_NULL,
                related_name='triage_assessments'
            ),
        ),
        # Add chief complaint for triage
        migrations.AddField(
            model_name='appointment',
            name='chief_complaint',
            field=models.TextField(
                blank=True,
                null=True,
                help_text='Patient chief complaint for triage'
            ),
        ),
        # Add vital signs snapshot for triage
        migrations.AddField(
            model_name='appointment',
            name='triage_vitals',
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Vital signs at triage: BP, HR, RR, SpO2, temp, pain_scale'
            ),
        ),
        # Add wait time tracking
        migrations.AddField(
            model_name='appointment',
            name='ed_arrival_time',
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text='Time patient arrived in ED'
            ),
        ),
        migrations.AddField(
            model_name='appointment',
            name='ed_room_assignment',
            field=models.CharField(
                max_length=20,
                blank=True,
                null=True,
                help_text='ED room/bed number'
            ),
        ),
    ]
