from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0030_alter_auditlog_chain_hash_alter_auditlog_signature_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='mfa_method',
            field=models.CharField(choices=[('email', 'Email'), ('totp', 'Authenticator App'), ('passkey', 'Passkey')], default='email', max_length=20),
        ),
        migrations.AddField(
            model_name='user',
            name='totp_grace_period_expires',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
