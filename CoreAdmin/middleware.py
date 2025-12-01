from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import re


class ModeratorRestrictionMiddleware(MiddlewareMixin):
    """
    Middleware to restrict moderator access to certain URLs and views.
    Only superusers can access all admin functionality.
    """
    
    # URLs that only superusers can access
    SUPERUSER_ONLY_URLS = [
        r'^/api/coreadmin/users/',
        r'^/api/coreadmin/activity-logs/',
        r'^/api/coreadmin/sessions/',
        r'^/api/coreadmin/system/',
        r'^/api/coreadmin/analytics/',
        r'^/api/coreadmin/reports/',
        r'^/api/coreadmin/export/',
        r'^/api/coreadmin/import/',
        r'^/api/coreadmin/settings/',
        r'^/api/coreadmin/logs/',
    ]
    
    # URLs that moderators can access
    MODERATOR_ALLOWED_URLS = [
        r'^/api/coreadmin/login/',
        r'^/api/coreadmin/logout/',
        r'^/api/coreadmin/2fa/',
        r'^/api/coreadmin/profile/',
        r'^/api/coreadmin/change-password/',
        r'^/api/coreadmin/dashboard/',
        r'^/api/coreadmin/content/',
        r'^/api/coreadmin/products/',
        r'^/api/coreadmin/orders/',
        r'^/api/coreadmin/customers/',
    r'^/api/coreadmin/designs/',
    r'^/api/coreadmin/categories/',
    r'^/api/coreadmin/tags/',
    r'^/api/coreadmin/copyright-reports/',
    r'^/api/coreadmin/transactions/',
    r'^/api/coreadmin/refunds/',
    r'^/api/coreadmin/orders/',
    r'^/api/coreadmin/financial-reports/',
    r'^/api/coreadmin/custom-orders/',
    r'^/api/coreadmin/subscription-plans/',
        r'^/api/coreadmin/feedback/',
        r'^/api/coreadmin/designers/',
        r'^/api/coreadmin/designers/onboarding/',
        r'^/api/coreadmin/designers/payouts/',
    ]
    
    def process_request(self, request):
        """
        Check if the request is to a restricted URL and apply moderator restrictions.
        """
        # Skip middleware for non-admin URLs
        if not request.path.startswith('/api/coreadmin/'):
            return None
        
        # Skip middleware for authentication endpoints
        if request.path in ['/api/coreadmin/login/', '/api/coreadmin/2fa/verify/']:
            return None
        
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return None
        
        # Check if user has admin profile
        try:
            admin_profile = request.user.admin_profile
        except:
            return None
        
        # Superusers can access everything
        if request.user.is_superuser:
            return None
        
        # Check if user is a moderator
        if admin_profile.admin_group == 'moderator':
            # Check if URL is restricted for moderators
            if self._is_restricted_url(request.path):
                return JsonResponse({
                    'error': 'Access denied. This functionality is restricted to superusers only.',
                    'message': 'You do not have permission to access this resource.'
                }, status=403)
        
        return None
    
    def _is_restricted_url(self, path):
        """
        Check if the URL is restricted for moderators.
        """
        # Check superuser-only URLs
        for pattern in self.SUPERUSER_ONLY_URLS:
            if re.match(pattern, path):
                return True
        
        # Check if URL is in moderator allowed list
        for pattern in self.MODERATOR_ALLOWED_URLS:
            if re.match(pattern, path):
                return False
        
        # If URL doesn't match any pattern, it's restricted for moderators
        return True
    
    def process_response(self, request, response):
        """
        Add admin group information to response headers for debugging.
        """
        if (request.path.startswith('/api/coreadmin/') and 
            request.user and 
            request.user.is_authenticated):
            
            try:
                admin_profile = request.user.admin_profile
                response['X-Admin-Group'] = admin_profile.admin_group
                response['X-Admin-2FA-Enabled'] = str(admin_profile.is_2fa_enabled)
            except:
                pass
        
        return response


class AdminActivityLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to automatically log admin activities.
    """
    
    def process_request(self, request):
        """
        Store request information for activity logging.
        """
        if request.path.startswith('/api/coreadmin/'):
            request._admin_activity_logged = False
    
    def process_response(self, request, response):
        """
        Log admin activities for API requests.
        """
        if (request.path.startswith('/api/coreadmin/') and 
            request.user and 
            request.user.is_authenticated and
            not getattr(request, '_admin_activity_logged', False)):
            
            try:
                from .models import AdminActivityLog
                
                # Determine activity type based on URL and method
                activity_type = self._get_activity_type(request)
                description = self._get_activity_description(request)
                
                # Log the activity
                AdminActivityLog.log_activity(
                    user=request.user,
                    activity_type=activity_type,
                    description=description,
                    request=request,
                    metadata={
                        'method': request.method,
                        'path': request.path,
                        'status_code': response.status_code
                    }
                )
                
                request._admin_activity_logged = True
            except Exception:
                # Don't let logging errors break the request
                pass
        
        return response
    
    def _get_activity_type(self, request):
        """
        Determine activity type based on request.
        """
        path = request.path.lower()
        method = request.method.upper()
        
        if 'login' in path:
            return 'login'
        elif 'logout' in path:
            return 'logout'
        elif '2fa' in path:
            return '2fa_verify'
        elif 'password' in path:
            return 'password_change'
        elif 'profile' in path:
            return 'profile_update'
        elif method in ['POST', 'PUT', 'PATCH']:
            return 'system_config'
        elif method == 'GET':
            return 'other'
        else:
            return 'other'
    
    def _get_activity_description(self, request):
        """
        Generate activity description based on request.
        """
        method = request.method.upper()
        path = request.path
        
        if method == 'GET':
            return f"Viewed {path}"
        elif method == 'POST':
            return f"Created/Performed action on {path}"
        elif method in ['PUT', 'PATCH']:
            return f"Updated {path}"
        elif method == 'DELETE':
            return f"Deleted {path}"
        else:
            return f"Accessed {path}"
