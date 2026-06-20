from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
    verbose_name = "API"

    def ready(self):
        # signals_alerts.py previously imported channels for WebSocket broadcasts.
        # The app now runs WSGI-only (Gunicorn); channels is not installed and the
        # WS layer has been removed.  The signal receivers (lab results, admissions,
        # prescriptions) are retained but their broadcast functions are now no-ops
        # that log to the standard logger instead.
        import api.signals_alerts  # noqa
        import api.signals_cds  # noqa
        import api.signals_pharmacy  # noqa
        import api.checks  # noqa

        # Run RBAC coverage validation check if fail-closed mode enabled
        from django.conf import settings
        if getattr(settings, "_RBAC_COVERAGE_WARNING_ENABLED", False):
            try:
                from medsync_backend.settings import _validate_rbac_coverage_at_startup
                _validate_rbac_coverage_at_startup()
            except Exception as e:
                import logging
                logging.getLogger("medsync.rbac").warning(
                    f"Could not validate RBAC coverage at startup: {e}"
                )

