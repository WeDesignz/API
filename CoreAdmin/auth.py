from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from django.contrib.auth.models import User
from .models import AdminUserProfile, AdminActivityLog
from rest_framework import exceptions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta


class AdminJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication for admin users.
    Validates admin permissions and 2FA status.
    """
    
    def get_validated_token(self, raw_token):
        """
        Validates an encoded JSON web token and returns a validated token
        wrapper object.
        """
        messages = []
        for AuthToken in self.get_auth_token_classes():
            try:
                return AuthToken(raw_token)
            except TokenError as e:
                messages.append({'token_class': AuthToken.__name__,
                                'token_type': AuthToken.token_type,
                                'message': e.args[0]})
        
        raise InvalidToken({
            'detail': 'Given token not valid for any token type',
            'messages': messages,
        })
    
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        """
        try:
            user_id = validated_token[self.get_user_id_claim()]
        except KeyError:
            raise InvalidToken('Token contained no recognizable user identification')
        
        try:
            user = self.get_user_model().objects.get(**{self.get_user_id_field(): user_id})
        except self.get_user_model().DoesNotExist:
            raise InvalidToken('User not found')
        
        if not self.get_user_model().objects.filter(pk=user_id).exists():
            raise InvalidToken('User not found')
        
        return user
    
    def authenticate(self, request):
        """
        Returns a two-tuple of `User` and token if authentication is successful.
        Otherwise returns `None`.
        """
        header = self.get_header(request)
        if header is None:
            return None
        
        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
        
        validated_token = self.get_validated_token(raw_token)
        
        # Check if this is an admin token
        if not validated_token.get('admin', False):
            return None
        
        user = self.get_user(validated_token)
        
        if not user:
            return None
        
        # Check if user has admin profile
        try:
            admin_profile = user.admin_profile
        except AdminUserProfile.DoesNotExist:
            return None
        
        # Check if admin profile is active
        if not admin_profile.is_active:
            return None
        
        # Check if 2FA is required and verified recently
        if admin_profile.is_2fa_enabled:
            last_verification = admin_profile.last_2fa_verification
            if not last_verification:
                return None
            
            # Check if 2FA verification is within acceptable time window (24 hours)
            if timezone.now() - last_verification > timedelta(hours=24):
                return None
        
        # Log successful authentication
        AdminActivityLog.log_activity(
            user=user,
            activity_type='login',
            description='Admin API access',
            request=request,
            metadata={'admin_group': admin_profile.admin_group}
        )
        
        return (user, validated_token)


@api_view(['POST'])
@permission_classes([AllowAny])
def admin_token_refresh(request):
    """
    Refresh admin JWT token.
    Validates admin status before refreshing tokens.
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({
                'error': 'Refresh token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        token = RefreshToken(refresh_token)
        
        # Check if this is an admin token
        if not token.get('admin', False):
            return Response({
                'error': 'Invalid admin token'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user and validate admin status
        user_id = token.get('user_id')
        try:
            user = User.objects.get(id=user_id)
            admin_profile = user.admin_profile
            
            if not admin_profile.is_active:
                return Response({
                    'error': 'Admin access deactivated'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check 2FA status if enabled
            if admin_profile.is_2fa_enabled:
                last_verification = admin_profile.last_2fa_verification
                if not last_verification:
                    return Response({
                        'error': '2FA verification required',
                        'detail': 'Please login again to verify 2FA'
                    }, status=status.HTTP_403_FORBIDDEN)
                
                if timezone.now() - last_verification > timedelta(hours=24):
                    return Response({
                        'error': '2FA verification expired',
                        'detail': '2FA verification is valid for 24 hours. Please login again.'
                    }, status=status.HTTP_403_FORBIDDEN)
            
        except (User.DoesNotExist, AdminUserProfile.DoesNotExist):
            return Response({
                'error': 'Invalid user'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update last 2FA verification time on successful refresh (if 2FA is enabled)
        # This extends the 2FA session as long as the user is actively using the app
        if admin_profile.is_2fa_enabled:
            admin_profile.last_2fa_verification = timezone.now()
            admin_profile.save(update_fields=['last_2fa_verification'])
        
        # Generate new tokens
        new_refresh = RefreshToken.for_user(user)
        new_refresh['admin'] = True
        new_refresh['admin_group'] = admin_profile.admin_group
        
        return Response({
            'access': str(new_refresh.access_token),
            'refresh': str(new_refresh)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': 'Token refresh failed'
        }, status=status.HTTP_400_BAD_REQUEST)


def admin_required(admin_group=None, superuser_only=False):
    """
    Decorator to require admin permissions.
    
    Args:
        admin_group: Required admin group ('superadmin' or 'moderator')
        superuser_only: Require superuser status
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user or not request.user.is_authenticated:
                raise exceptions.PermissionDenied('Authentication required')
            
            try:
                admin_profile = request.user.admin_profile
            except AdminUserProfile.DoesNotExist:
                raise exceptions.PermissionDenied('Admin profile required')
            
            if not admin_profile.is_active:
                raise exceptions.PermissionDenied('Admin access deactivated')
            
            # Check superuser requirement
            if superuser_only and not request.user.is_superuser:
                raise exceptions.PermissionDenied('Superuser privileges required')
            
            # Check admin group requirement
            if admin_group and admin_profile.admin_group != admin_group:
                raise exceptions.PermissionDenied(f'{admin_group.title()} privileges required')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def log_admin_activity(activity_type, description, metadata=None):
    """
    Decorator to log admin activities.
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            result = view_func(request, *args, **kwargs)
            
            # Log activity if user is authenticated admin
            if (request.user and 
                request.user.is_authenticated and 
                hasattr(request.user, 'admin_profile')):
                
                AdminActivityLog.log_activity(
                    user=request.user,
                    activity_type=activity_type,
                    description=description,
                    request=request,
                    metadata=metadata or {}
                )
            
            return result
        
        return wrapper
    return decorator
