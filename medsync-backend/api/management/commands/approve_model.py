import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from api.models import ModelVersion
from core.models import User

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Approves an AI model version for clinical use and promotes it to production.'

    def add_arguments(self, parser):
        parser.add_argument('--version-id', type=str, required=True, help='UUID of the ModelVersion')
        parser.add_argument('--approved-by', type=str, required=True, help='Email of the super_admin')
        parser.add_argument('--notes', type=str, required=True, help='Clinical validation notes')

    def handle(self, *args, **options):
        version_id = options['version_id']
        approved_by_email = options['approved_by']
        notes = options['notes']

        try:
            version = ModelVersion.objects.get(id=version_id)
        except ModelVersion.DoesNotExist:
            raise CommandError(f"Model version {version_id} not found.")

        try:
            user = User.objects.get(email=approved_by_email)
            if not user.is_superuser:
                raise CommandError(f"User {approved_by_email} is not a super_admin.")
        except User.DoesNotExist:
            raise CommandError(f"User {approved_by_email} not found.")

        # 1. Update version
        version.clinical_use_approved = True
        version.is_production = True
        version.approved_by = user
        version.approved_at = timezone.now()
        version.approval_notes = notes
        version.save()

        # 2. Demote previous production model of the same type
        ModelVersion.objects.filter(
            model_type=version.model_type,
            is_production=True
        ).exclude(id=version.id).update(is_production=False)

        self.stdout.write(self.style.SUCCESS(
            f"Successfully approved {version.model_type} {version.version_tag} for clinical use. "
            "It is now the active production model."
        ))
        
        logger.info(f"Model {version_id} approved by {approved_by_email}")
