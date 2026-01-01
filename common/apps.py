from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'common'
    verbose_name = 'Common Utilities'
    
    def ready(self):
        """Import signals and tasks when the app is ready."""
        import common.signals
        # Import tasks to ensure they are registered with Celery
        try:
            import common.tasks  # noqa
        except ImportError:
            pass
