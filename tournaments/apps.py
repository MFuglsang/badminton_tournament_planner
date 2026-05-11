from django.apps import AppConfig


class TournamentsConfig(AppConfig):
    """Configure Django settings for the tournaments app."""

    name = 'tournaments'

    def ready(self):
        """Import signal handlers when Django starts the app.

        Returns:
            None: This hook only ensures signal registration.
        """
        import tournaments.signals  # noqa
