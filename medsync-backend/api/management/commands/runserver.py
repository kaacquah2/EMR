"""
Custom runserver command that properly configures Daphne for development.

This command wraps Django's default runserver but ensures Daphne (the ASGI server
used for WebSocket support) is configured with proper timeout settings for graceful
shutdown during file reloads.

Without this configuration, rapid file reloads cause "took too long to shut down"
errors because Daphne's default 2-second application close timeout is too short for
pending requests to complete gracefully.

Usage:
    python manage.py runserver                    # Default (0.0.0.0:8000)
    python manage.py runserver 8001              # Custom port
    python manage.py runserver 127.0.0.1:8000    # Custom host:port
"""

import os
from django.core.management.commands.runserver import Command as BaseCommand
from django.conf import settings


class Command(BaseCommand):
    """Custom runserver that applies Daphne timeout configuration."""

    def handle(self, *args, **options):
        """
        Override handle to set Daphne timeout before starting server.

        The DAPHNE_APPLICATION_CLOSE_TIMEOUT from settings.py is passed to
        the ASGI server via environment variable for daphne to pick up.
        """
        timeout = getattr(settings, 'DAPHNE_APPLICATION_CLOSE_TIMEOUT', 5)

        if settings.DEBUG:
            self.stdout.write(
                self.style.SUCCESS(
                    f"🚀 Starting Django development server with Daphne "
                    f"(application_close_timeout={timeout}s)..."
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    "   This allows pending requests to complete gracefully during hot-reload.\n"
                )
            )

        os.environ.setdefault('DAPHNE_APPLICATION_CLOSE_TIMEOUT', str(timeout))

        return super().handle(*args, **options)
