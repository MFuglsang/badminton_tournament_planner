from django.apps import AppConfig


class TournamentsConfig(AppConfig):
    """Configure Django settings for the tournaments app."""

    name = 'tournaments'

    def ready(self):
        """Import signal handlers when Django starts the app."""
        import tournaments.signals  # noqa
