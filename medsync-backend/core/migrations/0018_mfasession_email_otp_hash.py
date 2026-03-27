from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_superadminhospitalaccess_accepted_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="mfasession",
            name="email_otp_hash",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
