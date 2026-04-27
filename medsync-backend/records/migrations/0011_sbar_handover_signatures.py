# Generated migration for SBAR Handover with Dual Signatures

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_add_password_reset_attempt_model'),
        ('patients', '0008_encrypt_phi_fields'),
        ('records', '0010_encounter_draft'),
    ]

    operations = [
        # Add SBAR fields
        migrations.AddField(
            model_name='shifthandover',
            name='sbar_situation',
            field=models.TextField(
                blank=True, default='',
                help_text='Current patient status, vitals, recent changes'
            ),
        ),
        migrations.AddField(
            model_name='shifthandover',
            name='sbar_background',
            field=models.TextField(
                blank=True, default='',
                help_text='Patient history, admission reason, relevant context'
            ),
        ),
        migrations.AddField(
            model_name='shifthandover',
            name='sbar_assessment',
            field=models.TextField(
                blank=True, default='',
                help_text='Current clinical assessment and concerns'
            ),
        ),
        migrations.AddField(
            model_name='shifthandover',
            name='sbar_recommendation',
            field=models.TextField(
                blank=True, default='',
                help_text='Recommended actions for incoming nurse'
            ),
        ),
        
        # Add incoming nurse field (dual signature)
        migrations.AddField(
            model_name='shifthandover',
            name='incoming_nurse',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='handovers_received',
                to=settings.AUTH_USER_MODEL,
                help_text='Incoming nurse assigned to receive this handover'
            ),
        ),
        
        # Add incoming acknowledgement timestamp (second signature)
        migrations.AddField(
            model_name='shifthandover',
            name='incoming_acknowledged_at',
            field=models.DateTimeField(
                blank=True, null=True,
                help_text='Incoming nurse acknowledgement timestamp (second signature)'
            ),
        ),
        
        # Add outgoing_signed_at as new field (submitted_at remains for compatibility)
        migrations.AddField(
            model_name='shifthandover',
            name='outgoing_signed_at',
            field=models.DateTimeField(
                auto_now_add=True, null=True,
                help_text='Outgoing nurse submission timestamp'
            ),
        ),
        
        # Add new indexes
        migrations.AddIndex(
            model_name='shifthandover',
            index=models.Index(
                fields=['incoming_nurse', 'incoming_acknowledged_at'],
                name='records_shifthandover_incoming_ack_idx'
            ),
        ),
    ]


