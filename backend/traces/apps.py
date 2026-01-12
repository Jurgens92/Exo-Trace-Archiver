from django.apps import AppConfig


class TracesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'traces'
    verbose_name = 'Message Trace Logs'

    def ready(self):
        """
        Initialize the app - this is called once when Django starts.
        We could start the scheduler here, but for production it's better
        to run the scheduler as a separate process or use celery.
        """
        pass
