# Generated manually for NDPA consent withdrawal audit trail

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("interop", "0012_consentscope_consent_excluded_scopes"),
    ]

    operations = [
        migrations.AddField(
            model_name="consent",
            name="withdrawn_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="consent",
            name="withdrawal_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="consent",
            name="withdrawn_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="consents_withdrawn",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
