from django import template
from django.http import HttpRequest
from django.contrib.auth import get_user_model
from django.contrib.auth.context_processors import PermWrapper

register = template.Library()
User = get_user_model()


@register.simple_tag(takes_context=True)
def sidebar_status_safe(context):
    """
    Safely check if the sidebar is open or closed.
    This is a fix for the Jazzmin sidebar_status template tag issue
    where it sometimes receives a string instead of a request object.
    """
    request = context.get('request')
    
    # Ensure we have a valid request object
    if not isinstance(request, HttpRequest):
        return ""
    
    # Check if sidebar is closed via cookie
    if hasattr(request, 'COOKIES') and request.COOKIES.get("jazzy_menu", "") == "closed":
        return "sidebar-collapse"
    return ""


@register.filter
def can_view_self_safe(perms):
    """
    Safely determines whether a user has sufficient permissions to view its own profile.
    This is a fix for the Jazzmin can_view_self filter issue where perms can be None.
    """
    # Handle None or invalid perms
    if not perms or not isinstance(perms, PermWrapper):
        return False
    
    try:
        view_perm = "view_{}".format(User._meta.model_name)
        return perms[User._meta.app_label][view_perm]
    except (KeyError, AttributeError, TypeError):
        return False

