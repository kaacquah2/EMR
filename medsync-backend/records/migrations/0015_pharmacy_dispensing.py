# Generated migration for Pharmacy Dispensing System

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0014_incident_medicationadministration_and_more'),
        ('core', '0001_initial'),
    ]

    operations = [
        # Add pharmacy workflow fields to Prescription
        migrations.AddField(
            model_name='prescription',
            name='dispensed_at',
            field=models.DateTimeField(null=True, blank=True, help_text='Timestamp when medication was dispensed'),
        ),
        migrations.AddField(
            model_name='prescription',
            name='dispensed_by',
            field=models.ForeignKey(
                'core.User',
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name='dispensed_prescriptions',
                help_text='Pharmacy technician who dispensed medication'
            ),
        ),
        migrations.AddField(
            model_name='prescription',
            name='dispensed_quantity',
            field=models.PositiveIntegerField(null=True, blank=True, help_text='Quantity dispensed'),
        ),
        migrations.AddField(
            model_name='prescription',
            name='dispense_notes',
            field=models.TextField(blank=True, null=True, help_text='Pharmacy dispensing notes'),
        ),
        migrations.AddField(
            model_name='prescription',
            name='priority',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('routine', 'Routine'),
                    ('urgent', 'Urgent'),
                    ('stat', 'STAT'),
                ],
                default='routine',
                help_text='Prescription priority level'
            ),
        ),
        migrations.AddField(
            model_name='prescription',
            name='drug_interaction_checked',
            field=models.BooleanField(default=False, help_text='Whether drug interactions were checked'),
        ),
        migrations.AddField(
            model_name='prescription',
            name='drug_interactions',
            field=models.JSONField(null=True, blank=True, help_text='Detected drug-drug interactions'),
        ),
        
        # Add index for pharmacy worklist
        migrations.AddIndex(
            model_name='prescription',
            index=models.Index(fields=['hospital', 'status', 'priority', '-created_at'], name='rx_pharmacy_queue_idx'),
        ),
    ]
