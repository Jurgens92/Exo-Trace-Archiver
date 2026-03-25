from django.apps import AppConfig


class TracesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'traces'
    verbose_name = 'Message Trace Logs'

    def ready(self):
        """
        Start the background scheduler when Django starts.

        The scheduler runs in a daemon thread alongside the server,
        so there's no need to run a separate process.
        """
        from .scheduler import start_scheduler
        start_scheduler()
