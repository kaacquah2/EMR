# Generated for HIGH-5 fix: Password reset rate limiting

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_add_mfa_failure_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='PasswordResetAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('attempted_at', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-attempted_at'],
                'indexes': [
                    models.Index(fields=['email', '-attempted_at'], name='core_passwor_email_cb02e7_idx'),
                ],
            },
        ),
    ]
