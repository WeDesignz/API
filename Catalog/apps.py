from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Catalog'
    
    def ready(self):
        # Import tasks to ensure they are registered with Celery
        # This is called after Django is fully initialized
        try:
            import Catalog.tasks  # noqa
        except ImportError:
            pass