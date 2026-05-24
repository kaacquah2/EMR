from django.core.checks import Error, register

@register()
def check_bypass_emails_guard(app_configs, **kwargs):
    from django.conf import settings
    errors = []
    bypass = getattr(settings, 'DEV_PERMISSION_BYPASS_EMAILS', None)
    if bypass and not settings.DEBUG:
        errors.append(
            Error(
                "CRITICAL SECURITY RISK: DEV_PERMISSION_BYPASS_EMAILS is set while DEBUG is False.",
                id="security.E001",
            )
        )
    return errors
