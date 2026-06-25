from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_remove_tasksubmission_userpushsubscription"),
    ]

    operations = [
        # User.hospital: CASCADE → SET_NULL (hospital deletion preserves users)
        migrations.AlterField(
            model_name="user",
            name="hospital",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="core.hospital",
            ),
        ),
        # AuditLog.user: CASCADE → SET_NULL (user deletion preserves compliance trail)
        migrations.AlterField(
            model_name="auditlog",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # PasswordResetAudit.user: CASCADE → SET_NULL (audit records survive user deletion)
        migrations.AlterField(
            model_name="passwordresetaudit",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="password_resets",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
