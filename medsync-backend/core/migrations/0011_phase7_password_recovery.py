# Generated migration for Phase 7: 3-Tier Password Recovery

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_superadminhospitalaccess'),
    ]

    operations = [
        # Add fields to User model
        migrations.AddField(
            model_name='user',
            name='password_reset_token',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='password_reset_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='temp_password',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='temp_password_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='must_change_password_on_login',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='failed_password_reset_attempts',
            field=models.IntegerField(default=0),
        ),
        
        # Create PasswordResetAudit model
        migrations.CreateModel(
            name='PasswordResetAudit',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reset_type', models.CharField(choices=[('self_service', 'User Self-Service'), ('admin_link', 'Admin-Generated Reset Link'), ('temp_password', 'Admin-Generated Temp Password'), ('super_admin_override', 'Super Admin Override')], max_length=20)),
                ('reason', models.TextField(blank=True, help_text='Why reset was initiated (for admin/super-admin resets)', null=True)),
                ('token_issued_at', models.DateTimeField(auto_now_add=True)),
                ('token_expires_at', models.DateTimeField()),
                ('token_used_at', models.DateTimeField(blank=True, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('mfa_verified', models.BooleanField(default=False, help_text='For super admin only')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('completed', 'Completed'), ('expired', 'Expired'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('failure_reason', models.TextField(blank=True, help_text='Reason if status=failed', null=True)),
                ('hospital', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.hospital')),
                ('initiated_by', models.ForeignKey(blank=True, help_text='Admin or super admin who initiated (null for self-service)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='password_resets_initiated', to='core.user')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='password_resets', to='core.user')),
            ],
            options={
                'ordering': ['-token_issued_at'],
            },
        ),
        
        # Add indexes
        migrations.AddIndex(
            model_name='passwordresetaudit',
            index=models.Index(fields=['user', '-token_issued_at'], name='core_passwor_user_id_token_idx'),
        ),
        migrations.AddIndex(
            model_name='passwordresetaudit',
            index=models.Index(fields=['hospital', '-token_issued_at'], name='core_passwor_hospita_token_idx'),
        ),
        migrations.AddIndex(
            model_name='passwordresetaudit',
            index=models.Index(fields=['status'], name='core_passwor_status_idx'),
        ),
    ]
