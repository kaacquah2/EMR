from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    verbose_name = "API"

    def ready(self):
        import api.signals_alerts  # noqa
        import api.signals_cds  # noqa
        import api.signals_pharmacy  # noqa
        import api.checks  # noqa

        # Production safety guard for LLM mode
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured
        if getattr(settings, 'ENV', '').lower() == 'production' and getattr(settings, 'LLM_MODE', '') == 'mock':
            raise ImproperlyConfigured(
                "LLM_MODE=mock is not allowed when ENV=production. "
                "AI differential diagnosis and risk predictions will return fake data."
            )

