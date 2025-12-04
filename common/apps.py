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
        # Patch Jazzmin template tags to fix errors
        self._patch_jazzmin_tags()
    
    def _patch_jazzmin_tags(self):
        """Patch Jazzmin template tags to handle edge cases."""
        try:
            from jazzmin.templatetags import jazzmin
            from django.http import HttpRequest
            from django.contrib.auth.context_processors import PermWrapper
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            # Patch sidebar_status to handle string instead of request object
            # The function signature must match the original: takes request as argument
            def patched_sidebar_status(request, *args, **kwargs):
                """Safely check if sidebar is open or closed."""
                # Handle case where request might be a string or invalid
                if not isinstance(request, HttpRequest):
                    return ""
                if hasattr(request, 'COOKIES') and request.COOKIES.get("jazzy_menu", "") == "closed":
                    return "sidebar-collapse"
                return ""
            
            # Patch can_view_self to handle None perms
            def patched_can_view_self(perms):
                """Safely determine if user can view their own profile."""
                if not perms or not isinstance(perms, PermWrapper):
                    return False
                try:
                    view_perm = "view_{}".format(User._meta.model_name)
                    return perms[User._meta.app_label][view_perm]
                except (KeyError, AttributeError, TypeError):
                    return False
            
            # Replace the functions in the module
            # This works because Django template tags call these functions directly
            jazzmin.sidebar_status = patched_sidebar_status
            jazzmin.can_view_self = patched_can_view_self
            
            # Get the register and properly re-register the tags/filters
            register = jazzmin.register
            
            # For sidebar_status, unregister the old one and re-register with our patched function
            if hasattr(register, 'tags') and 'sidebar_status' in register.tags:
                del register.tags['sidebar_status']
            # Re-register as a simple_tag (which is how it was originally registered)
            register.simple_tag(patched_sidebar_status, name='sidebar_status')
            
            # For can_view_self filter, unregister and re-register
            if hasattr(register, 'filters') and 'can_view_self' in register.filters:
                del register.filters['can_view_self']
            # Re-register the filter - filters are registered by assigning to the dict
            register.filters['can_view_self'] = patched_can_view_self
            
        except (ImportError, AttributeError) as e:
            # If Jazzmin is not installed or tags don't exist, silently fail
            pass
