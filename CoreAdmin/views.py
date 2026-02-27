from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken  # type: ignore
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.core.exceptions import PermissionDenied
import uuid

from .models import AdminUserProfile, AdminActivityLog, AdminSession, DesignerNotification, CustomerNotification, AdminNotificationCampaign, AdminPermissionGroup
from .serializers import (
    AdminLoginSerializer,
    Admin2FASetupSerializer,
    Admin2FAVerifySerializer,
    Admin2FAEnableSerializer,
    Admin2FADisableSerializer,
    AdminLogoutSerializer,
    AdminProfileSerializer,
    AdminActivityLogSerializer,
    AdminSessionSerializer,
    AdminUserCreateSerializer,
    AdminUserUpdateSerializer,
    AdminUserListSerializer,
    AdminUserPasswordResetSerializer,
    AdminPasswordChangeSerializer,
    AdminNotificationCreateSerializer,
    AdminPermissionGroupSerializer,
    AdminPermissionGroupListSerializer,
    PDFClientSerializer,
    PDFClientJobStatusSerializer,
    PDFClientJobCreateSerializer,
)
from Profiles.serializers import (
    DesignerManagementSerializer, DesignerDetailSerializer, DesignerWalletSerializer,
    DesignerTransactionSerializer, DesignerWithdrawalSerializer,
    DesignerAccountSuspensionSerializer, DesignerNotificationSerializer, DesignerOnboardingVerificationSerializer,
    DesignerAccountActionSerializer, DesignerWalletSummarySerializer
)
from Authentication.serializers import (
    CustomerListSerializer, CustomerDetailSerializer, CustomerHistorySerializer,
    CustomerAccountActionSerializer, CustomerViewHistorySerializer, CustomerDownloadHistorySerializer,
    CustomerNotificationSerializer, CustomerSearchSerializer, CustomerAnalyticsSerializer
)
from Catalog.serializers import (
    DesignListSerializer, DesignDetailSerializer, BundleListSerializer, BundleDetailSerializer,
    DesignActionSerializer, CategorySerializer, TagSerializer, CopyrightReportSerializer,
    CopyrightReportActionSerializer, DesignAnalyticsSerializer, DesignAnalyticsFilterSerializer,
    DesignSearchSerializer
)
from Orders.serializers import (
    TransactionListSerializer, TransactionDetailSerializer, RefundRequestSerializer,
    RefundListSerializer, OrderListSerializer, OrderDetailSerializer, OrderStatusUpdateSerializer,
    FinancialReportSerializer, FinancialReportDataSerializer, TransactionFilterSerializer,
    OrderFilterSerializer, RefundFilterSerializer
)
from django.db.models import Q, Sum, Count
from django.contrib.auth.models import User
from django.http import FileResponse
from django.core.paginator import Paginator
from datetime import timedelta
import os
import re
import logging

from Profiles.models import DesignerProfile
from Wallet.models import Wallet, WalletTransaction, WalletWithdrawalRequest
from Authentication.user_relations import get_user_wallets
from common.relations import get_related
from Catalog.models import PDFDownload, PDFClient, PDFClientJob

@swagger_auto_schema(
    method='post',
    operation_summary="Admin Login (Step 1)",
    operation_description="Admin login with email and password. Returns temporary token for 2FA verification.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='Admin email address',
                example='admin@wedesignz.com'
            ),
            'password': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Admin password',
                example='admin123'
            )
        },
        required=['email', 'password']
    ),
    responses={
        200: openapi.Response(
            description="Login successful - 2FA required",
            examples={
                "application/json": {
                    "message": "Login successful. 2FA verification required.",
                    "user": {
                        "id": 1,
                        "email": "admin@wedesignz.com",
                        "first_name": "Admin",
                        "last_name": "User"
                    },
                    "temp_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                    "requires_2fa": True
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid credentials")
    },
    tags=['CoreAdmin Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """
    Admin login - Step 1: Email/Password authentication.
    Returns temporary token for 2FA verification if 2FA is enabled.
    Otherwise, returns full tokens directly.
    """
    serializer = AdminLoginSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        admin_profile = serializer.validated_data['admin_profile']
        
        # Check if 2FA is enabled
        if admin_profile.is_2fa_enabled:
            # 2FA is enabled - require verification
            # Generate temporary token (short-lived)
            temp_refresh = RefreshToken.for_user(user)
            temp_refresh['admin_temp'] = True
            temp_refresh['admin_id'] = user.id
            
            # Log login attempt
            AdminActivityLog.log_activity(
                user=user,
                activity_type='login',
                description='Admin login attempt - 2FA required',
                request=request,
                metadata={'step': 'email_password', '2fa_enabled': True}
            )
            
            return Response({
                'message': 'Login successful. 2FA verification required.',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'admin_group': admin_profile.get_admin_group_display()
                },
                'temp_token': str(temp_refresh.access_token),
                'requires_2fa': True
            }, status=status.HTTP_200_OK)
        else:
            # 2FA is NOT enabled - allow direct login
            # Generate full JWT tokens
            refresh = RefreshToken.for_user(user)
            refresh['admin'] = True
            refresh['admin_group'] = admin_profile.admin_group
            
            # Create admin session
            session_key = str(uuid.uuid4())
            admin_session = AdminSession.objects.create(
                user_id=user.id,
                session_key=session_key,
                ip_address=AdminActivityLog.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                is_active=True
            )
            admin_session.set_user(user)
            
            # Log successful login
            AdminActivityLog.log_activity(
                user=user,
                activity_type='login',
                description='Admin login successful without 2FA',
                request=request,
                metadata={'step': 'email_password', '2fa_enabled': False}
            )
            
            return Response({
                'message': 'Login successful',
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'admin_group': admin_profile.get_admin_group_display()
                },
                'permissions': admin_profile.permissions or [],
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                },
                'requires_2fa': False
            }, status=status.HTTP_200_OK)
    
    # Format serializer errors for better frontend handling
    error_message = None
    if serializer.errors:
        # Get the first error message from any field
        for field, errors in serializer.errors.items():
            if errors:
                # Extract the actual error message string from ErrorDetail objects
                if isinstance(errors, list):
                    error_message = str(errors[0]) if errors else None
                else:
                    error_message = str(errors)
                if error_message:
                    break
    
    return Response({
        'error': error_message or 'Invalid email or password. Please check your credentials and try again.',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_summary="Admin 2FA Setup",
    operation_description="Setup 2FA for admin user. Generates QR code and secret key.",
    responses={
        200: openapi.Response(
            description="2FA setup data generated",
            examples={
                "application/json": {
                    "user_id": 1,
                    "email": "admin@wedesignz.com",
                    "secret_key": "JBSWY3DPEHPK3PXP",
                    "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
                    "backup_codes": ["ABC12345", "DEF67890", "..."]
                }
            }
        )
    },
    tags=['CoreAdmin Authentication']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_2fa_setup(request):
    """
    Setup 2FA for admin user.
    Generates QR code and secret key for authenticator app.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'User does not have admin profile'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = Admin2FASetupSerializer(request.user)
    data = serializer.to_representation(request.user)
    
    # Log 2FA setup
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='2fa_setup',
        description='2FA setup initiated',
        request=request
    )
    
    return Response(data, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='post',
    operation_summary="Admin 2FA Verification",
    operation_description="Verify 2FA code during login. Returns final JWT tokens.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'user_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='User ID from login response',
                example=1
            ),
            'totp_code': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='6-digit TOTP code from authenticator app',
                example='123456'
            )
        },
        required=['user_id', 'totp_code']
    ),
    responses={
        200: openapi.Response(
            description="2FA verification successful",
            examples={
                "application/json": {
                    "message": "Login successful",
                    "user": {
                        "id": 1,
                        "email": "admin@wedesignz.com",
                        "first_name": "Admin",
                        "last_name": "User",
                        "admin_group": "Super Admin"
                    },
                    "tokens": {
                        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
                    }
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid TOTP code")
    },
    tags=['CoreAdmin Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def admin_2fa_verify(request):
    """
    Admin 2FA verification - Step 2: TOTP verification.
    Returns final JWT tokens upon successful verification.
    """
    serializer = Admin2FAVerifySerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        admin_profile = serializer.validated_data['admin_profile']
        
        # Update last 2FA verification time
        admin_profile.last_2fa_verification = timezone.now()
        admin_profile.save()
        
        # Generate final JWT tokens
        refresh = RefreshToken.for_user(user)
        refresh['admin'] = True
        refresh['admin_group'] = admin_profile.admin_group
        
        # Create admin session
        session_key = str(uuid.uuid4())
        admin_session = AdminSession.objects.create(
            user_id=user.id,
            session_key=session_key,
            ip_address=AdminActivityLog.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            is_active=True
        )
        # Create the relation
        admin_session.set_user(user)
        
        # Log successful login
        AdminActivityLog.log_activity(
            user=user,
            activity_type='login',
            description='Admin login successful with 2FA',
            request=request,
            metadata={'step': '2fa_verified'}
        )
        
        return Response({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'admin_group': admin_profile.get_admin_group_display()
            },
            'permissions': admin_profile.permissions or [],
            'tokens': {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary="Enable 2FA",
    operation_description="Enable 2FA for admin user after setup.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'totp_code': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='6-digit TOTP code from authenticator app',
                example='123456'
            )
        },
        required=['totp_code']
    ),
    responses={
        200: openapi.Response(
            description="2FA enabled successfully",
            examples={
                "application/json": {
                    "message": "2FA enabled successfully",
                    "backup_codes": ["ABC12345", "DEF67890", "..."]
                }
            }
        )
    },
    tags=['CoreAdmin Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_2fa_enable(request):
    """
    Enable 2FA for admin user.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'User does not have admin profile'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = Admin2FAEnableSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        backup_codes = serializer.validated_data['backup_codes']
        
        # Log 2FA enable
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='2fa_setup',
            description='2FA enabled successfully',
            request=request
        )
        
        return Response({
            'message': '2FA enabled successfully',
            'backup_codes': backup_codes
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary="Disable 2FA",
    operation_description="Disable 2FA for admin user.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'password': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Current password for verification',
                example='admin123'
            )
        },
        required=['password']
    ),
    responses={
        200: openapi.Response(description="2FA disabled successfully")
    },
    tags=['CoreAdmin Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_2fa_disable(request):
    """
    Disable 2FA for admin user.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'User does not have admin profile'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = Admin2FADisableSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        # Disable 2FA
        admin_profile.is_2fa_enabled = False
        admin_profile.two_factor_secret = ''
        admin_profile.backup_codes = []
        admin_profile.save()
        
        # Log 2FA disable
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='2fa_setup',
            description='2FA disabled',
            request=request
        )
        
        return Response({
            'message': '2FA disabled successfully'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary="Admin Logout",
    operation_description="Logout admin user and invalidate session.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'refresh_token': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='JWT refresh token to blacklist',
                example='eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
            )
        },
        required=['refresh_token']
    ),
    responses={
        200: openapi.Response(description="Logout successful")
    },
    tags=['CoreAdmin Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_logout(request):
    """
    Admin logout - invalidate refresh token and log activity.
    """
    serializer = AdminLogoutSerializer(data=request.data)
    
    if serializer.is_valid():
        try:
            refresh_token = serializer.validated_data['refresh_token']
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass  # Token might already be blacklisted
        
        # Deactivate current session
        try:
            session = AdminSession.objects.filter(
                user_id=request.user.id,
                is_active=True
            ).first()
            if session:
                session.is_active = False
                session.save()
        except AdminSession.DoesNotExist:
            pass
        
        # Log logout
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='logout',
            description='Admin logout',
            request=request
        )
        
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_summary="Admin Profile",
    operation_description="Get admin user profile information.",
    responses={
        200: openapi.Response(description="Admin profile retrieved successfully")
    },
    tags=['CoreAdmin Management']
)
@swagger_auto_schema(
    method='put',
    operation_summary="Update Admin Profile",
    operation_description="Update admin user profile information.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'first_name': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Admin first name',
                example='John'
            ),
            'last_name': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Admin last name',
                example='Doe'
            ),
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='Admin email address',
                example='john.doe@example.com'
            ),
            'mobile_number': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Admin mobile number (10 digits)',
                example='1234567890'
            )
        }
    ),
    responses={
        200: openapi.Response(description="Admin profile updated successfully")
    },
    tags=['CoreAdmin Management']
)
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def admin_profile(request):
    """
    Get or update admin user profile.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'User does not have admin profile'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        serializer = AdminProfileSerializer(admin_profile)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'PUT':
        from .serializers import AdminProfileUpdateSerializer
        serializer = AdminProfileUpdateSerializer(admin_profile, data=request.data, context={'request': request})
        
        if serializer.is_valid():
            try:
                serializer.save()
                
                # Refresh admin_profile from database to get latest data including mobile number
                admin_profile.refresh_from_db()
                # Also refresh the related user object
                request.user.refresh_from_db()
                
                # Log profile update
                AdminActivityLog.log_activity(
                    user=request.user,
                    activity_type='profile_update',
                    description='Profile updated',
                    request=request
                )
                
                # Return updated profile with latest data
                profile_serializer = AdminProfileSerializer(admin_profile, context={'request': request})
                return Response(profile_serializer.data, status=status.HTTP_200_OK)
            except Exception as e:
                # Handle any unexpected errors during save
                error_message = str(e)
                if 'unique constraint' in error_message.lower() or 'duplicate key' in error_message.lower():
                    return Response({
                        'error': 'A record with this information already exists. Please check your email or mobile number.',
                        'details': error_message
                    }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    return Response({
                        'error': 'Failed to update profile. Please try again.',
                        'details': error_message
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Return validation errors with proper formatting
        error_messages = []
        if isinstance(serializer.errors, dict):
            for field, errors in serializer.errors.items():
                if isinstance(errors, list):
                    error_messages.extend([f"{field.replace('_', ' ').title()}: {error}" for error in errors])
                else:
                    error_messages.append(f"{field.replace('_', ' ').title()}: {errors}")
        else:
            error_messages.append(str(serializer.errors))
        
        return Response({
            'error': 'Validation failed',
            'details': error_messages if error_messages else ['Please check your input and try again.']
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary="Upload Admin Profile Photo",
    operation_description="Upload a profile photo for the admin user.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'profile_photo': openapi.Schema(
                type=openapi.TYPE_FILE,
                description='Profile photo image file'
            )
        }
    ),
    responses={
        200: openapi.Response(
            description="Profile photo uploaded successfully",
            examples={
                "application/json": {
                    "message": "Profile photo uploaded successfully",
                    "profile_photo_url": "https://example.com/media/profile_photo.jpg"
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid file"),
        401: openapi.Response(description="Unauthorized - authentication required")
    },
    tags=['CoreAdmin Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_upload_profile_photo(request):
    """
    Upload profile photo for admin user.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'User does not have admin profile'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if 'profile_photo' not in request.FILES:
        return Response({
            'error': 'No profile photo file provided'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    file = request.FILES['profile_photo']
    
    # Validate file type
    if not file.content_type.startswith('image/'):
        return Response({
            'error': 'File must be an image'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate file size (max 5MB)
    if file.size > 5 * 1024 * 1024:
        return Response({
            'error': 'File size must be less than 5MB'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from MediaFiles.models import Media, Relation
        from common.relations import attach_relation
        
        # Remove old profile photo if exists
        old_relations = Relation.objects.filter(
            relation_type='AdminUserProfile:Media',
            id_1=admin_profile.pk
        )
        for relation in old_relations:
            if relation.meta and relation.meta.get('type') == 'profile_photo':
                relation.delete()
        
        # Create new profile photo
        Media.set_profile_context()
        try:
            profile_photo = Media.objects.create(
                file=file,
                media_type='image',
                created_by=request.user
            )
        finally:
            Media.clear_profile_context()
        attach_relation('AdminUserProfile:Media', admin_profile, profile_photo, 
                      meta={'type': 'profile_photo'}, created_by=request.user)
        
        # Build profile photo URL
        profile_photo_url = None
        if profile_photo.file:
            try:
                from django.conf import settings
                # Get file path - this is relative to MEDIA_ROOT
                file_path = profile_photo.file.name
                # Construct URL: MEDIA_URL + file_path
                # Since upload_to='media/', file_path is 'media/filename.jpg'
                # MEDIA_URL is '/media/', so URL becomes '/media/media/filename.jpg'
                relative_url = f"{settings.MEDIA_URL}{file_path}"
                # Ensure it starts with /
                if not relative_url.startswith('/'):
                    relative_url = '/' + relative_url
                # Build absolute URL using SITE_URL from settings to ensure it points to Django backend
                site_url = getattr(settings, 'SITE_URL', None)
                if site_url:
                    # Remove trailing slash from SITE_URL if present
                    site_url = site_url.rstrip('/')
                    profile_photo_url = f"{site_url}{relative_url}"
                else:
                    # Fallback to request.build_absolute_uri if SITE_URL not set
                    profile_photo_url = request.build_absolute_uri(relative_url)
            except (ValueError, AttributeError, Exception) as e:
                # Fallback: try using file.url if available
                try:
                    url = profile_photo.file.url
                    site_url = getattr(settings, 'SITE_URL', None)
                    if site_url and url.startswith('/'):
                        site_url = site_url.rstrip('/')
                        profile_photo_url = f"{site_url}{url}"
                    elif url.startswith('http'):
                        profile_photo_url = url
                    else:
                        profile_photo_url = request.build_absolute_uri('/' + url)
                except:
                    profile_photo_url = None
        
        # Log profile photo update
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='profile_update',
            description='Profile photo updated',
            request=request
        )
        
        return Response({
            'message': 'Profile photo uploaded successfully',
            'profile_photo_url': profile_photo_url
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        # Handle specific error types and provide user-friendly messages
        error_message = str(e)
        if 'permission' in error_message.lower() or 'access' in error_message.lower():
            return Response({
                'error': 'You do not have permission to upload profile photos.',
                'details': error_message
            }, status=status.HTTP_403_FORBIDDEN)
        elif 'storage' in error_message.lower() or 'disk' in error_message.lower() or 'space' in error_message.lower():
            return Response({
                'error': 'Storage error. Please contact support.',
                'details': error_message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({
                'error': 'Failed to upload profile photo. Please try again.',
                'details': error_message
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary="Admin Activity Logs",
    operation_description="Get admin activity logs (superusers only).",
    manual_parameters=[
        openapi.Parameter(
            'activity_type',
            openapi.IN_QUERY,
            description='Filter by activity type',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'user_id',
            openapi.IN_QUERY,
            description='Filter by user ID',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Activity logs retrieved successfully"),
        403: openapi.Response(description="Access denied - superuser required")
    },
    tags=['CoreAdmin Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_activity_logs(request):
    """
    Get admin activity logs (superusers only).
    """
    if not request.user.is_superuser:
        return Response({
            'error': 'Access denied. Superuser privileges required.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Filter logs
    logs = AdminActivityLog.objects.all()
    
    activity_type = request.GET.get('activity_type')
    if activity_type:
        logs = logs.filter(activity_type=activity_type)
    
    user_id = request.GET.get('user_id')
    if user_id:
        logs = logs.filter(user_id=user_id)
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginated_logs = paginator.paginate_queryset(logs, request)
    
    serializer = AdminActivityLogSerializer(paginated_logs, many=True)
    return paginator.get_paginated_response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_summary="Admin Sessions",
    operation_description="Get active admin sessions (superusers only).",
    responses={
        200: openapi.Response(description="Sessions retrieved successfully"),
        403: openapi.Response(description="Access denied - superuser required")
    },
    tags=['CoreAdmin Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_sessions(request):
    """
    Get active admin sessions (superusers only).
    """
    if not request.user.is_superuser:
        return Response({
            'error': 'Access denied. Superuser privileges required.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    sessions = AdminSession.objects.filter(is_active=True).order_by('-last_activity')
    serializer = AdminSessionSerializer(sessions, many=True)
    
    return Response(serializer.data, status=status.HTTP_200_OK)


# ==================== Scheduled Tasks (Celery) ====================

def _scheduled_tasks_superuser_required(request):
    """Return (None, None) if allowed, else (Response, status). Uses AdminUserProfile.admin_group (Super Admin) instead of User.is_superuser."""
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return (Response({'error': 'Access denied. Admin profile required.'}, status=status.HTTP_403_FORBIDDEN), status.HTTP_403_FORBIDDEN)
    if admin_profile.admin_group != 'superadmin':
        return (Response({'error': 'Access denied. Super Admin privileges required.'}, status=status.HTTP_403_FORBIDDEN), status.HTTP_403_FORBIDDEN)
    return (None, None)


@swagger_auto_schema(
    method='get',
    operation_summary="Scheduled tasks overview",
    operation_description="Get counts of active, reserved, scheduled tasks and recent failure/success (superusers only).",
    responses={200: openapi.Response(description="Overview data"), 403: openapi.Response(description="Access denied")},
    tags=['Scheduled Tasks']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scheduled_tasks_overview(request):
    from django_celery_results.models import TaskResult
    err_resp, err_status = _scheduled_tasks_superuser_required(request)
    if err_resp is not None:
        return err_resp
    since = timezone.now() - timezone.timedelta(hours=24)
    failed_24h = TaskResult.objects.filter(status='FAILURE', date_created__gte=since).count()
    success_24h = TaskResult.objects.filter(status='SUCCESS', date_created__gte=since).count()
    active_count = 0
    reserved_count = 0
    scheduled_count = 0
    try:
        from API.celery import app
        i = app.control.inspect()
        if i:
            active = i.active() or {}
            reserved = i.reserved() or {}
            scheduled = i.scheduled() or {}
            active_count = sum(len(tasks) for tasks in active.values())
            reserved_count = sum(len(tasks) for tasks in reserved.values())
            scheduled_count = sum(len(tasks) for tasks in scheduled.values())
    except Exception:
        pass
    return Response({
        'active': active_count,
        'reserved': reserved_count,
        'scheduled': scheduled_count,
        'failed_last_24h': failed_24h,
        'success_last_24h': success_24h,
    }, status=status.HTTP_200_OK)


def _get_task_description(task):
    """Get docstring from a Celery task (task or task.run)."""
    description = (getattr(task, '__doc__', None) or '').strip()
    if not description and getattr(task, 'run', None):
        description = (getattr(task.run, '__doc__', None) or '').strip()
    return description or None


@swagger_auto_schema(
    method='get',
    operation_summary="Registered tasks list",
    operation_description="List all Celery task names and descriptions (docstrings) registered in the application (superusers only). Excludes internal celery.* tasks.",
    responses={200: openapi.Response(description="List of tasks with name and description"), 403: openapi.Response(description="Access denied")},
    tags=['Scheduled Tasks']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def registered_tasks_list(request):
    err_resp, _ = _scheduled_tasks_superuser_required(request)
    if err_resp is not None:
        return err_resp
    try:
        from API.celery import app
        task_names = sorted(
            name for name in app.tasks.keys()
            if not name.startswith('celery.')
        )
        tasks = []
        for name in task_names:
            task = app.tasks.get(name)
            description = _get_task_description(task) if task else None
            tasks.append({'name': name, 'description': description})
        return Response({'tasks': tasks}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_summary="Registered task detail",
    operation_description="Get description (docstring) for a registered Celery task by name (superusers only).",
    manual_parameters=[
        openapi.Parameter('task_name', openapi.IN_QUERY, description='Full task name (e.g. common.tasks.cleanup_expired_otps)', type=openapi.TYPE_STRING, required=True),
    ],
    responses={200: openapi.Response(description="Task name and description"), 403: openapi.Response(description="Access denied"), 404: openapi.Response(description="Task not found")},
    tags=['Scheduled Tasks']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def registered_task_detail(request):
    err_resp, _ = _scheduled_tasks_superuser_required(request)
    if err_resp is not None:
        return err_resp
    task_name = (request.GET.get('task_name') or '').strip()
    if not task_name:
        return Response({'error': 'task_name is required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        from API.celery import app
        task = app.tasks.get(task_name)
        if task is None:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)
        description = (getattr(task, '__doc__', None) or '')
        if not description and getattr(task, 'run', None):
            description = getattr(task.run, '__doc__', None) or ''
        description = (description or '').strip() or None
        return Response({'name': task_name, 'description': description}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_summary="Scheduled tasks list",
    operation_description="List Celery task history from TaskResult (superusers only).",
    manual_parameters=[
        openapi.Parameter('status', openapi.IN_QUERY, description='Filter by status (e.g. SUCCESS, FAILURE, PENDING)', type=openapi.TYPE_STRING),
        openapi.Parameter('task_name', openapi.IN_QUERY, description='Filter by task name (contains)', type=openapi.TYPE_STRING),
        openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        openapi.Parameter('page_size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
    ],
    responses={200: openapi.Response(description="Paginated task list"), 403: openapi.Response(description="Access denied")},
    tags=['Scheduled Tasks']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scheduled_tasks_list(request):
    from django_celery_results.models import TaskResult
    from rest_framework.pagination import PageNumberPagination
    err_resp, _ = _scheduled_tasks_superuser_required(request)
    if err_resp is not None:
        return err_resp
    qs = TaskResult.objects.all().order_by('-date_created')
    status_filter = request.GET.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter.upper())
    task_name = request.GET.get('task_name', '').strip()
    if task_name:
        qs = qs.filter(task_name__icontains=task_name)
    paginator = PageNumberPagination()
    try:
        ps = int(request.GET.get('page_size') or request.GET.get('limit', 25))
        if ps in (10, 25, 50, 100):
            paginator.page_size = ps
        else:
            paginator.page_size = 25
    except (ValueError, TypeError):
        paginator.page_size = 25
    page = paginator.paginate_queryset(qs, request)
    results = []
    for t in page:
        result_preview = None
        if t.result:
            try:
                s = str(t.result)
                result_preview = s[:200] + ('...' if len(s) > 200 else '')
            except Exception:
                result_preview = str(t.result)[:200]
        results.append({
            'task_id': t.task_id,
            'task_name': t.task_name or '',
            'status': t.status,
            'date_created': t.date_created.isoformat() if t.date_created else None,
            'date_done': t.date_done.isoformat() if t.date_done else None,
            'worker': t.worker or '',
            'result_preview': result_preview,
            'traceback': t.traceback[:500] if t.traceback and len(t.traceback) > 500 else (t.traceback or ''),
        })
    return paginator.get_paginated_response(results)


@swagger_auto_schema(
    method='get',
    operation_summary="Scheduled task detail",
    operation_description="Get a single task result by task_id (superusers only).",
    responses={200: openapi.Response(description="Task detail"), 403: openapi.Response(description="Access denied"), 404: openapi.Response(description="Task not found")},
    tags=['Scheduled Tasks']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def scheduled_tasks_detail(request, task_id):
    from django_celery_results.models import TaskResult
    err_resp, _ = _scheduled_tasks_superuser_required(request)
    if err_resp is not None:
        return err_resp
    try:
        t = TaskResult.objects.get(task_id=task_id)
    except TaskResult.DoesNotExist:
        return Response({'error': 'Task not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response({
        'task_id': t.task_id,
        'task_name': t.task_name or '',
        'status': t.status,
        'date_created': t.date_created.isoformat() if t.date_created else None,
        'date_done': t.date_done.isoformat() if t.date_done else None,
        'worker': t.worker or '',
        'result': t.result,
        'traceback': t.traceback or '',
        'task_args': t.task_args,
        'task_kwargs': t.task_kwargs,
        'meta': t.meta,
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    operation_summary="Revoke a task",
    operation_description="Revoke (stop) a running or pending Celery task by task_id (superusers only).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'terminate': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='If true, terminate the task if running', default=True),
        }
    ),
    responses={200: openapi.Response(description="Revoked"), 403: openapi.Response(description="Access denied"), 404: openapi.Response(description="Task not found")},
    tags=['Scheduled Tasks']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scheduled_tasks_revoke(request, task_id):
    err_resp, _ = _scheduled_tasks_superuser_required(request)
    if err_resp is not None:
        return err_resp
    terminate = request.data.get('terminate', True)
    try:
        from API.celery import app
        app.control.revoke(task_id, terminate=terminate)
        return Response({'success': True, 'message': 'Task revoke requested.'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary="Bulk revoke tasks",
    operation_description="Revoke (stop) multiple running or pending Celery tasks by task_id (superusers only).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'task_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_STRING),
                description='List of task IDs to revoke',
            ),
            'terminate': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='If true, terminate tasks if running', default=True),
        },
        required=['task_ids'],
    ),
    responses={
        200: openapi.Response(description="Bulk revoke result with revoked/failed counts"),
        403: openapi.Response(description="Access denied"),
    },
    tags=['Scheduled Tasks']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scheduled_tasks_bulk_revoke(request):
    err_resp, _ = _scheduled_tasks_superuser_required(request)
    if err_resp is not None:
        return err_resp
    task_ids = request.data.get('task_ids') or []
    if not isinstance(task_ids, list):
        return Response(
            {'success': False, 'error': 'task_ids must be a list'},
            status=status.HTTP_400_BAD_REQUEST
        )
    terminate = request.data.get('terminate', True)
    revoked = 0
    errors = []
    try:
        from API.celery import app
        for task_id in task_ids:
            if not task_id:
                continue
            try:
                app.control.revoke(str(task_id), terminate=terminate)
                revoked += 1
            except Exception as e:
                errors.append({'task_id': str(task_id), 'error': str(e)})
        return Response({
            'success': True,
            'revoked': revoked,
            'failed': len(errors),
            'errors': errors if errors else None,
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==================== Periodic Tasks (Celery Beat) ====================

def _periodic_task_schedule_display(periodic_task):
    """Build a human-readable schedule string for a PeriodicTask."""
    from django_celery_beat.models import IntervalSchedule, CrontabSchedule
    if periodic_task.interval_id:
        interval = periodic_task.interval
        if isinstance(interval, IntervalSchedule):
            every = interval.every
            period = (interval.period or 'seconds').lower()
            if period == 'seconds':
                return f'Every {every} sec' if every == 1 else f'Every {every} seconds'
            if period == 'minutes':
                return f'Every {every} min' if every == 1 else f'Every {every} minutes'
            if period == 'hours':
                return f'Every {every} hour' if every == 1 else f'Every {every} hours'
            if period == 'days':
                return f'Every {every} day' if every == 1 else f'Every {every} days'
            return f'Every {every} {period}'
    if periodic_task.crontab_id:
        crontab = periodic_task.crontab
        if isinstance(crontab, CrontabSchedule):
            parts = []
            if crontab.minute != '*':
                parts.append(f'min {crontab.minute}')
            if crontab.hour != '*':
                parts.append(f'hour {crontab.hour}')
            if crontab.day_of_week != '*':
                parts.append(f'dow {crontab.day_of_week}')
            if crontab.day_of_month != '*':
                parts.append(f'dom {crontab.day_of_month}')
            if crontab.month_of_year != '*':
                parts.append(f'month {crontab.month_of_year}')
            if parts:
                return ', '.join(parts)
            return 'Crontab (* * * * *)'
    if periodic_task.solar_id:
        return str(periodic_task.solar) if periodic_task.solar else 'Solar'
    if periodic_task.clocked_id:
        return str(periodic_task.clocked) if periodic_task.clocked else 'Clocked'
    return '—'


@swagger_auto_schema(
    method='get',
    operation_summary="Periodic tasks overview",
    operation_description="Get counts of periodic tasks (total, enabled) from Celery Beat (superusers only).",
    responses={200: openapi.Response(description="Overview data"), 403: openapi.Response(description="Access denied")},
    tags=['Periodic Tasks']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def periodic_tasks_overview(request):
    from django_celery_beat.models import PeriodicTask
    err_resp, _ = _scheduled_tasks_superuser_required(request)
    if err_resp is not None:
        return err_resp
    total = PeriodicTask.objects.count()
    enabled = PeriodicTask.objects.filter(enabled=True).count()
    return Response({
        'total': total,
        'enabled': enabled,
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    operation_summary="Periodic tasks list",
    operation_description="List Celery Beat periodic tasks (superusers only).",
    manual_parameters=[
        openapi.Parameter('enabled', openapi.IN_QUERY, description='Filter by enabled (true/false)', type=openapi.TYPE_BOOLEAN),
        openapi.Parameter('task_name', openapi.IN_QUERY, description='Filter by task path (contains)', type=openapi.TYPE_STRING),
        openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        openapi.Parameter('page_size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
    ],
    responses={200: openapi.Response(description="Paginated periodic task list"), 403: openapi.Response(description="Access denied")},
    tags=['Periodic Tasks']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def periodic_tasks_list(request):
    from django_celery_beat.models import PeriodicTask
    from rest_framework.pagination import PageNumberPagination
    err_resp, _ = _scheduled_tasks_superuser_required(request)
    if err_resp is not None:
        return err_resp
    qs = PeriodicTask.objects.select_related('interval', 'crontab', 'solar', 'clocked').order_by('name')
    enabled_filter = request.GET.get('enabled')
    if enabled_filter is not None:
        if str(enabled_filter).lower() in ('true', '1', 'yes'):
            qs = qs.filter(enabled=True)
        elif str(enabled_filter).lower() in ('false', '0', 'no'):
            qs = qs.filter(enabled=False)
    task_name = request.GET.get('task_name', '').strip()
    if task_name:
        qs = qs.filter(task__icontains=task_name)
    paginator = PageNumberPagination()
    try:
        ps = int(request.GET.get('page_size') or request.GET.get('limit', 25))
        if ps in (10, 25, 50, 100):
            paginator.page_size = ps
        else:
            paginator.page_size = 25
    except (ValueError, TypeError):
        paginator.page_size = 25
    page = paginator.paginate_queryset(qs, request)
    results = []
    for pt in page:
        results.append({
            'id': pt.id,
            'name': pt.name or '',
            'task': pt.task or '',
            'enabled': pt.enabled,
            'last_run_at': pt.last_run_at.isoformat() if pt.last_run_at else None,
            'total_run_count': getattr(pt, 'total_run_count', None) or 0,
            'schedule_display': _periodic_task_schedule_display(pt),
        })
    return paginator.get_paginated_response(results)


@swagger_auto_schema(
    method='post',
    operation_summary="Change Admin Password",
    operation_description="Change admin user password.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'old_password': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Current password',
                example='oldpassword123'
            ),
            'new_password': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='New password (minimum 8 characters)',
                example='newpassword123'
            ),
            'confirm_password': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Confirm new password',
                example='newpassword123'
            )
        },
        required=['old_password', 'new_password', 'confirm_password']
    ),
    responses={
        200: openapi.Response(description="Password changed successfully")
    },
    tags=['CoreAdmin Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_change_password(request):
    """
    Change admin user password.
    """
    try:
        serializer = AdminPasswordChangeSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            try:
                new_password = serializer.validated_data['new_password']
                
                # Update password
                request.user.set_password(new_password)
                request.user.save()
                
                # Log password change
                AdminActivityLog.log_activity(
                    user=request.user,
                    activity_type='password_change',
                    description='Password changed',
                    request=request
                )
                
                return Response({
                    'message': 'Password changed successfully'
                }, status=status.HTTP_200_OK)
            except Exception as e:
                # Handle any errors during password update
                error_message = str(e)
                return Response({
                    'error': 'Failed to change password. Please try again.',
                    'details': error_message
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Return validation errors with proper formatting
        error_messages = []
        if isinstance(serializer.errors, dict):
            for field, errors in serializer.errors.items():
                if isinstance(errors, list):
                    error_messages.extend([f"{field.replace('_', ' ').title()}: {error}" for error in errors])
                else:
                    error_messages.append(f"{field.replace('_', ' ').title()}: {errors}")
        else:
            error_messages.append(str(serializer.errors))
        
        return Response({
            'error': 'Validation failed',
            'details': error_messages if error_messages else ['Please check your input and try again.']
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        # Handle any unexpected errors
        return Response({
            'error': 'An error occurred while changing password. Please try again.',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Designer Management Views

@swagger_auto_schema(
    method='get',
    operation_summary="Designers List",
    operation_description="Get list of all designers with filtering and pagination (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by designer status (pending, verified, suspended, rejected)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'account_status',
            openapi.IN_QUERY,
            description='Filter by user account status (active, inactive)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'search',
            openapi.IN_QUERY,
            description='Search by name or email',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by field (created_at, updated_at, first_name, last_name)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_order',
            openapi.IN_QUERY,
            description='Sort order (asc, desc)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Designers retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designers_list(request):
    """
    Get list of all designers who have completed onboarding, with filtering and pagination.
    Only returns designers where onboarding_completed=True.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get all users with designer profiles who have completed onboarding
    # Note: DesignerProfile uses related_name='created_designer_profiles'
    # Only include designers who have completed their onboarding
    designers = User.objects.filter(
        created_designer_profiles__isnull=False,
        created_designer_profiles__onboarding_completed=True
    ).distinct()
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        designers = designers.filter(created_designer_profiles__status=status_filter)
    
    account_status = request.GET.get('account_status')
    if account_status == 'active':
        designers = designers.filter(is_active=True)
    elif account_status == 'inactive':
        designers = designers.filter(is_active=False)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        designers = designers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(username__icontains=search_query)
        )
    
    # Sorting
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_order = request.GET.get('sort_order', 'desc')
    
    if sort_order == 'desc':
        sort_by = f'-{sort_by}'
    
    if sort_by in ['created_at', 'updated_at', 'first_name', 'last_name', 'email']:
        designers = designers.order_by(sort_by)
    else:
        designers = designers.order_by('-date_joined')
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginated_designers = paginator.paginate_queryset(designers, request)
    
    serializer = DesignerManagementSerializer(paginated_designers, many=True)
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='user_management',
            description='Viewed designers list',
            request=request,
            metadata={'filters': request.GET.dict()}
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

    return paginator.get_paginated_response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_summary="Designer Detail",
    operation_description="Get detailed information about a specific designer (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Designer details retrieved successfully"),
        404: openapi.Response(description="Designer not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designer_detail(request, designer_id):
    """
    Get detailed information about a specific designer.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        designer = User.objects.get(id=designer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Designer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if user has a designer profile using the correct relation name
    if not designer.created_designer_profiles.exists():
        return Response({
            'error': 'User is not a designer'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = DesignerDetailSerializer(designer)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Viewed designer details: {designer.get_full_name()}',
        request=request,
        metadata={'designer_id': designer_id}
    )
    
    return Response(serializer.data, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='put',
    operation_summary="Update Designer Status",
    operation_description="Update designer profile status (SuperAdmin and Moderator access).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'status': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Designer status',
                enum=['pending', 'verified', 'suspended', 'rejected'],
                example='verified'
            ),
            'is_active': openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description='User account active status',
                example=True
            )
        },
        required=['status']
    ),
    responses={
        200: openapi.Response(description="Designer status updated successfully"),
        404: openapi.Response(description="Designer not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def designer_update_status(request, designer_id):
    """
    Update designer profile status and account status.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        designer = User.objects.get(id=designer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Designer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    profile = designer.created_designer_profiles.first()
    if not profile:
        return Response({
            'error': 'User is not a designer'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Update designer profile status
    new_status = request.data.get('status')
    if new_status in ['pending', 'verified', 'suspended', 'rejected']:
        profile.status = new_status
        profile.updated_by = request.user
        profile.save()
    
    # Update user account status
    is_active = request.data.get('is_active')
    if is_active is not None:
        designer.is_active = is_active
        designer.save()
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Updated designer status: {designer.get_full_name()}',
        request=request,
        metadata={
            'designer_id': designer_id,
            'new_status': new_status,
            'is_active': is_active
        }
    )
    
    return Response({
        'message': 'Designer status updated successfully',
        'designer': DesignerDetailSerializer(designer).data
    }, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='get',
    operation_summary="Designer Wallet",
    operation_description="Get designer wallet information and balance (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Designer wallet retrieved successfully"),
        404: openapi.Response(description="Designer not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designer_wallet(request, designer_id):
    """
    Get designer wallet information and balance.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        designer = User.objects.get(id=designer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Designer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get designer wallets
    wallets = get_user_wallets(designer)
    
    if not wallets.exists():
        return Response({
            'message': 'No wallet found for this designer',
            'wallet': None
        }, status=status.HTTP_200_OK)
    
    # Get primary wallet (first one)
    primary_wallet = wallets.first()
    
    # Calculate total earnings and pending amount using relation system
    transactions = get_related(primary_wallet, 'Wallet:WalletTransaction', WalletTransaction)
    total_earnings = transactions.filter(
        wallet_transaction_type='credit'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    withdrawals = get_related(primary_wallet, 'Wallet:WithdrawalRequest', WalletWithdrawalRequest)
    pending_withdrawals = withdrawals.filter(
        status='pending'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    serializer = DesignerWalletSerializer({
        'wallet': primary_wallet,
        'total_earnings': total_earnings,
        'pending_withdrawals': pending_withdrawals
    })
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Viewed designer wallet: {designer.get_full_name()}',
        request=request,
        metadata={'designer_id': designer_id}
    )
    
    return Response(serializer.data, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='get',
    operation_summary="Designer Transactions",
    operation_description="Get designer wallet transactions (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'transaction_type',
            openapi.IN_QUERY,
            description='Filter by transaction type (credit, debit)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Designer transactions retrieved successfully"),
        404: openapi.Response(description="Designer not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designer_transactions(request, designer_id):
    """
    Get designer wallet transactions.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        designer = User.objects.get(id=designer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Designer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get designer wallets
    wallets = get_user_wallets(designer)
    
    if not wallets.exists():
        return Response({
            'message': 'No wallet found for this designer',
            'transactions': []
        }, status=status.HTTP_200_OK)
    
    # Get transactions for all wallets using relation system
    transaction_ids = []
    for wallet in wallets:
        wallet_transactions = get_related(wallet, 'Wallet:WalletTransaction', WalletTransaction)
        transaction_ids.extend(wallet_transactions.values_list('id', flat=True))
    transactions = WalletTransaction.objects.filter(id__in=transaction_ids).order_by('-created_at')
    
    # Apply filters
    transaction_type = request.GET.get('transaction_type')
    if transaction_type in ['credit', 'debit']:
        transactions = transactions.filter(wallet_transaction_type=transaction_type)
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginated_transactions = paginator.paginate_queryset(transactions, request)
    
    serializer = DesignerTransactionSerializer(paginated_transactions, many=True)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Viewed designer transactions: {designer.get_full_name()}',
        request=request,
        metadata={'designer_id': designer_id}
    )
    
    return paginator.get_paginated_response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_summary="Designer Withdrawals",
    operation_description="Get designer withdrawal requests (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by withdrawal status (pending, approved, rejected)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Designer withdrawals retrieved successfully"),
        404: openapi.Response(description="Designer not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designer_withdrawals(request, designer_id):
    """
    Get designer withdrawal requests.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        designer = User.objects.get(id=designer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Designer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get designer wallets
    wallets = get_user_wallets(designer)
    
    if not wallets.exists():
        return Response({
            'message': 'No wallet found for this designer',
            'withdrawals': []
        }, status=status.HTTP_200_OK)
    
    # Get withdrawal requests for all wallets using relation system
    withdrawal_ids = []
    for wallet in wallets:
        wallet_withdrawals = get_related(wallet, 'Wallet:WithdrawalRequest', WalletWithdrawalRequest)
        withdrawal_ids.extend(wallet_withdrawals.values_list('id', flat=True))
    withdrawals = WalletWithdrawalRequest.objects.filter(id__in=withdrawal_ids).order_by('-created_at')
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter in ['pending', 'approved', 'rejected']:
        withdrawals = withdrawals.filter(status=status_filter)
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginated_withdrawals = paginator.paginate_queryset(withdrawals, request)
    
    serializer = DesignerWithdrawalSerializer(paginated_withdrawals, many=True)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Viewed designer withdrawals: {designer.get_full_name()}',
        request=request,
        metadata={'designer_id': designer_id}
    )
    
    return paginator.get_paginated_response(serializer.data)

@swagger_auto_schema(
    method='put',
    operation_summary="Update Withdrawal Status",
    operation_description="Update designer withdrawal request status (SuperAdmin only).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'status': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Withdrawal status',
                enum=['pending', 'approved', 'rejected'],
                example='approved'
            ),
            'admin_notes': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Admin notes for the withdrawal',
                example='Approved for payout'
            )
        },
        required=['status']
    ),
    responses={
        200: openapi.Response(description="Withdrawal status updated successfully"),
        404: openapi.Response(description="Withdrawal not found"),
        403: openapi.Response(description="Access denied - superadmin required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_withdrawal_status(request, withdrawal_id):
    """
    Update designer withdrawal request status (SuperAdmin only).
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Only superadmins can update withdrawal status
    if admin_profile.admin_group != 'superadmin':
        return Response({
            'error': 'Access denied. Superadmin privileges required.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        withdrawal = WalletWithdrawalRequest.objects.get(id=withdrawal_id)
    except WalletWithdrawalRequest.DoesNotExist:
        return Response({
            'error': 'Withdrawal request not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Update withdrawal status
    new_status = request.data.get('status')
    if new_status in ['pending', 'approved', 'rejected']:
        withdrawal.status = new_status
        withdrawal.updated_by = request.user
        withdrawal.save()
    
    # Add admin notes if provided
    admin_notes = request.data.get('admin_notes')
    if admin_notes:
        # Store admin notes in metadata or notes field if available
        if hasattr(withdrawal, 'notes'):
            withdrawal.notes = admin_notes
            withdrawal.save()
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Updated withdrawal status: {withdrawal.id}',
        request=request,
        metadata={
            'withdrawal_id': withdrawal_id,
            'new_status': new_status,
            'admin_notes': admin_notes
        }
    )
    
    return Response({
        'message': 'Withdrawal status updated successfully',
        'withdrawal': DesignerWithdrawalSerializer(withdrawal).data
    }, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='get',
    operation_summary="Designer Analytics",
    operation_description="Get designer analytics and statistics (SuperAdmin only).",
    responses={
        200: openapi.Response(description="Designer analytics retrieved successfully"),
        403: openapi.Response(description="Access denied - superadmin required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designer_analytics(request):
    """
    Get designer analytics and statistics (SuperAdmin only).
    Returns stats in format expected by AdminWebApp dashboard.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Only superadmins can view analytics
    if admin_profile.admin_group != 'superadmin':
        return Response({
            'error': 'Access denied. Superadmin privileges required.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get all designers who have completed onboarding
        # Note: DesignerProfile uses related_name='created_designer_profiles'
        # Only count designers who have completed their onboarding
        designers = User.objects.filter(
            created_designer_profiles__isnull=False,
            created_designer_profiles__onboarding_completed=True
        ).distinct()
        
        # Calculate basic statistics (only for completed onboarding designers)
        total_designers = designers.count()
        pending_approval = designers.filter(created_designer_profiles__status='pending').distinct().count()
        
        # Get rejected count (from profile status)
        # Note: 'rejected' status doesn't exist in DesignerProfile, so we use 0
        # If you add 'rejected' status later, uncomment the line below
        # rejected_profiles = designers.filter(created_designer_profiles__status='rejected').distinct().count()
        rejected = 0  # No rejected status in current system
        
        # Return stats in format expected by frontend
        stats_data = {
            'total_designers': total_designers,
            'pending_approval': pending_approval,
            'rejected': rejected
        }
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='user_management',
                description='Viewed designer analytics',
                request=request
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)

        return Response(stats_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while retrieving designer analytics',
            'detail': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    operation_summary="Bulk Update Designer Status",
    operation_description="Bulk update designer statuses (SuperAdmin only).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'designer_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description='List of designer IDs to update',
                example=[1, 2, 3]
            ),
            'status': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='New status for all designers',
                enum=['pending', 'verified', 'suspended', 'rejected'],
                example='verified'
            ),
            'is_active': openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description='New active status for all designers',
                example=True
            )
        },
        required=['designer_ids', 'status']
    ),
    responses={
        200: openapi.Response(description="Designers updated successfully"),
        403: openapi.Response(description="Access denied - superadmin required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_update_designer_status(request):
    """
    Bulk update designer statuses (SuperAdmin only).
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Only superadmins can perform bulk operations
    if admin_profile.admin_group != 'superadmin':
        return Response({
            'error': 'Access denied. Superadmin privileges required.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    designer_ids = request.data.get('designer_ids', [])
    new_status = request.data.get('status')
    is_active = request.data.get('is_active')
    
    if not designer_ids:
        return Response({
            'error': 'Designer IDs are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if new_status not in ['pending', 'verified', 'suspended', 'rejected']:
        return Response({
            'error': 'Invalid status'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update designers
    updated_count = 0
    failed_updates = []
    
    for designer_id in designer_ids:
        try:
            designer = User.objects.get(id=designer_id)
            
            profile = designer.created_designer_profiles.first()
            if profile:
                profile.status = new_status
                profile.updated_by = request.user
                profile.save()
            
            if is_active is not None:
                designer.is_active = is_active
                designer.save()
            
            updated_count += 1
            
        except User.DoesNotExist:
            failed_updates.append(f"Designer {designer_id} not found")
        except Exception as e:
            failed_updates.append(f"Error updating designer {designer_id}: {str(e)}")
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Bulk updated {updated_count} designers',
        request=request,
        metadata={
            'designer_ids': designer_ids,
            'new_status': new_status,
            'is_active': is_active,
            'updated_count': updated_count,
            'failed_updates': failed_updates
        }
    )
    
    return Response({
        'message': f'Successfully updated {updated_count} designers',
        'updated_count': updated_count,
        'failed_updates': failed_updates
    }, status=status.HTTP_200_OK)

# Enhanced Designer Management Views

@swagger_auto_schema(
    method='get',
    operation_summary="Designer Onboarding List",
    operation_description="Get list of designers with onboarding status (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by designer status (pending, verified, suspended, rejected)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'search',
            openapi.IN_QUERY,
            description='Search by designer name or email',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Designers retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designer_onboarding_list(request):
    """
    Get list of designers with onboarding status filtering.
    Uses DesignerProfile.status instead of DesignerOnboardingStatus.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get designers with profiles
    from Profiles.models import DesignerProfile
    from django.contrib.auth.models import User
    
    designers = User.objects.filter(
        created_designer_profiles__isnull=False
    ).select_related().distinct()
    
    # Apply status filter
    status_filter = request.GET.get('status')
    if status_filter:
        # Map old status values to new ones
        status_mapping = {
            'pending': 'pending',
            'approved': 'verified',
            'rejected': 'pending'  # Rejected designers are still pending in new system
        }
        mapped_status = status_mapping.get(status_filter, status_filter)
        designers = designers.filter(created_designer_profiles__status=mapped_status)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        designers = designers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(username__icontains=search_query)
        )
    
    # Order by creation date
    designers = designers.order_by('-date_joined')
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginated_designers = paginator.paginate_queryset(designers, request)
    
    # Use DesignerDetailSerializer
    serializer = DesignerDetailSerializer(paginated_designers, many=True)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description='Viewed designer onboarding list',
        request=request,
        metadata={'filters': request.GET.dict()}
    )
    
    return paginator.get_paginated_response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_summary="Designer Onboarding Detail",
    operation_description="Get detailed information about a designer onboarding request (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Onboarding details retrieved successfully"),
        404: openapi.Response(description="Onboarding request not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designer_onboarding_detail(request, designer_id):
    """
    Get detailed information about a designer onboarding request.
    Returns onboarding status and step data (step1, step2, step3).
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Check if designer exists
        designer = User.objects.get(id=designer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Designer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    try:
        from Profiles.models import DesignerProfile, Studio, StudioBusinessDetails
        from Authentication.models import Email, MobileNumber
        from MediaFiles.models import Media, Relation
        from Catalog.models import Product
        
        # Get designer profile
        try:
            designer_profile = DesignerProfile.objects.get(created_by=designer)
        except DesignerProfile.DoesNotExist:
            designer_profile = None
        
        # Build response data using DesignerProfile status
        response_data = {
            'designer_id': designer_id,
            'designer_name': designer.get_full_name() or designer.username,
            'designer_email': designer.email,
            'status': designer_profile.status if designer_profile else 'pending',
            'designer_profile_status': designer_profile.status if designer_profile else 'pending',
            'onboarding_completed': designer_profile.onboarding_completed if designer_profile else False,
            # Legacy fields for backward compatibility (always False since we're not using multi-step verification)
                'superadmin_verified': False,
                'moderator_verified': False,
            'final_approval': designer_profile.status == 'verified' if designer_profile else False,
                'rejection_reason': None,
        }
        
        # Get Step 1 data (Personal Details)
        step1_data = {}
        if designer_profile:
            # Get email
            email_obj = Email.objects.filter(created_by=designer, is_primary=True).first()
            email = email_obj.email if email_obj else designer.email
            email_verified = email_obj.is_verified if email_obj else False
            
            # Get phone
            mobile_obj = MobileNumber.objects.filter(created_by=designer, is_primary=True).first()
            phone = mobile_obj.mobile_number if mobile_obj else ''
            phone_verified = mobile_obj.is_verified if mobile_obj else False
            
            # Get profile photo
            profile_photo_url = None
            if designer_profile:
                profile_photo_relations = Relation.objects.filter(
                    relation_type='DesignerProfile:Media',
                    id_1=designer_profile.pk
                )
                for relation in profile_photo_relations:
                    if relation.meta and relation.meta.get('type') == 'profile_photo':
                        try:
                            profile_photo = Media.objects.get(pk=relation.id_2)
                            if hasattr(profile_photo.file, 'url'):
                                relative_url = profile_photo.file.url
                                if relative_url.startswith('/'):
                                    profile_photo_url = request.build_absolute_uri(relative_url)
                                elif relative_url.startswith('http'):
                                    profile_photo_url = relative_url
                                else:
                                    profile_photo_url = request.build_absolute_uri('/' + relative_url)
                                break
                        except Media.DoesNotExist:
                            continue
            
            step1_data = {
                'first_name': designer.first_name or '',
                'last_name': designer.last_name or '',
                'email': email,
                'phone': phone,
                'email_verified': email_verified,
                'phone_verified': phone_verified,
                'profile_photo_url': profile_photo_url,
                'is_individual': designer_profile.is_individual if designer_profile else False,
            }
        
        # Get Step 2 data (Business Details)
        step2_data = {}
        studio = Studio.objects.filter(created_by=designer).first()
        if studio:
            business_details = StudioBusinessDetails.objects.filter(studio=studio).first()
            if business_details:
                # Parse registered_addresses_json to extract address fields
                registered_address = {}
                if business_details.registered_addresses_json:
                    if isinstance(business_details.registered_addresses_json, dict):
                        registered_address = business_details.registered_addresses_json
                    elif isinstance(business_details.registered_addresses_json, str):
                        import json
                        try:
                            registered_address = json.loads(business_details.registered_addresses_json)
                        except:
                            registered_address = {}
                
                # Build absolute URL for pan_card if it exists
                pan_card_url = None
                if business_details.pan_card:
                    if business_details.pan_card.startswith('/'):
                        pan_card_url = request.build_absolute_uri(business_details.pan_card)
                    elif business_details.pan_card.startswith('http'):
                        pan_card_url = business_details.pan_card
                    else:
                        pan_card_url = request.build_absolute_uri('/' + business_details.pan_card)
                
                step2_data = {
                    'business_email': business_details.studio_email or '',
                    'business_phone': business_details.studio_mobile_number or '',
                    'legal_business_name': business_details.legal_business_name or '',
                    'business_type': business_details.business_type or '',
                    'category': business_details.business_category or '',
                    'subcategory': business_details.business_sub_category or '',
                    'business_model': business_details.business_model or '',
                    'street_address': registered_address.get('street', '') or '',
                    'city': registered_address.get('city', '') or '',
                    'state': registered_address.get('state', '') or '',
                    'pincode': registered_address.get('pincode') or registered_address.get('postal_code', '') or '',
                    'country': registered_address.get('country', 'India') or 'India',
                    'pan_number': business_details.pan_number or '',
                    'pan_card_url': pan_card_url,
                    'gst_number': business_details.gst_number or None,
                    'msme_number': business_details.msme_udyam_number or None,
                }
        
        # Get Step 3 data (Designs Upload)
        step3_data = {}
        step4_data = {'products': []}
        if designer_profile:
            # Get all products created by the designer
            products = Product.objects.filter(created_by=designer).order_by('-created_at')
            total_products = products.count()
            # Get minimum required designs from config
            from common.business_config import BusinessConfig
            minimum_required = BusinessConfig.get_minimum_required_designs_onboard()
            
            step3_data = {
                'designs_uploaded': total_products,
                'minimum_required': minimum_required,
                'requirement_met': total_products >= minimum_required,
            }
            
            # Get Step 4 data (Product Images) - Show EXACTLY one image per product (JPG preferred, PNG fallback)
            # Show ALL products created by the designer
            # Each product should contribute only ONE image to the display
            product_list = []
            products_with_images = 0
            seen_product_ids = set()  # Track products we've already added to avoid duplicates
            
            # Process all products created by the designer
            products_to_process = products
            
            for product in products_to_process:
                # Skip if we've already added this product (safety check)
                if product.id in seen_product_ids:
                    continue
                
                # Get product media (images)
                product_media = get_related(product, 'Product:Media', Media)
                
                # Prioritize JPG files, fallback to PNG if JPG not available
                selected_image = None
                
                # First pass: Look for JPG files
                for media in product_media:
                    if media.file:
                        file_url = media.file.url if hasattr(media.file, 'url') else None
                        if file_url:
                            # Build absolute URL
                            if file_url.startswith('/'):
                                absolute_url = request.build_absolute_uri(file_url)
                            elif file_url.startswith('http'):
                                absolute_url = file_url
                            else:
                                absolute_url = request.build_absolute_uri('/' + file_url)
                            
                            # Check if it's a JPG file
                            file_lower = file_url.lower()
                            if any(ext in file_lower for ext in ['.jpg', '.jpeg']):
                                selected_image = {
                                    'id': media.id,
                                    'url': absolute_url,
                                    'title': product.title,
                                    'product_id': product.id
                                }
                                break  # Found JPG, stop searching
                
                # Second pass: If no JPG found, look for PNG files
                if not selected_image:
                    for media in product_media:
                        if media.file:
                            file_url = media.file.url if hasattr(media.file, 'url') else None
                            if file_url:
                                # Build absolute URL
                                if file_url.startswith('/'):
                                    absolute_url = request.build_absolute_uri(file_url)
                                elif file_url.startswith('http'):
                                    absolute_url = file_url
                                else:
                                    absolute_url = request.build_absolute_uri('/' + file_url)
                                
                                # Check if it's a PNG file
                                file_lower = file_url.lower()
                                if '.png' in file_lower:
                                    selected_image = {
                                        'id': media.id,
                                        'url': absolute_url,
                                        'title': product.title,
                                        'product_id': product.id
                                    }
                                    break  # Found PNG, stop searching
                
                # Add product with EXACTLY one image (one image per product, no duplicates)
                # Only add if we found either JPG or PNG
                if selected_image:
                    product_list.append({
                        'product_id': product.id,
                        'title': product.title,
                        'image': selected_image  # Single image per product - JPG preferred, PNG as fallback
                    })
                    seen_product_ids.add(product.id)
                    products_with_images += 1
            
            step4_data = {
                'products': product_list,
                'total_products': products_with_images  # This should equal the number of products with images
            }
        
        # Add step data to response
        response_data['step1'] = step1_data
        response_data['step2'] = step2_data
        response_data['step3'] = step3_data
        response_data['step4'] = step4_data
        
        # Check if any onboarding data exists
        has_onboarding_data = bool(step1_data or step2_data or step3_data or onboarding)
        if not has_onboarding_data:
            response_data['message'] = 'Onboarding data is not available for this designer. They may not have completed the onboarding process yet.'
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='user_management',
                description=f'Viewed designer onboarding details: {designer.get_full_name()}',
                request=request,
                metadata={'designer_id': designer_id}
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)

        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while retrieving onboarding details',
            'detail': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    operation_summary="Verify Designer Onboarding (Deprecated)",
    operation_description="This endpoint is deprecated. Use designer_update_status instead. Updates designer profile status directly.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'verification_type': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Type of verification (final_approval to approve, reject to reject)',
                enum=['final_approval', 'reject'],
                example='final_approval'
            ),
            'notes': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Verification notes',
                example='Documents verified successfully'
            ),
            'rejection_reason': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Rejection reason (required if verification_type is reject)',
                example='Insufficient documentation'
            )
        },
        required=['verification_type']
    ),
    responses={
        200: openapi.Response(description="Designer status updated successfully"),
        404: openapi.Response(description="Designer not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_designer_onboarding(request, designer_id):
    """
    Verify designer onboarding request.
    DEPRECATED: This endpoint is kept for backward compatibility but now uses DesignerProfile.status.
    Use designer_update_status endpoint instead.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        designer = User.objects.get(id=designer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Designer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    profile = designer.created_designer_profiles.first()
    if not profile:
        return Response({
            'error': 'User is not a designer'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = DesignerOnboardingVerificationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    verification_type = serializer.validated_data['verification_type']
    notes = serializer.validated_data.get('notes', '')
    rejection_reason = serializer.validated_data.get('rejection_reason', '')
    
    # Check permissions - only superadmin can approve/reject
    if admin_profile.admin_group != 'superadmin':
        return Response({
            'error': 'Access denied. Superadmin privileges required.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Process verification - map to DesignerProfile.status
    if verification_type == 'final_approval':
        profile.status = 'verified'
        profile.updated_by = request.user
        profile.save()
        
        # Also activate user account
        designer.is_active = True
        designer.save()
        
        message = "Designer approved successfully"
        
    elif verification_type == 'reject':
        # Set status to 'rejected' to properly track rejection
        profile.status = 'rejected'
        profile.updated_by = request.user
        profile.save()
        
        # Deactivate user account
        designer.is_active = False
        designer.save()
        
        # Hide all designs from this designer (set visibility_status to 'hide')
        from Catalog.models import Product
        import logging
        
        logger = logging.getLogger(__name__)
        
        with transaction.atomic():
            # Get all designs from this designer (excluding deleted ones)
            designer_products = Product.objects.filter(
                created_by=designer
            ).exclude(status='deleted')
            
            # Hide all designs by setting visibility_status to 'hide'
            updated_count = designer_products.update(visibility_status='hide')
            
            # Log the action
            if updated_count > 0:
                pass

        message = f"Designer rejected: {rejection_reason}"
    else:
        # Legacy verification types (superadmin, moderator) - no longer used
        return Response({
            'error': f'Verification type "{verification_type}" is no longer supported. Use "final_approval" or "reject".'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'{verification_type} for designer: {designer.get_full_name()}',
        request=request,
        metadata={
            'designer_id': designer_id,
            'verification_type': verification_type,
            'notes': notes,
            'rejection_reason': rejection_reason,
            'new_status': profile.status
        }
    )
    
    return Response({
        'message': message,
        'designer': DesignerDetailSerializer(designer).data
    }, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='post',
    operation_summary="Suspend/Delete Designer Account",
    operation_description="Suspend or delete designer account (SuperAdmin only).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'action': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Action to perform',
                enum=['suspend', 'delete'],
                example='suspend'
            ),
            'reason': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Reason for action',
                enum=['policy_violation', 'fraudulent_activity', 'inactive_account', 'requested_by_designer', 'other'],
                example='policy_violation'
            ),
            'notes': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Additional notes',
                example='Account suspended due to policy violation'
            )
        },
        required=['action', 'reason']
    ),
    responses={
        200: openapi.Response(description="Account action completed successfully"),
        404: openapi.Response(description="Designer not found"),
        403: openapi.Response(description="Access denied - superadmin required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def designer_account_action(request, designer_id):
    """
    Suspend or delete designer account (SuperAdmin only).
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Only superadmins can suspend/delete accounts
    if admin_profile.admin_group != 'superadmin':
        return Response({
            'error': 'Access denied. Superadmin privileges required.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        designer = User.objects.get(id=designer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Designer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = DesignerAccountActionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    action = serializer.validated_data['action']
    reason = serializer.validated_data['reason']
    notes = serializer.validated_data.get('notes', '')
    
    from .models import DesignerAccountSuspension
    suspension, created = DesignerAccountSuspension.objects.get_or_create(
        designer=designer,
        defaults={'suspension_reason': reason}
    )
    
    if action == 'suspend':
        success = suspension.suspend_account(request.user, reason, notes, request)
        message = "Designer account suspended successfully"
        
        # TODO: Send suspension notification email to designer
        
    elif action == 'delete':
        success = suspension.delete_account(request.user, reason, notes, request)
        message = "Designer account deleted successfully"
        
        # TODO: Send deletion notification email to designer
        # TODO: Transfer ownership of approved designs to WeDesignz
    
    if not success:
        return Response({
            'error': f'Failed to {action} designer account'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'{action.title()} designer account: {designer.get_full_name()}',
        request=request,
        metadata={
            'designer_id': designer_id,
            'action': action,
            'reason': reason,
            'notes': notes
        }
    )
    
    return Response({
        'message': message,
        'suspension': DesignerAccountSuspensionSerializer(suspension).data
    }, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='get',
    operation_summary="Designer Wallet Summary",
    operation_description="Get comprehensive wallet summary for a designer (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Wallet summary retrieved successfully"),
        404: openapi.Response(description="Designer not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Designer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designer_wallet_summary(request, designer_id):
    """
    Get comprehensive wallet summary for a designer.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        designer = User.objects.get(id=designer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Designer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get designer wallets
    wallets = get_user_wallets(designer)
    
    if not wallets.exists():
        return Response({
            'message': 'No wallet found for this designer',
            'wallet_summary': {
                'wallet_balance': 0,
                'total_earnings': 0,
                'pending_payout': 0,
                'available_balance': 0,
                'can_request_payout': False
            }
        }, status=status.HTTP_200_OK)
    
    primary_wallet = wallets.first()
    
    # Calculate financial metrics using relation system
    transactions = get_related(primary_wallet, 'Wallet:WalletTransaction', WalletTransaction)
    total_earnings = transactions.filter(
        wallet_transaction_type='credit'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Payouts are manual now, so can_request_payout is based on balance only
    wallet_summary = {
        'wallet_balance': float(primary_wallet.balance),
        'total_earnings': float(total_earnings),
        'pending_payout': 0,  # No longer tracking pending payouts separately
        'available_balance': float(primary_wallet.balance),
        'can_request_payout': float(primary_wallet.balance) > 0
    }
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Viewed designer wallet summary: {designer.get_full_name()}',
        request=request,
        metadata={'designer_id': designer_id}
    )
    
    return Response({
        'designer': {
            'id': designer.id,
            'name': designer.get_full_name(),
            'email': designer.email
        },
        'wallet_summary': wallet_summary
    }, status=status.HTTP_200_OK)

# Customer Management Views

@swagger_auto_schema(
    method='get',
    operation_summary="Customers List",
    operation_description="Get list of all customers with filtering and pagination (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by account status (active, deactivated, blocked)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'plan_status',
            openapi.IN_QUERY,
            description='Filter by plan status (active, expired, none)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'search',
            openapi.IN_QUERY,
            description='Search by name, email, or phone number',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by field (created_at, updated_at, first_name, last_name, email)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_order',
            openapi.IN_QUERY,
            description='Sort order (asc, desc)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Customers retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Customer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customers_list(request):
    """
    Get list of all customers with filtering and pagination.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get all users (customers)
    customers = User.objects.all()
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        # Filter by account status using relation system
        from .models import CustomerAccountStatus
        from common.relations import get_related
        status_customers = []
        for customer in customers:
            account_statuses = get_related(customer, 'User:CustomerAccountStatus', CustomerAccountStatus)
            if account_statuses.exists():
                current_status = account_statuses.first().status
            else:
                # No status record = treat as active (default for new customers)
                current_status = 'active'
            if current_status == status_filter:
                status_customers.append(customer.id)
        customers = customers.filter(id__in=status_customers)
    
    plan_status = request.GET.get('plan_status')
    if plan_status == 'active':
        customers = customers.filter(
            created_subscriptions__status='active'
        ).distinct()
    elif plan_status == 'expired':
        customers = customers.filter(
            created_subscriptions__status='expired'
        ).distinct()
    elif plan_status == 'none':
        customers = customers.filter(
            created_subscriptions__isnull=True
        )
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        customers = customers.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(username__icontains=search_query)
        )
    
    # Sorting
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_order = request.GET.get('sort_order', 'desc')
    
    if sort_order == 'desc':
        sort_by = f'-{sort_by}'
    
    if sort_by in ['created_at', 'updated_at', 'first_name', 'last_name', 'email']:
        customers = customers.order_by(sort_by)
    else:
        customers = customers.order_by('-date_joined')
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginated_customers = paginator.paginate_queryset(customers, request)
    
    serializer = CustomerListSerializer(paginated_customers, many=True)
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='user_management',
            description='Viewed customers list',
            request=request,
            metadata={'filters': request.GET.dict()}
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

    return paginator.get_paginated_response(serializer.data)

@swagger_auto_schema(
    method='get',
    operation_summary="Customer Detail",
    operation_description="Get detailed information about a specific customer (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Customer details retrieved successfully"),
        404: openapi.Response(description="Customer not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Customer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_detail(request, customer_id):
    """
    Get detailed information about a specific customer.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        customer = User.objects.get(id=customer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Customer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = CustomerDetailSerializer(customer)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Viewed customer details: {customer.get_full_name()}',
        request=request,
        metadata={'customer_id': customer_id}
    )
    
    return Response(serializer.data, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='get',
    operation_summary="Customer History",
    operation_description="Get complete customer activity history (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'date_from',
            openapi.IN_QUERY,
            description='Filter from date (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_to',
            openapi.IN_QUERY,
            description='Filter to date (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Customer history retrieved successfully"),
        404: openapi.Response(description="Customer not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Customer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_history(request, customer_id):
    """
    Get complete customer activity history.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        customer = User.objects.get(id=customer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Customer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Apply date filters if provided
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Get view history with date filtering using relation system
    from .models import CustomerViewHistory, CustomerDownloadHistory
    from common.relations import get_related
    
    view_history = get_related(customer, 'User:CustomerViewHistory', CustomerViewHistory)
    download_history = get_related(customer, 'User:CustomerDownloadHistory', CustomerDownloadHistory)
    
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            view_history = view_history.filter(viewed_at__gte=date_from_obj)
            download_history = download_history.filter(downloaded_at__gte=date_from_obj)
        except ValueError:
            return Response({
                'error': 'Invalid date_from format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            view_history = view_history.filter(viewed_at__lte=date_to_obj)
            download_history = download_history.filter(downloaded_at__lte=date_to_obj)
        except ValueError:
            return Response({
                'error': 'Invalid date_to format. Use YYYY-MM-DD'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create history data
    history_data = {
        'customer': {
            'id': customer.id,
            'name': customer.get_full_name(),
            'email': customer.email
        },
        'view_history': CustomerViewHistorySerializer(view_history.order_by('-viewed_at'), many=True).data,
        'purchase_history': [
            {
                'id': order.id,
                'total_amount': float(order.total_amount),
                'status': order.status,
                'created_at': order.created_at
            } for order in Order.objects.filter(created_by=customer).order_by('-created_at')
        ],
        'download_history': CustomerDownloadHistorySerializer(download_history.order_by('-downloaded_at'), many=True).data,
        'active_plan': None,
        'wishlist_items': [
            {
                'id': item.id,
                'product_id': item.product.id,
                'product_title': item.product.title,
                'product_price': float(item.product.price) if item.product.price else 0,
                'added_at': item.created_at
            } for item in Cart.objects.filter(created_by=customer, cart_type='wishlist').select_related('product')
        ],
        'cart_items': [
            {
                'id': item.id,
                'product_id': item.product.id,
                'product_title': item.product.title,
                'product_price': float(item.product.price) if item.product.price else 0,
                'added_at': item.created_at
            } for item in Cart.objects.filter(created_by=customer, cart_type='cart').select_related('product')
        ]
    }
    
    # Get active subscription
    try:
        from Plans.models import Subscription
        subscription = Subscription.objects.filter(
            created_by=customer,
            status='active'
        ).select_related('plan').first()
        
        if subscription:
            from datetime import timedelta
            history_data['active_plan'] = {
                'plan_name': subscription.plan.get_plan_name_display(),
                'plan_duration': subscription.plan.get_plan_duration_display(),
                'price': float(subscription.plan.price),
                'auto_renew': subscription.auto_renew,
                'created_at': subscription.created_at,
                'expires_at': subscription.created_at + timedelta(
                    days=30 if subscription.plan.plan_duration == 'monthly' else 365
                )
            }
    except:
        pass
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Viewed customer history: {customer.get_full_name()}',
        request=request,
        metadata={'customer_id': customer_id}
    )
    
    return Response(history_data, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='post',
    operation_summary="Customer Account Action",
    operation_description="Activate or deactivate customer account (SuperAdmin and Moderator access).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'action': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Action to perform',
                enum=['activate', 'deactivate'],
                example='deactivate'
            ),
            'reason': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Deactivation reason (required for deactivation)',
                enum=['policy_violation', 'fraudulent_activity', 'inactive_account', 'requested_by_customer', 'payment_issues', 'other'],
                example='policy_violation'
            ),
            'notes': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Additional notes',
                example='Account deactivated due to policy violation'
            )
        },
        required=['action']
    ),
    responses={
        200: openapi.Response(description="Account action completed successfully"),
        404: openapi.Response(description="Customer not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Customer Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def customer_account_action(request, customer_id):
    """
    Activate or deactivate customer account.
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        customer = User.objects.get(id=customer_id)
    except User.DoesNotExist:
        return Response({
            'error': 'Customer not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = CustomerAccountActionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    action = serializer.validated_data['action']
    reason = serializer.validated_data.get('reason')
    notes = serializer.validated_data.get('notes', '')
    
    from .models import CustomerAccountStatus
    from common.relations import get_related, attach_relation
    
    # Get or create account status using relation system
    account_statuses = get_related(customer, 'User:CustomerAccountStatus', CustomerAccountStatus)
    if account_statuses.exists():
        account_status = account_statuses.first()
    else:
        account_status = CustomerAccountStatus.objects.create(
            customer_id=customer.pk,
            status='active'
        )
        # Create the relation
        attach_relation('User:CustomerAccountStatus', customer, account_status)
    
    if action == 'deactivate':
        success = account_status.deactivate_account(request.user, reason, notes, request)
        message = "Customer account deactivated successfully"
        
        # TODO: Send deactivation notification email to customer
        
    elif action == 'activate':
        success = account_status.reactivate_account(request.user, request)
        message = "Customer account activated successfully"
        
        # TODO: Send reactivation notification email to customer
    
    if not success:
        return Response({
            'error': f'Failed to {action} customer account'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'{action.title()} customer account: {customer.get_full_name()}',
        request=request,
        metadata={
            'customer_id': customer_id,
            'action': action,
            'reason': reason,
            'notes': notes
        }
    )
    
    return Response({
        'message': message,
        'account_status': {
            'status': account_status.status,
            'status_display': account_status.get_status_display(),
            'deactivation_reason': account_status.deactivation_reason,
            'deactivation_notes': account_status.deactivation_notes,
            'deactivated_by': account_status.deactivated_by.get_full_name() if account_status.deactivated_by else None,
            'deactivated_at': account_status.deactivated_at,
            'reactivated_by': account_status.reactivated_by.get_full_name() if account_status.reactivated_by else None,
            'reactivated_at': account_status.reactivated_at
        }
    }, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='get',
    operation_summary="Customer Analytics",
    operation_description="Get customer analytics and statistics (SuperAdmin only).",
    responses={
        200: openapi.Response(description="Customer analytics retrieved successfully"),
        403: openapi.Response(description="Access denied - superadmin required")
    },
    tags=['CoreAdmin Customer Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_analytics(request):
    """
    Get customer analytics and statistics (SuperAdmin only).
    """
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Only superadmins can view analytics
    if admin_profile.admin_group != 'superadmin':
        return Response({
            'error': 'Access denied. Superadmin privileges required.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get all customers
    customers = User.objects.all()
    
    # Calculate statistics
    total_customers = customers.count()
    active_customers = customers.filter(is_active=True).count()
    
    from .models import CustomerAccountStatus
    from common.relations import get_related
    
    # Count deactivated and blocked customers using relation system
    deactivated_customers = 0
    blocked_customers = 0
    
    for customer in customers:
        account_statuses = get_related(customer, 'User:CustomerAccountStatus', CustomerAccountStatus)
        if account_statuses.exists():
            account_status = account_statuses.first().status
            if account_status == 'deactivated':
                deactivated_customers += 1
            elif account_status == 'blocked':
                blocked_customers += 1
    
    # Subscription statistics
    from Plans.models import Subscription
    customers_with_subscriptions = Subscription.objects.filter(status='active').values('created_by').distinct().count()
    customers_without_subscriptions = total_customers - customers_with_subscriptions
    
    # Financial statistics
    from Orders.models import Order
    total_revenue = Order.objects.filter(status='success').aggregate(total=Sum('total_amount'))['total'] or 0
    total_orders = Order.objects.filter(status='success').count()
    average_order_value = float(total_revenue) / total_orders if total_orders > 0 else 0
    
    # Recent registrations (last 30 days)
    from datetime import timedelta
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_registrations = customers.filter(date_joined__gte=thirty_days_ago).count()
    
    # Top customers by spending
    top_customers = []
    for customer in customers[:10]:  # Top 10 customers
        customer_spent = Order.objects.filter(
            created_by=customer,
            status='success'
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        
        top_customers.append({
            'customer_id': customer.id,
            'name': customer.get_full_name(),
            'email': customer.email,
            'total_spent': float(customer_spent),
            'total_orders': Order.objects.filter(created_by=customer, status='success').count()
        })
    
    # Sort by spending
    top_customers.sort(key=lambda x: x['total_spent'], reverse=True)
    
    analytics_data = {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'deactivated_customers': deactivated_customers,
        'blocked_customers': blocked_customers,
        'customers_with_subscriptions': customers_with_subscriptions,
        'customers_without_subscriptions': customers_without_subscriptions,
        'total_revenue': float(total_revenue),
        'average_order_value': average_order_value,
        'recent_registrations': recent_registrations,
        'top_customers': top_customers[:5]  # Top 5 customers
    }
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='user_management',
            description='Viewed customer analytics',
            request=request
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

    return Response(analytics_data, status=status.HTTP_200_OK)

# ==================== DESIGN MANAGEMENT VIEWS ====================

@swagger_auto_schema(
    method='get',
    operation_summary="Designs List",
    operation_description="Get list of all designs with filtering and pagination (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by design status (active, inactive, draft, deleted)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'designer_id',
            openapi.IN_QUERY,
            description='Filter by designer ID',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'category_id',
            openapi.IN_QUERY,
            description='Filter by category ID',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'date_from',
            openapi.IN_QUERY,
            description='Filter by upload date from (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_to',
            openapi.IN_QUERY,
            description='Filter by upload date to (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'type',
            openapi.IN_QUERY,
            description='Filter by type (design, bundle)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'search',
            openapi.IN_QUERY,
            description='Search by title, description, or designer name',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by field (created_at, updated_at, title, price)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_order',
            openapi.IN_QUERY,
            description='Sort order (asc, desc)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page_size',
            openapi.IN_QUERY,
            description='Number of items per page',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Designs retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designs_list(request):
    """
    Get list of all designs with filtering and pagination.
    """
    # Ensure user is authenticated (should be handled by decorator, but double-check)
    if not request.user or not request.user.is_authenticated:
        return Response({
            'error': 'Authentication credentials were not provided',
            'detail': 'Authentication credentials were not provided'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while checking admin profile',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        # Get all products (designs)
        from Catalog.models import Product, CollectionBundle
        designs = Product.objects.all()
        bundles = CollectionBundle.objects.all()
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while loading designs',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        designs = designs.filter(status=status_filter)
        # When filtering by 'active', also filter by visibility_status='show'
        # to match the criteria used by hero section and other public endpoints
        if status_filter == 'active':
            designs = designs.filter(visibility_status='show')
    
    designer_id = request.GET.get('designer_id')
    if designer_id:
        designs = designs.filter(created_by_id=designer_id)
    
    category_id = request.GET.get('category_id')
    if category_id:
        designs = designs.filter(category_id=category_id)
    
    date_from = request.GET.get('date_from')
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            designs = designs.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    date_to = request.GET.get('date_to')
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            designs = designs.filter(created_at__lte=date_to_obj)
        except ValueError:
            pass
    
    type_filter = request.GET.get('type')
    if type_filter == 'bundle':
        # Return bundles instead of designs
        bundles = bundles.filter(status='available')
        # Apply similar filters to bundles
        if designer_id:
            bundles = bundles.filter(created_by_id=designer_id)
        
        # Search functionality
        search = request.GET.get('search')
        if search:
            bundles = bundles.filter(
                Q(name__icontains=search) |
                Q(created_by__first_name__icontains=search) |
                Q(created_by__last_name__icontains=search) |
                Q(created_by__email__icontains=search)
            )
        
        # Sorting
        sort_by = request.GET.get('sort_by', 'created_at')
        sort_order = request.GET.get('sort_order', 'desc')
        
        if sort_order == 'desc':
            sort_by = f'-{sort_by}'
        
        bundles = bundles.order_by(sort_by)
        
        # Pagination
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = bundles.count()
        bundles_page = bundles[start:end]
        
        serializer = BundleListSerializer(bundles_page, many=True)
        
        return Response({
            'message': 'Bundles retrieved successfully',
            'data': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size
            }
        })
    
    # Search functionality for designs
    search = request.GET.get('search')
    if search:
        designs = designs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(created_by__first_name__icontains=search) |
            Q(created_by__last_name__icontains=search) |
            Q(created_by__email__icontains=search)
        )
    
    # Sorting
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_order = request.GET.get('sort_order', 'desc')
    
    if sort_order == 'desc':
        sort_by = f'-{sort_by}'
    
    designs = designs.order_by(sort_by)
    
    # Pagination - accept both 'limit' and 'page_size' for compatibility
    try:
        page = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page = 1
    
    limit_param = request.GET.get('limit') or request.GET.get('page_size', 20)
    try:
        page_size = int(limit_param)
    except (ValueError, TypeError):
        page_size = 20
    start = (page - 1) * page_size
    end = start + page_size
    
    total_count = designs.count()
    designs_page = designs[start:end] if total_count > 0 else []
    
    try:
        serializer = DesignListSerializer(designs_page, many=True, context={'request': request})
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'Failed to serialize designs',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='other',
            description='Designs list viewed',
            request=request,
            metadata={
                'action': 'designs_list_viewed',
                'filters': {
                    'status': status_filter,
                    'designer_id': designer_id,
                    'category_id': category_id,
                    'date_from': date_from,
                    'date_to': date_to,
                    'search': search
                },
                'pagination': {
                    'page': page,
                    'page_size': page_size
                }
            }
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

    try:
        return Response({
            'message': 'Designs retrieved successfully',
            'data': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size if page_size > 0 else 0
            }
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while preparing the response',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary="Design Detail",
    operation_description="Get detailed information about a specific design (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Design details retrieved successfully"),
        404: openapi.Response(description="Design not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def design_detail(request, design_id):
    """
    Get detailed information about a specific design.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from Catalog.models import Product
        design = Product.objects.get(id=design_id)
    except Product.DoesNotExist:
        return Response({
            'error': 'Design not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = DesignDetailSerializer(design, context={'request': request})
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='other',
            description=f'Viewed design details: {design.title}',
            request=request,
            metadata={
                'design_id': design_id,
                'design_title': design.title
            }
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

    return Response({
        'message': 'Design details retrieved successfully',
        'data': serializer.data
    })

@swagger_auto_schema(
    method='post',
    operation_summary="Design Action",
    operation_description="Approve, reject, or disable a design (SuperAdmin and Moderator access).",
    request_body=DesignActionSerializer,
    responses={
        200: openapi.Response(description="Design action completed successfully"),
        400: openapi.Response(description="Invalid action or missing required fields"),
        404: openapi.Response(description="Design not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def design_action(request, design_id):
    """
    Approve, reject, or disable a design.
    Completely rewritten from scratch with improved error handling and logging.
    """
    import logging
    logger = logging.getLogger(__name__)

    # Step 1: Validate admin profile
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)

    except AdminUserProfile.DoesNotExist:

        return Response({
            'error': 'Admin profile required',
            'detail': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:

        return Response({
            'error': 'Internal server error',
            'detail': 'Failed to verify admin profile'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Step 2: Validate design exists (without locking - just check existence)
    try:
        from Catalog.models import Product
        # First check if design exists (without locking)
        if not Product.objects.filter(id=design_id).exists():

            return Response({
                'error': 'Design not found',
                'detail': 'Design not found'
            }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:

        return Response({
            'error': 'Internal server error',
            'detail': 'Failed to verify design'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Step 3: Validate request data
    serializer = DesignActionSerializer(data=request.data)
    if not serializer.is_valid():

        return Response({
            'error': 'Invalid data',
            'detail': 'Invalid request data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    action = serializer.validated_data['action']
    rejection_reason = serializer.validated_data.get('rejection_reason', '')
    reason = serializer.validated_data.get('reason', '')  # For flag action
    admin_notes = serializer.validated_data.get('admin_notes', '')

    # Step 4: Process action within transaction (with locking)
    from .models import DesignApproval
    from common.relations import get_related, attach_relation
    
    success = False
    message = ""
    error_detail = ""
    
    try:
        with transaction.atomic():
            # Get design with lock inside transaction
            try:
                design = Product.objects.select_for_update().get(id=design_id)

            except Product.DoesNotExist:

                return Response({
                    'error': 'Design not found',
                    'detail': 'Design not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Handle flag actions separately (they don't use DesignApproval)
            if action == 'flag':

                # Store flag information in product_metadata
                if not design.product_metadata:
                    design.product_metadata = {}
                # Store previous visibility_status before hiding (so we can restore it later)
                design.product_metadata['previous_visibility_status'] = design.visibility_status
                design.product_metadata['flagged'] = True
                design.product_metadata['flag_reason'] = reason
                design.product_metadata['flagged_by'] = request.user.id
                design.product_metadata['flagged_at'] = timezone.now().isoformat()
                # Use update() to bypass signals - hide design from feed by setting visibility_status to 'hide'
                Product.objects.filter(pk=design.pk).update(
                    product_metadata=design.product_metadata,
                    visibility_status='hide'
                )
                success = True
                message = "Design flagged successfully and hidden from feed"

            elif action == 'resolve_flag':

                # Get previous visibility_status before clearing flag (default to 'show' if not stored)
                previous_visibility = 'show'
                if design.product_metadata:
                    previous_visibility = design.product_metadata.get('previous_visibility_status', 'show')
                    design.product_metadata.pop('flagged', None)
                    design.product_metadata.pop('flag_reason', None)
                    design.product_metadata.pop('flagged_by', None)
                    design.product_metadata.pop('flagged_at', None)
                    design.product_metadata.pop('previous_visibility_status', None)
                # Use update() to bypass signals - restore visibility_status to previous value
                Product.objects.filter(pk=design.pk).update(
                    product_metadata=design.product_metadata,
                    visibility_status=previous_visibility
                )
                success = True
                message = "Flag resolved successfully and design restored to feed"

            else:
                # Get or create design approval record for approve/reject/disable actions

                # Try to get existing approval record directly by product_id (faster than get_related)
                approval = None
                try:
                    approval = DesignApproval.objects.filter(product_id=design.pk).first()
                    if approval:
                        pass
                except Exception as e:
                    pass

                # Create new approval if not found
                if not approval:

                    try:
                        approval = DesignApproval.objects.create(
                            product_id=design.pk,
                            action='pending'
                        )

                        # Try to attach relation (non-blocking - skip if it fails)
                        try:
                            attach_relation('Product:DesignApproval', design, approval, created_by=request.user)
                        except Exception as rel_error:
                            pass
                    except Exception as e:

                        raise
                
                # Execute the action
                if action == 'approve':

                    try:
                        success = approval.approve_design(request.user, admin_notes, request)
                        message = "Design approved successfully"
                        if success:
                            pass
                        else:
                            error_detail = "Failed to approve design - check logs for details"
                    except Exception as e:

                        raise
                        
                elif action == 'reject':

                    success = approval.reject_design(request.user, rejection_reason, admin_notes, request)
                    message = "Design rejected successfully"
                    if success:
                        pass
                    else:
                        error_detail = "Failed to reject design - check logs for details"
                        
                elif action == 'disable':

                    success = approval.disable_design(request.user, admin_notes, request)
                    message = "Design disabled successfully"
                    if success:
                        pass
                    else:
                        error_detail = "Failed to disable design - check logs for details"
                else:

                    error_detail = f"Unknown action: {action}"
            
            # Refresh design from database to get updated status
            if success:
                design.refresh_from_db()

    except Exception as e:

        return Response({
            'error': 'Internal server error',
            'detail': f'Failed to process action: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # Step 5: Return response IMMEDIATELY (skip activity logging to ensure fast response)
    if success:
        response_data = {
            'message': message,
            # Don't include 'detail' in success responses - transformResponse treats it as an error
            'data': {
                'design_id': design_id,
                'action': action,
                'status': design.status
            }
        }

        # Return response immediately - activity logging will be handled by middleware if needed
        # Skip manual logging here to ensure fast response
        return Response(response_data, status=status.HTTP_200_OK)
    else:

        return Response({
            'error': 'Failed to perform action',
            'detail': error_detail or 'Failed to perform action'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_summary="Categories List",
    operation_description="Get list of all categories with hierarchy (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Categories retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def categories_list(request):
    """
    Get list of all categories with hierarchy.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from Catalog.models import Category
    # Get only parent categories (categories without a parent) and prefetch subcategories
    # Use select_related and prefetch_related to optimize queries
    categories = Category.objects.filter(
        parent__isnull=True
    ).prefetch_related(
        'subcategories'
    ).select_related(
        'created_by', 'updated_by'
    ).order_by('name')
    
    serializer = CategorySerializer(categories, many=True)
    
    # Log activity (shortened activity_type to fit varchar(20) constraint)
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='CATEGORIES_VIEWED',
            description='Viewed categories list',
            request=request,
            metadata={}
        )
    except Exception:
        # If activity logging fails, continue anyway
        pass
    
    return Response({
        'message': 'Categories retrieved successfully',
        'data': serializer.data
    })

@swagger_auto_schema(
    method='post',
    operation_summary="Create Category",
    operation_description="Create a new category (SuperAdmin access only).",
    request_body=CategorySerializer,
    responses={
        201: openapi.Response(description="Category created successfully"),
        400: openapi.Response(description="Invalid data"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_category(request):
    """
    Create a new category.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Ensure parent_id is None for parent categories
    data = request.data.copy()
    data['parent_id'] = None
    # Remove any created_by fields (read-only) - we'll set it via context
    data.pop('created_by', None)
    data.pop('created_by_id', None)
    
    # Pass created_by and request via context so serializer can use it
    serializer = CategorySerializer(
        data=data, 
        context={
            'created_by': request.user,
            'request': request
        }
    )
    if serializer.is_valid():
        category = serializer.save()
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='CATEGORY_CREATED',
                description=f'Created category: {category.name}',
                request=request,
                metadata={
                    'category_id': category.id,
                    'category_name': category.name
                }
            )
        except Exception:
            # If activity logging fails, continue anyway
            pass
        
        return Response({
            'message': 'Category created successfully',
            'data': CategorySerializer(category).data
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='put',
    operation_summary="Update Category",
    operation_description="Update a category's name and/or icon (SuperAdmin access only).",
    request_body=CategorySerializer,
    responses={
        200: openapi.Response(description="Category updated successfully"),
        400: openapi.Response(description="Invalid data"),
        404: openapi.Response(description="Category not found"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_category(request, category_id):
    """
    Update a category's name and/or icon.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from Catalog.models import Category
    
    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return Response({
            'error': 'Category not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Prepare data for update - only allow name and icon_name to be updated
    data = request.data.copy()
    # Only allow updating name and icon_name
    # If name is provided, use it; otherwise keep existing
    # If icon_name is provided (including empty string), use it; otherwise keep existing
    update_data = {}
    if 'name' in data:
        update_data['name'] = data.get('name')
    if 'icon_name' in data:
        update_data['icon_name'] = data.get('icon_name') or None
    
    # Remove fields that shouldn't be updated
    data.pop('parent_id', None)
    data.pop('parent', None)
    data.pop('created_by', None)
    data.pop('created_by_id', None)
    
    # Pass updated_by via context
    serializer = CategorySerializer(
        category,
        data=update_data,
        partial=True,
        context={
            'updated_by': request.user,
            'request': request
        }
    )
    
    if serializer.is_valid():
        category = serializer.save()
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='CATEGORY_UPDATED',
                description=f'Updated category: {category.name}',
                request=request,
                metadata={
                    'category_id': category.id,
                    'category_name': category.name,
                    'icon_name': category.icon_name
                }
            )
        except Exception:
            # If activity logging fails, continue anyway
            pass
        
        return Response({
            'message': 'Category updated successfully',
            'data': CategorySerializer(category).data
        }, status=status.HTTP_200_OK)
    else:
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='delete',
    operation_summary="Delete Category",
    operation_description="Delete a category or subcategory (SuperAdmin access only).",
    responses={
        200: openapi.Response(description="Category deleted successfully"),
        404: openapi.Response(description="Category not found"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required"),
        400: openapi.Response(description="Cannot delete category with products or subcategories")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_category(request, category_id):
    """
    Delete a category or subcategory.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from Catalog.models import Category, Product
    
    try:
        category = Category.objects.get(id=category_id)
    except Category.DoesNotExist:
        return Response({
            'error': 'Category not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    category_name = category.name
    
    # Check if category has products
    products_count = Product.objects.filter(category=category).count()
    if products_count > 0:
        return Response({
            'error': f'Cannot delete category. It has {products_count} product(s). Please remove or reassign products first.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if it's a parent category with subcategories
    if category.parent is None:
        subcategories_count = category.subcategories.count()
        if subcategories_count > 0:
            return Response({
                'error': f'Cannot delete category. It has {subcategories_count} subcategor{("ies" if subcategories_count > 1 else "y")}. Please delete subcategories first.'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='CATEGORY_DELETED',
            description=f'Deleted category: {category_name}',
            request=request,
            metadata={
                'category_id': category.id,
                'category_name': category_name
            }
        )
    except Exception:
        # If activity logging fails, continue anyway
        pass
    
    category.delete()
    
    return Response({
        'message': 'Category deleted successfully',
        'data': {
            'category_id': category_id,
            'category_name': category_name
        }
    }, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='get',
    operation_summary="Tags List",
    operation_description="Get list of all tags (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Tags retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tags_list(request):
    """
    Get list of all tags.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from Catalog.models import Tags
    tags = Tags.objects.all().order_by('name')
    
    serializer = TagSerializer(tags, many=True)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='TAGS_LIST_VIEWED',
        ip_address=AdminActivityLog.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={}
    )
    
    return Response({
        'message': 'Tags retrieved successfully',
        'data': serializer.data
    })

@swagger_auto_schema(
    method='get',
    operation_summary="Copyright Reports List",
    operation_description="Get list of all copyright violation reports (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by report status (pending, resolved, rejected, design_disabled)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'priority',
            openapi.IN_QUERY,
            description='Filter by priority (low, medium, high, urgent)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page_size',
            openapi.IN_QUERY,
            description='Number of items per page',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Copyright reports retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def copyright_reports_list(request):
    """
    Get list of all copyright violation reports.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from .models import CopyrightReport
    reports = CopyrightReport.objects.all()
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        reports = reports.filter(status=status_filter)
    
    priority_filter = request.GET.get('priority')
    if priority_filter:
        reports = reports.filter(priority=priority_filter)
    
    # Sorting
    reports = reports.order_by('-created_at')
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    
    total_count = reports.count()
    reports_page = reports[start:end]
    
    serializer = CopyrightReportSerializer(reports_page, many=True)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='COPYRIGHT_REPORTS_LIST_VIEWED',
        ip_address=AdminActivityLog.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={
            'filters': {
                'status': status_filter,
                'priority': priority_filter
            },
            'pagination': {
                'page': page,
                'page_size': page_size
            }
        }
    )
    
    return Response({
        'message': 'Copyright reports retrieved successfully',
        'data': serializer.data,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size
        }
    })

@swagger_auto_schema(
    method='post',
    operation_summary="Copyright Report Action",
    operation_description="Resolve, reject, or disable design due to copyright violation (SuperAdmin and Moderator access).",
    request_body=CopyrightReportActionSerializer,
    responses={
        200: openapi.Response(description="Copyright report action completed successfully"),
        400: openapi.Response(description="Invalid action or missing required fields"),
        404: openapi.Response(description="Report not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def copyright_report_action(request, report_id):
    """
    Resolve, reject, or disable design due to copyright violation.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from .models import CopyrightReport
        report = CopyrightReport.objects.get(id=report_id)
    except CopyrightReport.DoesNotExist:
        return Response({
            'error': 'Report not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = CopyrightReportActionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    action = serializer.validated_data['action']
    resolution = serializer.validated_data.get('resolution', '')
    admin_notes = serializer.validated_data.get('admin_notes', '')
    
    success = False
    message = ""
    
    if action == 'resolve':
        success = report.resolve_report(request.user, resolution, admin_notes, request)
        message = "Copyright report resolved successfully"
    elif action == 'reject':
        success = report.reject_report(request.user, admin_notes, request)
        message = "Copyright report rejected successfully"
    elif action == 'disable_design':
        success = report.disable_design(request.user, resolution, admin_notes, request)
        message = "Design disabled due to copyright violation"
    
    if success:
        # Log activity
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type=f'COPYRIGHT_REPORT_{action.upper()}',
            ip_address=AdminActivityLog.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            metadata={
                'report_id': report_id,
                'action': action,
                'resolution': resolution,
                'admin_notes': admin_notes
            }
        )
        
        return Response({
            'message': message,
            'data': {
                'report_id': report_id,
                'action': action,
                'status': report.status
            }
        })
    else:
        return Response({
            'error': 'Failed to perform action'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_summary="Design Analytics",
    operation_description="Get design analytics and performance metrics (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'designer_id',
            openapi.IN_QUERY,
            description='Filter by designer ID',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'category_id',
            openapi.IN_QUERY,
            description='Filter by category ID',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by design status',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_from',
            openapi.IN_QUERY,
            description='Filter by date from (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_to',
            openapi.IN_QUERY,
            description='Filter by date to (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by field (total_views, total_downloads, total_purchases, revenue_generated, trending_score)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_order',
            openapi.IN_QUERY,
            description='Sort order (asc, desc)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page_size',
            openapi.IN_QUERY,
            description='Number of items per page',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Design analytics retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def design_analytics(request):
    """
    Get design analytics and performance metrics.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from Catalog.models import Product
    from .models import DesignAnalytics
    from common.relations import get_related
    
    # Get all products
    products = Product.objects.all()
    
    # Apply filters
    designer_id = request.GET.get('designer_id')
    if designer_id:
        products = products.filter(created_by_id=designer_id)
    
    category_id = request.GET.get('category_id')
    if category_id:
        products = products.filter(category_id=category_id)
    
    status_filter = request.GET.get('status')
    if status_filter:
        products = products.filter(status=status_filter)
    
    date_from = request.GET.get('date_from')
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            products = products.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    date_to = request.GET.get('date_to')
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            products = products.filter(created_at__lte=date_to_obj)
        except ValueError:
            pass
    
    # Get analytics for each product
    analytics_data = []
    for product in products:
        # Get analytics using relation system
        analytics = get_related(product, 'Product:DesignAnalytics', DesignAnalytics)
        if analytics.exists():
            analytics_obj = analytics.first()
        else:
            # Create default analytics if not exists
            analytics_obj = DesignAnalytics.objects.create(
                product_id=product.pk
            )
            # Create the relation
            from common.relations import attach_relation
            attach_relation('Product:DesignAnalytics', product, analytics_obj)
        
        analytics_data.append({
            'design_id': product.id,
            'design_title': product.title,
            'designer_name': product.created_by.get_full_name(),
            'category_name': product.category.name,
            'status': product.status,
            'total_views': analytics_obj.total_views,
            'total_downloads': analytics_obj.total_downloads,
            'total_purchases': analytics_obj.total_purchases,
            'average_rating': analytics_obj.average_rating,
            'revenue_generated': float(analytics_obj.total_revenue),
            'trending_score': analytics_obj.trending_score,
            'created_at': product.created_at,
            'last_activity': analytics_obj.updated_at
        })
    
    # Sorting
    sort_by = request.GET.get('sort_by', 'trending_score')
    sort_order = request.GET.get('sort_order', 'desc')
    
    if sort_order == 'desc':
        analytics_data.sort(key=lambda x: x[sort_by], reverse=True)
    else:
        analytics_data.sort(key=lambda x: x[sort_by])
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    
    total_count = len(analytics_data)
    analytics_page = analytics_data[start:end]
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='other',
            description='Design analytics viewed',
            request=request,
            metadata={
                'action': 'design_analytics_viewed',
                'filters': {
                    'designer_id': designer_id,
                    'category_id': category_id,
                    'status': status_filter,
                    'date_from': date_from,
                    'date_to': date_to
                },
                'pagination': {
                    'page': page,
                    'page_size': page_size
                }
            }
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

    return Response({
        'message': 'Design analytics retrieved successfully',
        'data': analytics_page,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size
        }
    })

@swagger_auto_schema(
    method='get',
    operation_summary="Design Statistics",
    operation_description="Get design statistics (total, pending, approved, rejected counts) (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Design statistics retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Design Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def design_stats(request):
    """
    Get design statistics - counts by status.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from Catalog.models import Product
        
        # Count designs by status
        total = Product.objects.count()
        pending = Product.objects.filter(status='draft').count()
        approved = Product.objects.filter(status='active').count()
        rejected = Product.objects.filter(status='inactive').count()
        
        stats_data = {
            'total': total,
            'pending': pending,
            'approved': approved,
            'rejected': rejected
        }
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='other',
                description='Design statistics viewed',
                request=request,
                metadata={
                    'action': 'design_stats_viewed',
                    'stats': stats_data
                }
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)

        return Response(stats_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while retrieving design statistics',
            'detail': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== TRANSACTION MANAGEMENT VIEWS ====================

@swagger_auto_schema(
    method='get',
    operation_summary="Transactions List",
    operation_description="Get list of all transactions with filtering and pagination (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'transaction_type',
            openapi.IN_QUERY,
            description='Filter by transaction type (plan, bundle, design, custom, withdrawal)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_from',
            openapi.IN_QUERY,
            description='Filter by date from (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_to',
            openapi.IN_QUERY,
            description='Filter by date to (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by status (pending, success, failed)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'user_id',
            openapi.IN_QUERY,
            description='Filter by user ID',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'razorpay_payment_id',
            openapi.IN_QUERY,
            description='Filter by Razorpay payment ID',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by field (created_at, total_amount, status)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_order',
            openapi.IN_QUERY,
            description='Sort order (asc, desc)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page_size',
            openapi.IN_QUERY,
            description='Number of items per page',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Transactions retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Transaction Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transactions_list(request):
    """
    Get list of all transactions with filtering and pagination.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from Orders.models import Order
    from Razorpay.models import RazorpayPayment
    
    # Get all orders (transactions)
    orders = Order.objects.all()
    
    # Apply filters
    transaction_type = request.GET.get('transaction_type')
    if transaction_type:
        # TODO: Implement transaction type filtering based on order content
        pass
    
    date_from = request.GET.get('date_from')
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            orders = orders.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    date_to = request.GET.get('date_to')
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            orders = orders.filter(created_at__lte=date_to_obj)
        except ValueError:
            pass
    
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    user_id = request.GET.get('user_id')
    if user_id:
        orders = orders.filter(created_by_id=user_id)
    
    razorpay_payment_id = request.GET.get('razorpay_payment_id')
    if razorpay_payment_id:
        # Filter by Razorpay payment ID
        payments = RazorpayPayment.objects.filter(razorpay_payment_id=razorpay_payment_id)
        order_ids = [payment.order.id for payment in payments if payment.order]
        orders = orders.filter(id__in=order_ids)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        from django.db.models import Q
        # Search by order_number, razorpay payment ID, or razorpay order ID
        search_filter = Q(order_number__icontains=search_query)
        
        # Search in related RazorpayPayment records
        razorpay_payments = RazorpayPayment.objects.filter(
            Q(razorpay_payment_id__icontains=search_query) |
            Q(razorpay_order_id__icontains=search_query)
        )
        if razorpay_payments.exists():
            order_ids_from_payments = [p.order_id for p in razorpay_payments if p.order_id]
            search_filter |= Q(id__in=order_ids_from_payments)
        
        # Also search by customer name/email
        search_filter |= Q(created_by__first_name__icontains=search_query)
        search_filter |= Q(created_by__last_name__icontains=search_query)
        search_filter |= Q(created_by__email__icontains=search_query)
        search_filter |= Q(created_by__username__icontains=search_query)
        
        orders = orders.filter(search_filter)
    
    # Sorting
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_order = request.GET.get('sort_order', 'desc')
    
    if sort_order == 'desc':
        sort_by = f'-{sort_by}'
    
    orders = orders.order_by(sort_by)
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    
    total_count = orders.count()
    orders_page = orders[start:end]
    
    serializer = TransactionListSerializer(orders_page, many=True)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Viewed transactions list with filters: status: {status_filter or "all"}, user_id: {user_id or "all"}',
        request=request,
        metadata={
            'filters': {
                'transaction_type': transaction_type,
                'date_from': date_from,
                'date_to': date_to,
                'status': status_filter,
                'user_id': user_id,
                'razorpay_payment_id': razorpay_payment_id
            },
            'pagination': {
                'page': page,
                'page_size': page_size
            }
        }
    )
    
    return Response({
        'message': 'Transactions retrieved successfully',
        'data': serializer.data,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size
        }
    })

@swagger_auto_schema(
    method='get',
    operation_summary="Transaction Detail",
    operation_description="Get detailed information about a specific transaction (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Transaction details retrieved successfully"),
        404: openapi.Response(description="Transaction not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Transaction Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_detail(request, transaction_id):
    """
    Get detailed information about a specific transaction.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from Orders.models import Order
        order = Order.objects.get(id=transaction_id)
    except Order.DoesNotExist:
        return Response({
            'error': 'Transaction not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = TransactionDetailSerializer(order)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='TRANSACTION_DETAIL_VIEWED',
        ip_address=AdminActivityLog.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={
            'transaction_id': transaction_id,
            'order_id': order.id
        }
    )
    
    return Response({
        'message': 'Transaction details retrieved successfully',
        'data': serializer.data
    })

@swagger_auto_schema(
    method='post',
    operation_summary="Initiate Refund",
    operation_description="Initiate a refund for a transaction (SuperAdmin access only).",
    request_body=RefundRequestSerializer,
    responses={
        201: openapi.Response(description="Refund initiated successfully"),
        400: openapi.Response(description="Invalid data or transaction not eligible for refund"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['CoreAdmin Transaction Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_refund(request):
    """
    Initiate a refund for a transaction.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = RefundRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    transaction_id = serializer.validated_data['transaction_id']
    refund_amount = serializer.validated_data['refund_amount']
    refund_reason = serializer.validated_data['refund_reason']
    admin_notes = serializer.validated_data.get('admin_notes', '')
    
    from .models import Refund
    from common.relations import attach_relation
    
    # Create refund record
    refund = Refund.objects.create(
        order_id=transaction_id,
        refund_amount=refund_amount,
        refund_reason=refund_reason,
        admin_notes=admin_notes,
        ip_address=AdminActivityLog.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Create the relation
    from Orders.models import Order
    order = Order.objects.get(id=transaction_id)
    attach_relation('Order:Refund', order, refund)
    
    # TODO: Call Razorpay refund API
    # TODO: Update refund status based on Razorpay response
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='REFUND_INITIATED',
        ip_address=AdminActivityLog.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={
            'transaction_id': transaction_id,
            'refund_id': refund.id,
            'refund_amount': float(refund_amount),
            'refund_reason': refund_reason
        }
    )
    
    return Response({
        'message': 'Refund initiated successfully',
        'data': {
            'refund_id': refund.id,
            'transaction_id': transaction_id,
            'refund_amount': float(refund_amount),
            'status': refund.status
        }
    }, status=status.HTTP_201_CREATED)

@swagger_auto_schema(
    method='get',
    operation_summary="Refunds List",
    operation_description="Get list of all refunds with filtering and pagination (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by refund status (pending, processed, failed, completed)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_from',
            openapi.IN_QUERY,
            description='Filter by date from (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_to',
            openapi.IN_QUERY,
            description='Filter by date to (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'user_id',
            openapi.IN_QUERY,
            description='Filter by user ID',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'processed_by_id',
            openapi.IN_QUERY,
            description='Filter by processed by admin ID',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by field (created_at, refund_amount, status)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_order',
            openapi.IN_QUERY,
            description='Sort order (asc, desc)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page_size',
            openapi.IN_QUERY,
            description='Number of items per page',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Refunds retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Transaction Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def refunds_list(request):
    """
    Get list of all refunds with filtering and pagination.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from .models import Refund
    refunds = Refund.objects.all()
    
    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        refunds = refunds.filter(status=status_filter)
    
    date_from = request.GET.get('date_from')
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            refunds = refunds.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    date_to = request.GET.get('date_to')
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            refunds = refunds.filter(created_at__lte=date_to_obj)
        except ValueError:
            pass
    
    user_id = request.GET.get('user_id')
    if user_id:
        # Filter by user through order relation
        from Orders.models import Order
        user_orders = Order.objects.filter(created_by_id=user_id)
        order_ids = [order.id for order in user_orders]
        refunds = refunds.filter(order_id__in=order_ids)
    
    processed_by_id = request.GET.get('processed_by_id')
    if processed_by_id:
        refunds = refunds.filter(processed_by_id=processed_by_id)
    
    # Sorting
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_order = request.GET.get('sort_order', 'desc')
    
    if sort_order == 'desc':
        sort_by = f'-{sort_by}'
    
    refunds = refunds.order_by(sort_by)
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    
    total_count = refunds.count()
    refunds_page = refunds[start:end]
    
    serializer = RefundListSerializer(refunds_page, many=True)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='REFUNDS_LIST_VIEWED',
        ip_address=AdminActivityLog.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={
            'filters': {
                'status': status_filter,
                'date_from': date_from,
                'date_to': date_to,
                'user_id': user_id,
                'processed_by_id': processed_by_id
            },
            'pagination': {
                'page': page,
                'page_size': page_size
            }
        }
    )
    
    return Response({
        'message': 'Refunds retrieved successfully',
        'data': serializer.data,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size
        }
    })

@swagger_auto_schema(
    method='get',
    operation_summary="Orders List",
    operation_description="Get list of all orders with filtering and pagination (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'order_type',
            openapi.IN_QUERY,
            description='Filter by order type (plan, bundle, design, custom)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_from',
            openapi.IN_QUERY,
            description='Filter by date from (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_to',
            openapi.IN_QUERY,
            description='Filter by date to (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by status (pending, success, failed)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'user_id',
            openapi.IN_QUERY,
            description='Filter by user ID',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by field (created_at, total_amount, status)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_order',
            openapi.IN_QUERY,
            description='Sort order (asc, desc)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page_size',
            openapi.IN_QUERY,
            description='Number of items per page',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Orders retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Transaction Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def orders_list(request):
    """
    Get list of all orders with filtering and pagination.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from Orders.models import Order
    from Razorpay.models import RazorpayPayment
    
    # Prefetch related RazorpayPayment instances for better performance
    orders = Order.objects.prefetch_related('razorpay_payments').all()
    
    # Apply filters
    order_type = request.GET.get('order_type')
    if order_type:
        orders = orders.filter(order_type=order_type)
    
    date_from = request.GET.get('date_from')
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            orders = orders.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    date_to = request.GET.get('date_to')
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            orders = orders.filter(created_at__lte=date_to_obj)
        except ValueError:
            pass
    
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    user_id = request.GET.get('user_id')
    if user_id:
        orders = orders.filter(created_by_id=user_id)
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        from django.db.models import Q
        # Search by order_number, razorpay payment ID, or razorpay order ID
        search_filter = Q(order_number__icontains=search_query)
        
        # Search in related RazorpayPayment records
        razorpay_payments = RazorpayPayment.objects.filter(
            Q(razorpay_payment_id__icontains=search_query) |
            Q(razorpay_order_id__icontains=search_query)
        )
        if razorpay_payments.exists():
            order_ids_from_payments = [p.order_id for p in razorpay_payments if p.order_id]
            search_filter |= Q(id__in=order_ids_from_payments)
        
        # Also search by customer name/email
        search_filter |= Q(created_by__first_name__icontains=search_query)
        search_filter |= Q(created_by__last_name__icontains=search_query)
        search_filter |= Q(created_by__email__icontains=search_query)
        search_filter |= Q(created_by__username__icontains=search_query)
        
        orders = orders.filter(search_filter)
    
    # Sorting
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_order = request.GET.get('sort_order', 'desc')
    
    if sort_order == 'desc':
        sort_by = f'-{sort_by}'
    
    orders = orders.order_by(sort_by)
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    
    total_count = orders.count()
    orders_page = orders[start:end]
    
    serializer = OrderListSerializer(orders_page, many=True)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Viewed orders list with filters: {order_type or "all types"}, status: {status_filter or "all"}',
        request=request,
        metadata={
            'filters': {
                'order_type': order_type,
                'date_from': date_from,
                'date_to': date_to,
                'status': status_filter,
                'user_id': user_id
            },
            'pagination': {
                'page': page,
                'page_size': page_size
            }
        }
    )
    
    return Response({
        'message': 'Orders retrieved successfully',
        'data': serializer.data,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size
        }
    })

@swagger_auto_schema(
    method='get',
    operation_summary="Order Detail",
    operation_description="Get detailed information about a specific order (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Order details retrieved successfully"),
        404: openapi.Response(description="Order not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Transaction Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def order_detail(request, order_id):
    """
    Get detailed information about a specific order.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from Orders.models import Order
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({
            'error': 'Order not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = OrderDetailSerializer(order)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='ORDER_DETAIL_VIEWED',
        ip_address=AdminActivityLog.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={
            'order_id': order_id
        }
    )
    
    return Response({
        'message': 'Order details retrieved successfully',
        'data': serializer.data
    })

@swagger_auto_schema(
    method='post',
    operation_summary="Update Order Status",
    operation_description="Update order status (SuperAdmin access only).",
    request_body=OrderStatusUpdateSerializer,
    responses={
        200: openapi.Response(description="Order status updated successfully"),
        400: openapi.Response(description="Invalid data"),
        404: openapi.Response(description="Order not found"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['CoreAdmin Transaction Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_order_status(request, order_id):
    """
    Update order status.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from Orders.models import Order
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return Response({
            'error': 'Order not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = OrderStatusUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    new_status = serializer.validated_data['status']
    admin_notes = serializer.validated_data.get('admin_notes', '')
    
    # Update order status
    old_status = order.status
    order.status = new_status
    order.updated_by = request.user
    order.save()
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='ORDER_STATUS_UPDATED',
        ip_address=AdminActivityLog.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={
            'order_id': order_id,
            'old_status': old_status,
            'new_status': new_status,
            'admin_notes': admin_notes
        }
    )
    
    return Response({
        'message': 'Order status updated successfully',
        'data': {
            'order_id': order_id,
            'old_status': old_status,
            'new_status': new_status
        }
    })

@swagger_auto_schema(
    method='get',
    operation_summary="Financial Reports",
    operation_description="Generate financial reports (SuperAdmin access only).",
    manual_parameters=[
        openapi.Parameter(
            'report_type',
            openapi.IN_QUERY,
            description='Report type (daily, monthly, yearly)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_from',
            openapi.IN_QUERY,
            description='Start date for custom period (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'date_to',
            openapi.IN_QUERY,
            description='End date for custom period (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'export_format',
            openapi.IN_QUERY,
            description='Export format (json, csv, pdf)',
            type=openapi.TYPE_STRING
        )
    ],
    responses={
        200: openapi.Response(description="Financial report generated successfully"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['CoreAdmin Transaction Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financial_reports(request):
    """
    Generate financial reports.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    report_type = request.GET.get('report_type', 'daily')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    export_format = request.GET.get('export_format', 'json')
    
    # Calculate date range based on report type
    from datetime import datetime, timedelta
    now = timezone.now()
    
    if report_type == 'daily':
        period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    elif report_type == 'monthly':
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    elif report_type == 'yearly':
        period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = now
    else:
        # Custom period
        if date_from and date_to:
            try:
                period_start = datetime.strptime(date_from, '%Y-%m-%d')
                period_end = datetime.strptime(date_to, '%Y-%m-%d')
            except ValueError:
                return Response({
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'error': 'date_from and date_to are required for custom period'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Generate report data
    from Orders.models import Order
    from .models import Refund, FinancialReport
    
    # Get orders in period
    orders = Order.objects.filter(
        created_at__gte=period_start,
        created_at__lte=period_end
    )
    
    # Calculate metrics
    total_transactions = orders.count()
    total_amount = orders.aggregate(total=Sum('total_amount'))['total'] or 0
    successful_orders = orders.filter(status='success')
    successful_amount = successful_orders.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Get refunds in period
    refunds = Refund.objects.filter(
        created_at__gte=period_start,
        created_at__lte=period_end
    )
    total_refunds = refunds.aggregate(total=Sum('refund_amount'))['total'] or 0
    
    # Calculate net revenue
    net_revenue = float(successful_amount) - float(total_refunds)
    
    # TODO: Calculate breakdown by transaction type
    # TODO: Calculate pending settlements
    # Calculate platform commission from settings
    from common.business_config import BusinessConfig
    platform_commission = BusinessConfig.calculate_commission_amount(total_amount)
    
    # Create financial report record
    report = FinancialReport.objects.create(
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        total_transactions=total_transactions,
        total_amount=total_amount,
        total_refunds=total_refunds,
        net_revenue=net_revenue,
        generated_by_id=request.user.pk
    )
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='data_export',
        description=f'Generated {report_type} financial report for period {period_start.date()} to {period_end.date()}',
        request=request,
        metadata={
            'report_type': report_type,
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'export_format': export_format
        }
    )
    
    return Response({
        'message': 'Financial report generated successfully',
        'data': report.get_report_summary(),
        'report_id': report.id
    })

# ==================== CUSTOM ORDER MANAGEMENT VIEWS ====================

@swagger_auto_schema(
    method='get',
    operation_summary="Custom Orders List",
    operation_description="Get list of all custom orders with filtering and pagination (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by order status (pending, in_progress, completed, cancelled, delayed)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sla_status',
            openapi.IN_QUERY,
            description='Filter by SLA status (normal, warning, critical, breached, completed)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'assigned_to_id',
            openapi.IN_QUERY,
            description='Filter by assigned admin ID',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'created_after',
            openapi.IN_QUERY,
            description='Filter by creation date from (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'created_before',
            openapi.IN_QUERY,
            description='Filter by creation date to (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'search',
            openapi.IN_QUERY,
            description='Search by title or description',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by field (created_at, sla_deadline, status)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_order',
            openapi.IN_QUERY,
            description='Sort order (asc, desc)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page_size',
            openapi.IN_QUERY,
            description='Number of items per page',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Custom orders retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Custom Order Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def custom_orders_list(request):
    """
    Get list of all custom orders with filtering and pagination.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from CustomRequests.models import CustomOrderRequest
    from CustomRequests.serializers import CustomOrderListSerializer, CustomOrderFilterSerializer
    import logging
    logger = logging.getLogger(__name__)
    
    # Only show custom orders that have been paid (have an associated Order).
    # Unpaid CustomOrderRequests (user closed Razorpay) are not shown in the admin list.
    orders = CustomOrderRequest.objects.select_related('order').exclude(order__isnull=True)

    # Apply filters
    # Only pass filter-related params to the serializer, not pagination params
    filter_params = {k: v for k, v in request.GET.items() if k not in ['page', 'page_size', 'limit', 'sort_by', 'sort_order']}
    filter_serializer = CustomOrderFilterSerializer(data=filter_params)

    if filter_serializer.is_valid():
        filters = filter_serializer.validated_data

        if filters.get('status'):
            orders = orders.filter(status=filters['status'])
        
        if filters.get('assigned_to_id'):
            orders = orders.filter(assigned_to_id=filters['assigned_to_id'])
        
        if filters.get('created_after'):
            orders = orders.filter(created_at__gte=filters['created_after'])
        
        if filters.get('created_before'):
            orders = orders.filter(created_at__lte=filters['created_before'])
        
        # Only apply has_budget filter if it's explicitly provided (not default False)
        # Check if 'has_budget' was actually in the request params, not just defaulted
        if 'has_budget' in request.GET and filters.get('has_budget') is not None:
            if filters['has_budget']:
                orders = orders.exclude(budget__isnull=True)
            else:
                orders = orders.filter(budget__isnull=True)
        
        if filters.get('min_budget'):
            orders = orders.filter(budget__gte=filters['min_budget'])
        
        if filters.get('max_budget'):
            orders = orders.filter(budget__lte=filters['max_budget'])
        
        if filters.get('search'):
            search_term = filters['search']
            orders = orders.filter(
                Q(title__icontains=search_term) | 
                Q(description__icontains=search_term)
            )
    
    # SLA status filtering (post-processing)
    sla_status_filter = request.GET.get('sla_status')
    if sla_status_filter:

        # Convert queryset to list before filtering
        orders_list = list(orders)
        filtered_orders = []
        for order in orders_list:
            if order.get_sla_status() == sla_status_filter:
                filtered_orders.append(order)
        orders = filtered_orders

    else:
        pass

    # Sorting
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_order = request.GET.get('sort_order', 'desc')
    
    # Only apply order_by if orders is still a queryset (not a list from SLA filtering)
    if not isinstance(orders, list):
        if sort_order == 'desc':
            sort_by = f'-{sort_by}'
        orders = orders.order_by(sort_by)
    else:
        # If orders is a list, sort it manually
        reverse = sort_order == 'desc'
        try:
            orders.sort(key=lambda x: getattr(x, sort_by.lstrip('-'), 0), reverse=reverse)
        except (AttributeError, TypeError):
            # If sorting fails, just keep original order
            pass
    
    # Pagination
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    start = (page - 1) * page_size
    end = start + page_size
    
    total_count = len(orders) if isinstance(orders, list) else orders.count()
    orders_page = orders[start:end] if isinstance(orders, list) else orders[start:end]
    
    # Debug logging - also print to response for debugging
    import logging
    logger = logging.getLogger(__name__)
    debug_info = {
        'total_count': total_count,
        'page': page,
        'page_size': page_size,
        'orders_type': 'list' if isinstance(orders, list) else 'queryset',
        'orders_page_type': 'list' if isinstance(orders_page, list) else 'queryset',
        'orders_page_count': len(orders_page) if isinstance(orders_page, list) else (orders_page.count() if hasattr(orders_page, 'count') else 'unknown'),
    }

    # Convert queryset to list if needed for serialization
    if not isinstance(orders_page, list):
        orders_page = list(orders_page)
    
    serializer = CustomOrderListSerializer(orders_page, many=True, context={'request': request})
    
    # Additional debug: check if serializer data is empty
    if len(serializer.data) == 0 and total_count > 0:
        pass
    elif len(serializer.data) == 0 and total_count == 0:

        # Debug: check what happened to the queryset
        initial_count = CustomOrderRequest.objects.all().count()

    # Log activity
    status_filter = request.GET.get('status', '')
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Viewed custom orders list with filters: {status_filter or "all status"}, page: {page}',
        request=request,
        metadata={
            'filters': dict(request.GET),
            'pagination': {
                'page': page,
                'page_size': page_size
            }
        }
    )
    
    # Debug response (remove in production)
    debug_info = None
    if total_count == 0:
        debug_info = {
            'initial_db_count': CustomOrderRequest.objects.all().count(),
            'after_filters_count': orders.count() if not isinstance(orders, list) else len(orders),
            'orders_page_count': len(orders_page) if isinstance(orders_page, list) else (orders_page.count() if hasattr(orders_page, 'count') else 'unknown'),
            'serializer_data_count': len(serializer.data),
        }

    response_data = {
        'message': 'Custom orders retrieved successfully',
        'data': serializer.data,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size if page_size > 0 else 0
        }
    }
    
    # Include debug info in response if in development (remove in production)
    if debug_info:
        response_data['_debug'] = debug_info
    
    return Response(response_data)

@swagger_auto_schema(
    method='get',
    operation_summary="Custom Order Detail",
    operation_description="Get detailed information about a specific custom order (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Custom order details retrieved successfully"),
        404: openapi.Response(description="Custom order not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Custom Order Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def custom_order_detail(request, order_id):
    """
    Get detailed information about a specific custom order.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from CustomRequests.models import CustomOrderRequest
        order = CustomOrderRequest.objects.get(id=order_id)
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom order not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    from CustomRequests.serializers import CustomOrderDetailSerializer
    serializer = CustomOrderDetailSerializer(order)
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='CUSTOM_ORDER_DETAIL_VIEWED',
        ip_address=AdminActivityLog.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        metadata={
            'order_id': order_id
        }
    )
    
    return Response({
        'message': 'Custom order details retrieved successfully',
        'data': serializer.data
    })

@swagger_auto_schema(
    method='post',
    operation_summary="Custom Order Action",
    operation_description="Perform actions on custom orders (start, complete, deliver, cancel, assign) (SuperAdmin and Moderator access).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'action': openapi.Schema(type=openapi.TYPE_STRING, description='Action to perform'),
            'admin_notes': openapi.Schema(type=openapi.TYPE_STRING, description='Admin notes'),
            'delivery_message': openapi.Schema(type=openapi.TYPE_STRING, description='Delivery message'),
            'cancellation_reason': openapi.Schema(type=openapi.TYPE_STRING, description='Cancellation reason'),
            'refund_amount': openapi.Schema(type=openapi.TYPE_NUMBER, description='Refund amount'),
            'assigned_to_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Assigned admin ID')
        }
    ),
    responses={
        200: openapi.Response(description="Order action performed successfully"),
        400: openapi.Response(description="Invalid action or data"),
        404: openapi.Response(description="Custom order not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Custom Order Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def custom_order_action(request, order_id):
    """
    Perform actions on custom orders.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from CustomRequests.models import CustomOrderRequest
        order = CustomOrderRequest.objects.get(id=order_id)
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom order not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    from CustomRequests.serializers import CustomOrderActionSerializer
    serializer = CustomOrderActionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    action = serializer.validated_data['action']
    admin_notes = serializer.validated_data.get('admin_notes', '')
    
    try:
        if action == 'start':
            order.start_order(request.user)
            action_type = 'CUSTOM_ORDER_STARTED'
            
        elif action == 'complete':
            order.complete_order(request.user)
            action_type = 'CUSTOM_ORDER_COMPLETED'
            
        elif action == 'deliver':
            delivery_message = serializer.validated_data.get('delivery_message', '')
            order.deliver_order(request.user, delivery_message)
            action_type = 'CUSTOM_ORDER_DELIVERED'
            
        elif action == 'cancel':
            cancellation_reason = serializer.validated_data.get('cancellation_reason', '')
            cancellation_type = serializer.validated_data.get('cancellation_type', 'admin')
            refund_amount = serializer.validated_data.get('refund_amount')
            refund_reason = serializer.validated_data.get('refund_reason', '')
            order.cancel_order(request.user, cancellation_reason, cancellation_type, refund_amount, refund_reason)
            action_type = 'CUSTOM_ORDER_CANCELLED'
            
        elif action == 'assign':
            assigned_to_id = serializer.validated_data.get('assigned_to_id')
            if assigned_to_id:
                from django.contrib.auth.models import User
                assigned_user = User.objects.get(id=assigned_to_id)
                order.set_assigned_to(assigned_user)
            else:
                order.set_assigned_to(None)
            action_type = 'CUSTOM_ORDER_ASSIGNED'
            
        elif action == 'mark_delayed':
            order.mark_delayed(request.user)
            action_type = 'CUSTOM_ORDER_MARKED_DELAYED'
            
        else:
            return Response({
                'error': 'Invalid action'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Log activity
        action_descriptions = {
            'CUSTOM_ORDER_STARTED': 'Started custom order',
            'CUSTOM_ORDER_COMPLETED': 'Completed custom order',
            'CUSTOM_ORDER_DELIVERED': 'Delivered custom order',
            'CUSTOM_ORDER_CANCELLED': 'Cancelled custom order',
            'CUSTOM_ORDER_ASSIGNED': 'Assigned custom order',
            'CUSTOM_ORDER_MARKED_DELAYED': 'Marked custom order as delayed',
        }
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='user_management',
            description=action_descriptions.get(action_type, f'Performed action on custom order: {action}'),
            request=request,
            metadata={
                'order_id': order_id,
                'action': action,
                'admin_notes': admin_notes
            }
        )
        
        return Response({
            'message': f'Order {action} successfully',
            'data': {
                'order_id': order_id,
                'action': action,
                'new_status': order.status
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'Action failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary="Update Custom Order Status",
    operation_description="Update custom order status (SuperAdmin and Moderator access).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'status': openapi.Schema(type=openapi.TYPE_STRING, description='New status'),
            'admin_notes': openapi.Schema(type=openapi.TYPE_STRING, description='Admin notes')
        }
    ),
    responses={
        200: openapi.Response(description="Custom order status updated successfully"),
        400: openapi.Response(description="Invalid data"),
        404: openapi.Response(description="Custom order not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Custom Order Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_custom_order_status(request, order_id):
    """
    Update custom order status.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from CustomRequests.models import CustomOrderRequest
        order = CustomOrderRequest.objects.get(id=order_id)
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom order not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    from CustomRequests.serializers import CustomOrderRequestStatusUpdateSerializer
    serializer = CustomOrderRequestStatusUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    new_status = serializer.validated_data['status']
    old_status = order.status
    
    # Validate that deliverables are uploaded before allowing status change to 'completed'
    if new_status == 'completed' and old_status != 'completed':
        if not order.delivery_files_uploaded:
            return Response({
                'error': 'Cannot mark order as completed. Please upload deliverables first.',
                'details': 'Deliverables must be uploaded before changing status to completed. Use the "Upload Deliverable" button to upload files.'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update order status
    order.status = new_status
    order.updated_by = request.user
    
    # Update timestamps based on status changes
    if new_status == 'in_progress' and old_status == 'pending' and not order.started_at:
        order.started_at = timezone.now()
    elif new_status == 'completed' and not order.completed_at:
        order.completed_at = timezone.now()
    
    order.save()
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='user_management',
        description=f'Updated custom order status from {old_status} to {new_status}',
        request=request,
        metadata={
            'order_id': order_id,
            'old_status': old_status,
            'new_status': new_status,
        }
    )
    
    return Response({
        'message': 'Custom order status updated successfully',
        'data': {
            'order_id': order_id,
            'old_status': old_status,
            'new_status': new_status
        }
    })

@swagger_auto_schema(
    method='post',
    operation_summary="Upload Delivery Files",
    operation_description="Upload final deliverable files for custom orders (SuperAdmin and Moderator access).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'files': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_FILE)),
            'delivery_message': openapi.Schema(type=openapi.TYPE_STRING, description='Delivery message'),
            'admin_notes': openapi.Schema(type=openapi.TYPE_STRING, description='Admin notes')
        }
    ),
    responses={
        200: openapi.Response(description="Files uploaded successfully"),
        400: openapi.Response(description="Invalid files or order not ready for delivery"),
        404: openapi.Response(description="Custom order not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Custom Order Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def custom_order_upload_files(request, order_id):
    """
    Upload final deliverable files for custom orders.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from CustomRequests.models import CustomOrderRequest
        order = CustomOrderRequest.objects.get(id=order_id)
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom order not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Allow uploading deliverables for orders that are not cancelled
    if order.status == 'cancelled':
        return Response({
            'error': 'Cannot upload deliverables for cancelled orders'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    from CustomRequests.serializers import CustomOrderFileUploadSerializer
    serializer = CustomOrderFileUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    files = serializer.validated_data['files']
    delivery_message = serializer.validated_data.get('delivery_message', '')
    admin_notes = serializer.validated_data.get('admin_notes', '')
    
    try:
        # Upload files to Media model
        # Files should be stored in the customer's folder (order.created_by), not admin's folder
        customer_user = order.created_by
        uploaded_media = []
        
        # Set order context for file path generation
        Media.set_order_context(order.id)
        try:
            for file in files:
                from MediaFiles.models import Media
                # Create Media object with customer as created_by so it goes to customer's folder
                media_obj = Media.objects.create(
                    file=file,
                    media_type='image',  # Default to image, can be enhanced
                    created_by=customer_user  # Use customer user, not admin
                )
                order.attach_media(media_obj, meta={'type': 'delivery_file'}, created_by=request.user)
                uploaded_media.append(media_obj.id)
        finally:
            Media.clear_order_context()
        
        # Mark order as having delivery files
        order.delivery_files_uploaded = True
        order.delivery_message = delivery_message
        order.save()
        
        # Log activity
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='user_management',
            description=f'Uploaded {len(uploaded_media)} delivery files for custom order #{order_id}',
            request=request,
            metadata={
                'order_id': order_id,
                'files_count': len(uploaded_media),
                'delivery_message': delivery_message,
                'admin_notes': admin_notes
            }
        )
        
        return Response({
            'message': f'{len(uploaded_media)} files uploaded successfully',
            'data': {
                'order_id': order_id,
                'uploaded_files': uploaded_media,
                'delivery_files_uploaded': order.delivery_files_uploaded
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'File upload failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_summary="Custom Order Analytics",
    operation_description="Get analytics for custom orders (SuperAdmin access only).",
    manual_parameters=[
        openapi.Parameter(
            'start_date',
            openapi.IN_QUERY,
            description='Start date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'end_date',
            openapi.IN_QUERY,
            description='End date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'group_by',
            openapi.IN_QUERY,
            description='Group by field (status, assigned_to, created_by, hour, day)',
            type=openapi.TYPE_STRING
        )
    ],
    responses={
        200: openapi.Response(description="Analytics retrieved successfully"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['CoreAdmin Custom Order Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def custom_order_analytics(request):
    """
    Get analytics for custom orders.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from CustomRequests.models import CustomOrderRequest
    from CustomRequests.serializers import CustomOrderAnalyticsSerializer
    
    serializer = CustomOrderAnalyticsSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid parameters',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    filters = serializer.validated_data
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    group_by = filters.get('group_by', 'status')
    
    # Allow moderators to access basic stats (when no date filters and group_by=status)
    # SuperAdmin can access full analytics with date filters
    is_basic_stats = not start_date and not end_date and group_by == 'status'
    requires_superadmin = start_date or end_date or group_by != 'status'
    
    if requires_superadmin and admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
        return Response({
            'error': 'SuperAdmin privileges required for advanced analytics'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get orders in date range (paid only - have associated Order)
    orders = CustomOrderRequest.objects.exclude(order__isnull=True)
    if start_date:
        orders = orders.filter(created_at__gte=start_date)
    if end_date:
        orders = orders.filter(created_at__lte=end_date)
    
    # Calculate analytics
    total_orders = orders.count()
    completed_orders = orders.filter(status='completed').count()
    cancelled_orders = orders.filter(status='cancelled').count()
    delayed_orders = orders.filter(status='delayed').count()
    # SLA breach tracking removed - use status='delayed' instead
    sla_breached_orders = orders.filter(status='delayed').count()
    
    # Calculate completion rate
    completion_rate = (completed_orders / total_orders * 100) if total_orders > 0 else 0
    
    # Calculate average completion time
    completed_with_times = orders.filter(
        status='completed',
        started_at__isnull=False,
        completed_at__isnull=False
    )
    avg_completion_time = None
    if completed_with_times.exists():
        total_time = sum(
            (order.completed_at - order.started_at).total_seconds()
            for order in completed_with_times
        )
        avg_completion_time = total_time / completed_with_times.count()
    
    # Group by specified field
    group_data = {}
    if group_by == 'status':
        for status, _ in CustomOrderRequest.STATUS_CHOICES:
            count = orders.filter(status=status).count()
            group_data[status] = count
    elif group_by == 'assigned_to':
        assigned_orders = orders.exclude(assigned_to_id__isnull=True)
        for order in assigned_orders:
            assigned_to = order.assigned_to
            if assigned_to:
                key = f"{assigned_to.username} ({assigned_to.email})"
                group_data[key] = group_data.get(key, 0) + 1
    elif group_by == 'created_by':
        for order in orders:
            created_by = order.created_by
            key = f"{created_by.username} ({created_by.email})"
            group_data[key] = group_data.get(key, 0) + 1
    
    # Log activity
    AdminActivityLog.log_activity(
        user=request.user,
        activity_type='data_export',
        description=f'Viewed custom order analytics grouped by: {group_by}',
        request=request,
        metadata={
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'group_by': group_by
        }
    )
    
    # Calculate status counts for stats tiles
    pending_orders = orders.filter(status='pending').count()
    in_progress_orders = orders.filter(status='in_progress').count()
    
    return Response({
        'message': 'Custom order analytics retrieved successfully',
        'data': {
            'total': total_orders,  # For frontend compatibility
            'total_orders': total_orders,
            'pending': pending_orders,  # For frontend stats tiles
            'in_progress': in_progress_orders,  # For frontend stats tiles
            'completed': completed_orders,  # For frontend stats tiles
            'completed_orders': completed_orders,
            'cancelled_orders': cancelled_orders,
            'delayed_orders': delayed_orders,
            'sla_breached_orders': sla_breached_orders,
            'completion_rate': round(completion_rate, 2),
            'avg_completion_time_seconds': avg_completion_time,
            'group_data': group_data
        }
    })

# ==================== SUBSCRIPTION PLANS MANAGEMENT VIEWS ====================

@swagger_auto_schema(
    method='get',
    operation_summary="Subscription Plans List",
    operation_description="Get list of all subscription plans with filtering and pagination (SuperAdmin and Moderator access).",
    manual_parameters=[
        openapi.Parameter(
            'plan_name',
            openapi.IN_QUERY,
            description='Filter by plan name (basic, prime, premium)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'plan_duration',
            openapi.IN_QUERY,
            description='Filter by plan duration (monthly, annually)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by status (active, inactive)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'min_price',
            openapi.IN_QUERY,
            description='Filter by minimum price',
            type=openapi.TYPE_NUMBER
        ),
        openapi.Parameter(
            'max_price',
            openapi.IN_QUERY,
            description='Filter by maximum price',
            type=openapi.TYPE_NUMBER
        ),
        openapi.Parameter(
            'has_subscriptions',
            openapi.IN_QUERY,
            description='Filter by plans with/without subscriptions',
            type=openapi.TYPE_BOOLEAN
        ),
        openapi.Parameter(
            'search',
            openapi.IN_QUERY,
            description='Search by plan name or description',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by field (created_at, price, plan_name)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'sort_order',
            openapi.IN_QUERY,
            description='Sort order (asc, desc)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'page_size',
            openapi.IN_QUERY,
            description='Number of items per page',
            type=openapi.TYPE_INTEGER
        )
    ],
    responses={
        200: openapi.Response(description="Subscription plans retrieved successfully"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Subscription Plans Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_plans_list(request):
    """
    Get list of all subscription plans with filtering and pagination.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from Plans.models import Plan
    from Plans.serializers import SubscriptionPlanListSerializer, SubscriptionPlanFilterSerializer
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get all plans
        plans = Plan.objects.all()
        
        # Apply filters
        filter_serializer = SubscriptionPlanFilterSerializer(data=request.GET)
        if filter_serializer.is_valid():
            filters = filter_serializer.validated_data
            
            if filters.get('plan_name'):
                plans = plans.filter(plan_name=filters['plan_name'])
            
            if filters.get('plan_duration'):
                plans = plans.filter(plan_duration=filters['plan_duration'])
            
            if filters.get('status'):
                plans = plans.filter(status=filters['status'])
            
            if filters.get('min_price'):
                plans = plans.filter(price__gte=filters['min_price'])
            
            if filters.get('max_price'):
                plans = plans.filter(price__lte=filters['max_price'])
            
            # Only apply has_subscriptions filter if it's explicitly provided in query params
            # Don't apply it if it's just a default False from the serializer
            if 'has_subscriptions' in request.GET:
                has_subscriptions_param = request.GET.get('has_subscriptions')
                # Check if Plan model has subscriptions relationship
                try:
                    # Convert string to boolean
                    has_subscriptions = has_subscriptions_param.lower() in ('true', '1', 'yes')
                    if has_subscriptions:
                        plans = plans.exclude(subscriptions__isnull=True)
                    else:
                        plans = plans.filter(subscriptions__isnull=True)
                except Exception as e:
                    pass

        if request.GET.get('search'):
            search_term = request.GET.get('search')
            plans = plans.filter(
                Q(plan_name__icontains=search_term) | 
                Q(description__icontains=search_term)
            )
        
        # Sorting
        sort_by = request.GET.get('sort_by', 'created_at')
        sort_order = request.GET.get('sort_order', 'desc')
        
        # Validate sort_by field to prevent errors
        valid_sort_fields = ['created_at', 'updated_at', 'plan_name', 'price', 'plan_duration', 'status']
        if sort_by.lstrip('-') not in valid_sort_fields:
            sort_by = 'created_at'
        
        if sort_order == 'desc':
            sort_by = f'-{sort_by}'
        
        plans = plans.order_by(sort_by)
        
        # Pagination
        try:
            page = int(request.GET.get('page', 1))
        except (ValueError, TypeError):
            page = 1
        
        try:
            page_size = int(request.GET.get('page_size', 20))
        except (ValueError, TypeError):
            page_size = 20
        
        start = (page - 1) * page_size
        end = start + page_size
        
        total_count = plans.count()
        plans_page = plans[start:end]
        
        serializer = SubscriptionPlanListSerializer(plans_page, many=True)
        
        # Log activity (wrap in try-except to prevent logging errors from breaking the response)
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='other',  # Use 'other' since custom types exceed 20 char limit
                description=f'Viewed subscription plans list (page {page})',
                request=request,
                metadata={
                    'activity': 'SUBSCRIPTION_PLANS_LIST_VIEWED',
                    'filters': dict(request.GET),
                    'pagination': {
                        'page': page,
                        'page_size': page_size
                    }
                }
            )
        except Exception as log_error:
            pass

        return Response({
            'message': 'Subscription plans retrieved successfully',
            'data': serializer.data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size if page_size > 0 else 0
            }
        })
    except Exception as e:

        return Response({
            'error': f'Failed to retrieve subscription plans: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary="Subscription Plan Detail",
    operation_description="Get detailed information about a specific subscription plan (SuperAdmin and Moderator access).",
    responses={
        200: openapi.Response(description="Subscription plan details retrieved successfully"),
        404: openapi.Response(description="Subscription plan not found"),
        403: openapi.Response(description="Access denied - admin privileges required")
    },
    tags=['CoreAdmin Subscription Plans Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_plan_detail(request, plan_id):
    """
    Get detailed information about a specific subscription plan.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from Plans.models import Plan
        plan = Plan.objects.get(id=plan_id)
    except Plan.DoesNotExist:
        return Response({
            'error': 'Subscription plan not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    from Plans.serializers import SubscriptionPlanDetailSerializer
    serializer = SubscriptionPlanDetailSerializer(plan)
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='other',  # Use 'other' since custom types exceed 20 char limit
            description=f'Viewed subscription plan detail: {plan.plan_name}',
            request=request,
            metadata={
                'activity': 'SUBSCRIPTION_PLAN_DETAIL_VIEWED',
                'plan_id': plan_id
            }
        )
    except Exception as log_error:
        import logging
        logger = logging.getLogger(__name__)

    return Response({
        'message': 'Subscription plan details retrieved successfully',
        'data': serializer.data
    })

@swagger_auto_schema(
    method='post',
    operation_summary="Create Subscription Plan",
    operation_description="Create a new subscription plan (SuperAdmin access only).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'plan_name': openapi.Schema(type=openapi.TYPE_STRING, description='Plan name'),
            'description': openapi.Schema(type=openapi.TYPE_OBJECT, description='Plan description'),
            'price': openapi.Schema(type=openapi.TYPE_NUMBER, description='Plan price'),
            'plan_duration': openapi.Schema(type=openapi.TYPE_STRING, description='Plan duration'),
            'created_by_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Created by user ID')
        }
    ),
    responses={
        201: openapi.Response(description="Subscription plan created successfully"),
        400: openapi.Response(description="Invalid data"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['CoreAdmin Subscription Plans Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_subscription_plan(request):
    """
    Create a new subscription plan.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from Plans.serializers import SubscriptionPlanCreateSerializer
    from Plans.models import Plan
    from django.db import IntegrityError
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Check if an inactive plan with same name and duration exists BEFORE validation
    # This allows us to update it instead of creating a new one
    plan_name = request.data.get('plan_name')
    plan_duration = request.data.get('plan_duration')
    existing_inactive_plan = None
    
    if plan_name and plan_duration:
        existing_inactive_plan = Plan.objects.filter(
            plan_name=plan_name,
            plan_duration=plan_duration,
            status='inactive'
        ).first()
    
    # If inactive plan exists, we'll update it (skip unique validation in serializer)
    # Otherwise, validate normally
    serializer = SubscriptionPlanCreateSerializer(data=request.data)
    if not serializer.is_valid():

        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        if existing_inactive_plan:
            # Update and reactivate the existing inactive plan
            # This ensures only one active plan exists with same name and duration

            # Update all fields from the serializer
            for key, value in serializer.validated_data.items():
                if key != 'created_by_id':  # Don't update created_by
                    setattr(existing_inactive_plan, key, value)
            
            # Handle is_most_popular logic before saving
            is_most_popular = serializer.validated_data.get('is_most_popular', False)
            if is_most_popular:
                # Unmark other plans of the same duration
                Plan.objects.filter(
                    plan_duration=existing_inactive_plan.plan_duration,
                    is_most_popular=True
                ).exclude(id=existing_inactive_plan.id).update(is_most_popular=False)
            
            # Reactivate the plan
            existing_inactive_plan.status = 'active'
            existing_inactive_plan.updated_by = request.user
            existing_inactive_plan.save()
            plan = existing_inactive_plan

        else:
            # Create new plan (no existing plan with same name and duration)
            try:
                plan = serializer.save(created_by=request.user)

            except IntegrityError as e:
                # Handle case where unique constraint is violated (shouldn't happen due to validation, but just in case)

                return Response({
                    'error': 'A plan with this name and duration already exists',
                    'details': {'non_field_errors': ['A plan with this name and duration combination already exists.']}
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Determine if plan was reactivated or newly created
        was_reactivated = existing_inactive_plan is not None and existing_inactive_plan.id == plan.id
        
        # Log activity
        try:
            activity_description = (
                f'Reactivated and updated subscription plan: {plan.plan_name}'
                if was_reactivated
                else f'Created subscription plan: {plan.plan_name}'
            )
            
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='other',  # Use 'other' since custom types exceed 20 char limit
                description=activity_description,
                request=request,
                metadata={
                    'activity': 'SUBSCRIPTION_PLAN_REACTIVATED' if was_reactivated else 'SUBSCRIPTION_PLAN_CREATED',
                    'plan_id': plan.id,
                    'plan_name': plan.plan_name,
                    'plan_duration': plan.plan_duration,
                    'price': float(plan.price),
                    'was_reactivated': was_reactivated
                }
            )
        except Exception as log_error:
            pass

        # Return appropriate message based on whether plan was created or reactivated
        return Response({
            'message': (
                'Subscription plan reactivated and updated successfully'
                if was_reactivated
                else 'Subscription plan created successfully'
            ),
            'data': {
                'plan_id': plan.id,
                'plan_name': plan.plan_name,
                'plan_duration': plan.plan_duration,
                'price': float(plan.price),
                'status': plan.status,
                'was_reactivated': was_reactivated
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'error': f'Plan creation failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='put',
    operation_summary="Update Subscription Plan",
    operation_description="Update an existing subscription plan (SuperAdmin access only).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'description': openapi.Schema(type=openapi.TYPE_OBJECT, description='Plan description'),
            'price': openapi.Schema(type=openapi.TYPE_NUMBER, description='Plan price'),
            'status': openapi.Schema(type=openapi.TYPE_STRING, description='Plan status'),
            'updated_by_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Updated by user ID')
        }
    ),
    responses={
        200: openapi.Response(description="Subscription plan updated successfully"),
        400: openapi.Response(description="Invalid data"),
        404: openapi.Response(description="Subscription plan not found"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['CoreAdmin Subscription Plans Management']
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_subscription_plan(request, plan_id):
    """
    Update an existing subscription plan.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from Plans.models import Plan
        plan = Plan.objects.get(id=plan_id)
    except Plan.DoesNotExist:
        return Response({
            'error': 'Subscription plan not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    from Plans.serializers import SubscriptionPlanUpdateSerializer
    serializer = SubscriptionPlanUpdateSerializer(plan, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        old_status = plan.status
        old_price = plan.price
        
        # Handle is_most_popular logic before saving
        is_most_popular = serializer.validated_data.get('is_most_popular')
        if is_most_popular is True:
            # Unmark other plans of the same duration
            Plan.objects.filter(
                plan_duration=plan.plan_duration,
                is_most_popular=True
            ).exclude(id=plan.id).update(is_most_popular=False)
        
        plan = serializer.save(updated_by=request.user)
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='other',  # Use 'other' since custom types exceed 20 char limit
                description=f'Updated subscription plan: {plan.plan_name}',
                request=request,
                metadata={
                    'activity': 'SUBSCRIPTION_PLAN_UPDATED',
                'plan_id': plan_id,
                'old_status': old_status,
                'new_status': plan.status,
                'old_price': float(old_price),
                'new_price': float(plan.price)
            }
        )
        except Exception as log_error:
            import logging
            logger = logging.getLogger(__name__)

        return Response({
            'message': 'Subscription plan updated successfully',
            'data': {
                'plan_id': plan.id,
                'plan_name': plan.plan_name,
                'plan_duration': plan.plan_duration,
                'price': float(plan.price),
                'status': plan.status
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'Plan update failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary="Delete Subscription Plan",
    operation_description="Delete a subscription plan from the database (SuperAdmin access only). This will also delete all related subscriptions due to CASCADE.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'deactivation_reason': openapi.Schema(type=openapi.TYPE_STRING, description='Deletion reason'),
            'notify_customers': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Notify customers'),
            'admin_notes': openapi.Schema(type=openapi.TYPE_STRING, description='Admin notes')
        }
    ),
    responses={
        200: openapi.Response(description="Subscription plan deleted successfully"),
        400: openapi.Response(description="Invalid data"),
        404: openapi.Response(description="Subscription plan not found"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['CoreAdmin Subscription Plans Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deactivate_subscription_plan(request, plan_id):
    """
    Delete a subscription plan from the database.
    This will also delete all related subscriptions due to CASCADE.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from Plans.models import Plan
        plan = Plan.objects.get(id=plan_id)
    except Plan.DoesNotExist:
        return Response({
            'error': 'Subscription plan not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    from Plans.serializers import SubscriptionPlanDeactivateSerializer
    import logging
    logger = logging.getLogger(__name__)
    
    # Handle empty request body - allow deletion without any data
    request_data = request.data if request.data else {}
    serializer = SubscriptionPlanDeactivateSerializer(data=request_data)
    if not serializer.is_valid():

        return Response({
            'error': 'Invalid data',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    deletion_reason = serializer.validated_data.get('deactivation_reason', '')
    notify_customers = serializer.validated_data.get('notify_customers', True)
    admin_notes = serializer.validated_data.get('admin_notes', '')
    
    try:
        # Check for active subscriptions - warn but allow deletion
        active_subscriptions_count = plan.subscriptions.filter(status='active').count()
        total_subscriptions_count = plan.subscriptions.count()
        
        # Store plan info before deletion for logging
        plan_name = plan.plan_name
        plan_duration = plan.plan_duration
        plan_price = float(plan.price)
        
        # TODO: Implement customer notification if requested
        if notify_customers and active_subscriptions_count > 0:
            # Send notifications to customers with active subscriptions
            active_subscriptions = plan.subscriptions.filter(status='active')
            # notification_service.notify_plan_deletion(plan, active_subscriptions)

        # Log activity before deletion
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='other',  # Use 'other' since custom types exceed 20 char limit
                description=f'Deleted subscription plan: {plan_name}',
                request=request,
                metadata={
                    'activity': 'SUBSCRIPTION_PLAN_DELETED',
                    'plan_id': plan_id,
                    'plan_name': plan_name,
                    'plan_duration': plan_duration,
                    'price': plan_price,
                    'deletion_reason': deletion_reason,
                    'notify_customers': notify_customers,
                    'admin_notes': admin_notes,
                    'active_subscriptions_count': active_subscriptions_count,
                    'total_subscriptions_count': total_subscriptions_count
                }
            )
        except Exception as log_error:
            pass

        # Delete the plan (this will CASCADE delete all related subscriptions)
        plan.delete()

        return Response({
            'message': 'Subscription plan deleted successfully',
            'data': {
                'plan_id': plan_id,
                'plan_name': plan_name,
                'plan_duration': plan_duration,
                'deleted_subscriptions_count': total_subscriptions_count
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:

        return Response({
            'error': f'Plan deletion failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_summary="Subscription Plans Analytics",
    operation_description="Get analytics for subscription plans (SuperAdmin access only).",
    manual_parameters=[
        openapi.Parameter(
            'start_date',
            openapi.IN_QUERY,
            description='Start date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'end_date',
            openapi.IN_QUERY,
            description='End date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'group_by',
            openapi.IN_QUERY,
            description='Group by field (plan_name, plan_duration, status, month, year)',
            type=openapi.TYPE_STRING
        )
    ],
    responses={
        200: openapi.Response(description="Analytics retrieved successfully"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['CoreAdmin Subscription Plans Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_plans_analytics(request):
    """
    Get analytics for subscription plans.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    from Plans.models import Plan, Subscription
    from Plans.serializers import SubscriptionPlanAnalyticsSerializer
    
    serializer = SubscriptionPlanAnalyticsSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid parameters',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    filters = serializer.validated_data
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    group_by = filters.get('group_by', 'plan_name')
    
    # Get plans in date range
    plans = Plan.objects.all()
    if start_date:
        plans = plans.filter(created_at__gte=start_date)
    if end_date:
        plans = plans.filter(created_at__lte=end_date)
    
    # Calculate analytics
    total_plans = plans.count()
    active_plans = plans.filter(status='active').count()
    inactive_plans = plans.filter(status='inactive').count()
    
    # Calculate subscription statistics
    total_subscriptions = Subscription.objects.count()
    active_subscriptions = Subscription.objects.filter(status='active').count()
    
    # Calculate revenue
    total_revenue = sum(plan.price for plan in plans.filter(status='active'))
    
    # Calculate average plan price
    avg_plan_price = plans.aggregate(avg_price=models.Avg('price'))['avg_price'] or 0
    
    # Find most popular plan
    most_popular_plan = None
    if plans.exists():
        plan_subscription_counts = {}
        for plan in plans:
            count = plan.subscriptions.count()
            plan_subscription_counts[plan.id] = {
                'plan_name': plan.plan_name,
                'plan_duration': plan.plan_duration,
                'subscription_count': count
            }
        
        if plan_subscription_counts:
            most_popular_plan = max(plan_subscription_counts.items(), key=lambda x: x[1]['subscription_count'])
            most_popular_plan = {
                'plan_id': most_popular_plan[0],
                **most_popular_plan[1]
            }
    
    # Calculate revenue by plan
    revenue_by_plan = {}
    for plan in plans.filter(status='active'):
        active_subs = plan.subscriptions.filter(status='active').count()
        revenue_by_plan[plan.plan_name] = float(plan.price * active_subs)
    
    # Group by specified field
    group_data = {}
    if group_by == 'plan_name':
        for plan_name, _ in Plan.PLAN_NAME_CHOICES:
            count = plans.filter(plan_name=plan_name).count()
            group_data[plan_name] = count
    elif group_by == 'plan_duration':
        for duration, _ in Plan.DURATION_CHOICES:
            count = plans.filter(plan_duration=duration).count()
            group_data[duration] = count
    elif group_by == 'status':
        for status, _ in Plan.STATUS_CHOICES:
            count = plans.filter(status=status).count()
            group_data[status] = count
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='other',  # Use 'other' since custom types exceed 20 char limit
            description='Viewed subscription plans analytics',
            request=request,
            metadata={
                'activity': 'SUBSCRIPTION_PLANS_ANALYTICS_VIEWED',
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'group_by': group_by
            }
        )
    except Exception as log_error:
        import logging
        logger = logging.getLogger(__name__)

    return Response({
        'message': 'Subscription plans analytics retrieved successfully',
        'data': {
            'total_plans': total_plans,
            'active_plans': active_plans,
            'inactive_plans': inactive_plans,
            'total_subscriptions': total_subscriptions,
            'active_subscriptions': active_subscriptions,
            'total_revenue': float(total_revenue),
            'average_plan_price': float(avg_plan_price),
            'most_popular_plan': most_popular_plan,
            'revenue_by_plan': revenue_by_plan,
            'group_data': group_data
        }
    })

# ==================== BUSINESS CONFIG ENDPOINTS ====================

@swagger_auto_schema(
    method='get',
    operation_summary='Get Business Configuration',
    operation_description='Get current business configuration values (commission rate, GST percentage, custom order price, custom order time slot, minimum required designs). These values are read from SystemConfig (set in AdminWebApp), with fallback to environment variables.',
    responses={
        200: openapi.Response(
            description='Business configuration retrieved successfully',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'commission_rate': openapi.Schema(type=openapi.TYPE_NUMBER, description='Platform commission rate (%)'),
                    'gst_percentage': openapi.Schema(type=openapi.TYPE_NUMBER, description='GST percentage (%)'),
                    'custom_order_price': openapi.Schema(type=openapi.TYPE_NUMBER, description='Default price for custom orders (INR)'),
                    'custom_order_time_slot_hours': openapi.Schema(type=openapi.TYPE_INTEGER, description='Custom order time slot (hours)'),
                    'minimum_required_designs_onboard': openapi.Schema(type=openapi.TYPE_INTEGER, description='Minimum required designs for onboarding'),
                }
            )
        ),
    },
    tags=['CoreAdmin Business Configuration']
)
@api_view(['GET'])
@permission_classes([AllowAny])  # Allow public access for frontend apps
def business_config(request):
    """
    Get business configuration values.
    These values are read from SystemConfig model (set in AdminWebApp > System Config > Global Configuration),
    with fallback to environment variables if SystemConfig is not available.
    """
    from common.business_config import BusinessConfig
    
    return Response({
        'message': 'Business configuration retrieved successfully',
        'data': {
            'commission_rate': BusinessConfig.get_commission_rate(),
            'gst_percentage': BusinessConfig.get_gst_percentage(),
            'custom_order_price': float(BusinessConfig.get_custom_order_price()),
            'custom_order_time_slot_hours': BusinessConfig.get_custom_order_time_slot_hours(),
            'minimum_required_designs_onboard': BusinessConfig.get_minimum_required_designs_onboard(),
        }
    }, status=status.HTTP_200_OK)

@swagger_auto_schema(
    method='get',
    operation_summary='Get Landing Page Data',
    operation_description='Get landing page statistics and client names (public endpoint)',
    tags=['CoreAdmin System Configuration']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def get_landing_page_data(request):
    """Get landing page statistics and client names (public)"""
    try:
        from CoreAdmin.models import SystemConfig
        from django.core.cache import cache
        
        cache_key = 'landing_page_data'
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)
        
        config = SystemConfig.get_config()
        stats = config.landing_page_stats or {}
        client_names = config.client_names or []
        
        response_data = {
            'stats': {
                'totalClients': stats.get('totalClients', 0),
                'totalDesigners': stats.get('totalDesigners', 0),
                'totalDesignAssets': stats.get('totalDesignAssets', 0),
            },
            'clientNames': client_names,
        }
        
        # Cache for 1 hour
        cache.set(cache_key, response_data, 3600)
        return Response(response_data)
    except Exception as e:
        # Return default values on error
        return Response({
            'stats': {
                'totalClients': 0,
                'totalDesigners': 0,
                'totalDesignAssets': 0,
            },
            'clientNames': [],
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary='Get System Config',
    operation_description='Get system configuration including landing page settings',
    tags=['CoreAdmin System Configuration']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_system_config(request):
    """Get system configuration"""
    try:
        from CoreAdmin.models import SystemConfig
        config = SystemConfig.get_config()
        from common.business_config import BusinessConfig
        paid_pdf_opts = getattr(config, 'paid_pdf_designs_options', None)
        if not paid_pdf_opts:
            paid_pdf_opts = BusinessConfig.get_paid_pdf_designs_options()
        return Response({
            'commission_rate': config.commission_rate,
            'gst_percentage': config.gst_percentage,
            'design_price': float(config.design_price) if config.design_price else 50.00,
            'custom_order_price': float(config.custom_order_price) if config.custom_order_price is not None else 0.00,
            'custom_order_time_slot_hours': config.custom_order_time_slot_hours,
            'minimum_required_designs': config.minimum_required_designs,
            'free_mock_pdf_downloads_no_plan_per_month': getattr(config, 'free_mock_pdf_downloads_no_plan_per_month', 999),
            'paid_pdf_designs_options': paid_pdf_opts if paid_pdf_opts else [],
            'maintenance_mode': config.maintenance_mode,
            'hero_section_designs': config.hero_section_designs or [],
            'featured_designs': config.featured_designs or [],
            'dome_gallery_designs': config.dome_gallery_designs or [],
            'landing_page_stats': config.landing_page_stats or {},
            'client_names': config.client_names or [],
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='put',
    operation_summary='Update System Config',
    operation_description='Update system configuration',
    tags=['CoreAdmin System Configuration']
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_system_config(request):
    """Update system configuration"""
    try:
        from CoreAdmin.models import SystemConfig
        from django.core.cache import cache
        
        config = SystemConfig.get_config()
        
        # Update fields
        if 'commission_rate' in request.data:
            config.commission_rate = float(request.data['commission_rate'])
        if 'gst_percentage' in request.data:
            config.gst_percentage = float(request.data['gst_percentage'])
        if 'design_price' in request.data:
            from decimal import Decimal
            config.design_price = Decimal(str(request.data['design_price']))
        if 'custom_order_price' in request.data:
            from decimal import Decimal
            config.custom_order_price = Decimal(str(request.data['custom_order_price']))
        if 'custom_order_time_slot_hours' in request.data:
            config.custom_order_time_slot_hours = int(request.data['custom_order_time_slot_hours'])
        if 'minimum_required_designs' in request.data:
            config.minimum_required_designs = int(request.data['minimum_required_designs'])
        if 'free_mock_pdf_downloads_no_plan_per_month' in request.data:
            config.free_mock_pdf_downloads_no_plan_per_month = int(request.data['free_mock_pdf_downloads_no_plan_per_month'])
        if 'paid_pdf_designs_options' in request.data:
            opts = request.data['paid_pdf_designs_options']
            if isinstance(opts, list):
                # Only allow 20, 50, 100 - filter out values > 100
                filtered = [int(x) for x in opts if str(x).strip() and int(x) <= 100]
                config.paid_pdf_designs_options = filtered if filtered else [20, 50, 100]
            else:
                config.paid_pdf_designs_options = []
        if 'maintenance_mode' in request.data:
            config.maintenance_mode = bool(request.data['maintenance_mode'])
        if 'hero_section_designs' in request.data:
            # Convert string IDs to integers for consistency
            hero_ids = request.data['hero_section_designs']
            if isinstance(hero_ids, list):
                config.hero_section_designs = [int(pid) if isinstance(pid, str) else pid for pid in hero_ids if pid]
            else:
                config.hero_section_designs = hero_ids
        if 'featured_designs' in request.data:
            featured_ids = request.data['featured_designs']
            if isinstance(featured_ids, list):
                config.featured_designs = [int(pid) if isinstance(pid, str) else pid for pid in featured_ids if pid]
            else:
                config.featured_designs = featured_ids
        if 'dome_gallery_designs' in request.data:
            dome_ids = request.data['dome_gallery_designs']
            if isinstance(dome_ids, list):
                config.dome_gallery_designs = [int(pid) if isinstance(pid, str) else pid for pid in dome_ids if pid]
            else:
                config.dome_gallery_designs = dome_ids
        if 'landing_page_stats' in request.data:
            config.landing_page_stats = request.data['landing_page_stats']
        if 'client_names' in request.data:
            config.client_names = request.data['client_names']
        
        # Clear cache BEFORE saving (using old timestamp)
        old_timestamp = config.updated_at.timestamp() if hasattr(config, 'updated_at') and config.updated_at else None
        
        config.save()
        
        # Clear cache - invalidate all related cache keys
        try:
            from django.core.cache import cache
            # Clear cache keys with old timestamp
            if old_timestamp:
                cache.delete(f'hero_section_designs_{old_timestamp}')
                cache.delete(f'dome_gallery_images_{old_timestamp}')
            # Also try to clear with new timestamp (in case cache was created after save)
            new_timestamp = config.updated_at.timestamp()
            cache.delete(f'hero_section_designs_{new_timestamp}')
            cache.delete(f'dome_gallery_images_{new_timestamp}')
            # Clear landing page data cache
            cache.delete('landing_page_data_cache')
            cache.delete('landing_page_data')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)

            pass
        
        return Response({
            'message': 'System configuration updated successfully',
            'commission_rate': config.commission_rate,
            'gst_percentage': config.gst_percentage,
            'design_price': float(config.design_price) if config.design_price else 50.00,
            'custom_order_price': float(config.custom_order_price) if config.custom_order_price is not None else 0.00,
            'custom_order_time_slot_hours': config.custom_order_time_slot_hours,
            'minimum_required_designs': config.minimum_required_designs,
            'free_mock_pdf_downloads_no_plan_per_month': getattr(config, 'free_mock_pdf_downloads_no_plan_per_month', 999),
            'maintenance_mode': config.maintenance_mode,
            'hero_section_designs': config.hero_section_designs,
            'featured_designs': config.featured_designs,
            'dome_gallery_designs': config.dome_gallery_designs,
            'landing_page_stats': config.landing_page_stats,
            'client_names': config.client_names,
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    operation_summary='Create Notification',
    operation_description='Create and send notifications to all designers and/or customers. Supports immediate and scheduled delivery.',
    request_body=AdminNotificationCreateSerializer,
    responses={
        201: openapi.Response(
            description='Notification created successfully',
            examples={
                'application/json': {
                    'success': True,
                    'message': 'Notification sent to 150 recipients',
                    'notification_ids': [1, 2, 3]
                }
            }
        ),
        400: openapi.Response(description='Bad request - validation error'),
        500: openapi.Response(description='Internal server error')
    },
    tags=['Notifications']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_notification(request):
    """
    Create notification and send to selected recipients (all designers/customers).
    Supports immediate and scheduled delivery.
    """
    serializer = AdminNotificationCreateSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'success': False,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    recipients = data.get('recipients', {})
    send_to_designers = recipients.get('designers', False)
    send_to_customers = recipients.get('customers', False)
    
    if not send_to_designers and not send_to_customers:
        return Response({
            'success': False,
            'error': 'Please select at least one recipient type'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    send_type = data.get('sendType', 'immediate')
    scheduled_at = data.get('scheduledAt')
    priority = data.get('priority', 'medium')
    delivery_method = data.get('deliveryMethod', 'both')  # 'in_app', 'email', or 'both'
    
    # Log delivery method for debugging
    import logging
    logger = logging.getLogger(__name__)

    if send_type == 'scheduled':
        if not scheduled_at:
            return Response({
                'success': False,
                'error': 'Scheduled date and time is required for scheduled notifications'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate scheduled time is in future
        if scheduled_at <= timezone.now():
            return Response({
                'success': False,
                'error': 'Scheduled time must be in the future'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create campaign record
        campaign = AdminNotificationCampaign.objects.create(
            admin_id=request.user.id,
            title=data['title'],
            message=data['message'],
            priority=priority,
            send_to_designers=send_to_designers,
            send_to_customers=send_to_customers,
            delivery_method=delivery_method,
            status='scheduled',
            scheduled_at=scheduled_at
        )
        campaign.set_admin(request.user)
        
        # Schedule notification using Celery
        from common.tasks import send_scheduled_notification
        task = send_scheduled_notification.apply_async(
            args=[campaign.id, data['title'], data['message'], priority, send_to_designers, send_to_customers],
            kwargs={'delivery_method': delivery_method},
            eta=scheduled_at
        )
        
        # Store task ID in campaign
        campaign.celery_task_id = task.id
        campaign.save()
        
        return Response({
            'success': True,
            'message': 'Notification scheduled successfully',
            'scheduled_at': scheduled_at.isoformat(),
            'campaign_id': campaign.id
        }, status=status.HTTP_201_CREATED)
    
    else:
        # Send immediately
        # IMPORTANT: In-app notifications are ALWAYS created regardless of delivery_method
        # delivery_method only controls whether emails are sent:
        # - 'in_app': Create notifications only (no email) - notifications will appear in dashboards
        # - 'email': Create notifications + send email - notifications appear in dashboards AND emails sent
        # - 'both': Create notifications + send email (same as 'email')
        try:
            import logging
            logger = logging.getLogger(__name__)
            notification_ids = []
            designers_count = 0
            customers_count = 0
            
            # Create campaign record
            campaign = AdminNotificationCampaign.objects.create(
                admin_id=request.user.id,
                title=data['title'],
                message=data['message'],
                priority=priority,
                send_to_designers=send_to_designers,
                send_to_customers=send_to_customers,
                delivery_method=delivery_method,
                status='sent',
                sent_at=timezone.now()
            )
            campaign.set_admin(request.user)
            
            with transaction.atomic():
                # Send to all designers
                if send_to_designers:
                    # Get verified designers who have completed onboarding
                    designers = User.objects.filter(
                        created_designer_profiles__status='verified',
                        created_designer_profiles__onboarding_completed=True,
                        is_active=True
                    ).distinct()
                    
                    for designer in designers:
                        notification = DesignerNotification.objects.create(
                            designer_id=designer.id,
                            notification_type='system_update',
                            title=data['title'],
                            message=data['message'],
                            priority=priority
                        )
                        notification.set_designer(designer)
                        notification_ids.append(notification.id)
                        designers_count += 1
                        
                        # Send email only if deliveryMethod is 'email' or 'both'
                        if delivery_method in ['email', 'both']:
                            from common.tasks import send_notification_email
                            send_notification_email.delay(
                                'designer',
                                designer.id,
                                notification.id
                            )
                
                # Send to all customers
                if send_to_customers:
                    # Get ALL active users as customers (including verified designers)
                    # Users who are both designers and customers will receive notifications in both dashboards
                    customers = User.objects.filter(
                        is_active=True
                    ).distinct()
                    
                    for customer in customers:
                        notification = CustomerNotification.objects.create(
                            customer_id=customer.id,
                            notification_type='system_update',
                            title=data['title'],
                            message=data['message'],
                            priority=priority
                        )
                        notification.set_customer(customer)
                        notification_ids.append(notification.id)
                        customers_count += 1
                        
                        # Send email only if deliveryMethod is 'email' or 'both'
                        if delivery_method in ['email', 'both']:
                            from common.tasks import send_notification_email
                            send_notification_email.delay(
                                'customer',
                                customer.id,
                                notification.id
                            )
            
            # Update campaign with statistics
            campaign.mark_as_sent(
                total_recipients=len(notification_ids),
                designers_count=designers_count,
                customers_count=customers_count
            )

            return Response({
                'success': True,
                'message': f'Notification sent to {len(notification_ids)} recipients',
                'notification_ids': notification_ids,
                'delivery_method': delivery_method,
                'in_app_notifications_created': len(notification_ids),
                'emails_sent': delivery_method in ['email', 'both'],
                'campaign_id': campaign.id,
                'data': {
                    'id': notification_ids[0] if notification_ids else None,
                    'title': data['title'],
                    'message': data['message'],
                    'priority': priority,
                    'createdAt': timezone.now().isoformat()
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)

            return Response({
                'success': False,
                'error': f'Failed to create notification: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary='List Admin Notification Campaigns',
    operation_description='Get list of all notification campaigns created by admins (both sent and scheduled)',
    responses={
        200: openapi.Response(
            description='Campaigns retrieved successfully',
            examples={
                'application/json': {
                    'success': True,
                    'data': {
                        'campaigns': [
                            {
                                'id': 1,
                                'title': 'System Maintenance',
                                'message': 'Scheduled maintenance...',
                                'priority': 'high',
                                'status': 'sent',
                                'send_to_designers': True,
                                'send_to_customers': True,
                                'delivery_method': 'both',
                                'scheduled_at': None,
                                'sent_at': '2024-01-01T12:00:00Z',
                                'total_recipients': 150,
                                'designers_count': 50,
                                'customers_count': 100,
                                'created_at': '2024-01-01T10:00:00Z'
                            }
                        ]
                    }
                }
            }
        ),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Notifications']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_notification_campaigns(request):
    """
    Get list of all notification campaigns created by admins.
    Shows both sent and scheduled notifications.
    """
    try:
        campaigns = AdminNotificationCampaign.objects.all().order_by('-created_at')
        
        # Get admin info for each campaign
        campaigns_data = []
        for campaign in campaigns:
            admin = campaign.admin
            campaigns_data.append({
                'id': campaign.id,
                'title': campaign.title,
                'message': campaign.message,
                'priority': campaign.priority,
                'status': campaign.status,
                'send_to_designers': campaign.send_to_designers,
                'send_to_customers': campaign.send_to_customers,
                'delivery_method': campaign.delivery_method,
                'scheduled_at': campaign.scheduled_at.isoformat() if campaign.scheduled_at else None,
                'sent_at': campaign.sent_at.isoformat() if campaign.sent_at else None,
                'total_recipients': campaign.total_recipients,
                'designers_count': campaign.designers_count,
                'customers_count': campaign.customers_count,
                'created_at': campaign.created_at.isoformat(),
                'created_by': {
                    'id': admin.id if admin else None,
                    'email': admin.email if admin else None,
                    'name': f"{admin.first_name} {admin.last_name}".strip() if admin else 'Unknown'
                } if admin else None
            })
        
        return Response({
            'success': True,
            'data': {
                'campaigns': campaigns_data
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'success': False,
            'error': f'Failed to list notification campaigns: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ============================================================================
# Admin User Management Endpoints (Super Admin Only)
# ============================================================================

@swagger_auto_schema(
    method='get',
    operation_summary="List all admin users",
    operation_description="Get list of all admin users with filtering and pagination (SuperAdmin access only).",
    manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, description='Page number', type=openapi.TYPE_INTEGER),
        openapi.Parameter('limit', openapi.IN_QUERY, description='Items per page', type=openapi.TYPE_INTEGER),
        openapi.Parameter('role', openapi.IN_QUERY, description='Filter by role (superadmin, moderator)', type=openapi.TYPE_STRING),
        openapi.Parameter('status', openapi.IN_QUERY, description='Filter by status (active, inactive)', type=openapi.TYPE_STRING),
        openapi.Parameter('search', openapi.IN_QUERY, description='Search by name or email', type=openapi.TYPE_STRING),
    ],
    responses={
        200: openapi.Response(description='List of admin users'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Admin User Management']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_users_list(request):
    """
    Get list of all admin users with filtering and pagination.
    Super Admin only.
    """
    try:
        # Check if user is Super Admin
        admin_profile = request.user.admin_profile
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied. Only Super Admins can manage admin users.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get query parameters
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
        role_filter = request.GET.get('role', None)
        status_filter = request.GET.get('status', None)
        search_query = request.GET.get('search', None)
        
        # Start with all admin profiles
        queryset = AdminUserProfile.objects.select_related('user').all()
        
        # Apply filters
        if role_filter:
            queryset = queryset.filter(admin_group=role_filter)
        
        if status_filter:
            if status_filter == 'active':
                queryset = queryset.filter(is_active=True, user__is_active=True)
            elif status_filter == 'inactive':
                queryset = queryset.filter(Q(is_active=False) | Q(user__is_active=False))
        
        if search_query:
            queryset = queryset.filter(
                Q(user__email__icontains=search_query) |
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query)
            )
        
        # Order by created_at descending
        queryset = queryset.order_by('-created_at')
        
        # Pagination
        total = queryset.count()
        start = (page - 1) * limit
        end = start + limit
        admin_users = queryset[start:end]
        
        # Serialize data
        serializer = AdminUserListSerializer(admin_users, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'total_pages': (total + limit - 1) // limit
            }
        }, status=status.HTTP_200_OK)
        
    except AdminUserProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Admin profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'success': False,
            'error': f'Failed to list admin users: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    operation_summary="Create new admin user",
    operation_description="Create a new admin user (SuperAdmin access only).",
    request_body=AdminUserCreateSerializer,
    responses={
        201: openapi.Response(description='Admin user created successfully'),
        400: openapi.Response(description='Bad request - validation error'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Admin User Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_user_create(request):
    """
    Create a new admin user.
    Super Admin only.
    """
    try:
        # Check if user is Super Admin
        admin_profile = request.user.admin_profile
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied. Only Super Admins can create admin users.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = AdminUserCreateSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                user = serializer.save()
                
                # Log activity
                AdminActivityLog.log_activity(
                    user=request.user,
                    activity_type='user_management',
                    description=f'Created admin user: {user.email}',
                    request=request,
                    metadata={
                        'created_user_id': user.id,
                        'created_user_email': user.email,
                        'admin_group': user.admin_profile.admin_group
                    }
                )
                
                return Response({
                    'success': True,
                    'message': 'Admin user created successfully',
                    'data': {
                        'id': user.id,
                        'email': user.email,
                        'name': f"{user.first_name} {user.last_name}".strip(),
                        'admin_group': user.admin_profile.get_admin_group_display()
                    }
                }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'error': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except AdminUserProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Admin profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'success': False,
            'error': f'Failed to create admin user: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary="Get admin user details",
    operation_description="Get detailed information about a specific admin user (SuperAdmin access only).",
    responses={
        200: openapi.Response(description='Admin user details'),
        404: openapi.Response(description='Admin user not found'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Admin User Management']
)
@swagger_auto_schema(
    method='put',
    operation_summary="Update admin user",
    operation_description="Update admin user information (SuperAdmin access only).",
    request_body=AdminUserUpdateSerializer,
    responses={
        200: openapi.Response(description='Admin user updated successfully'),
        400: openapi.Response(description='Bad request - validation error'),
        404: openapi.Response(description='Admin user not found'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Admin User Management']
)
@swagger_auto_schema(
    method='delete',
    operation_summary="Deactivate admin user",
    operation_description="Deactivate an admin user (soft delete - sets is_active=False) (SuperAdmin access only).",
    responses={
        200: openapi.Response(description='Admin user deactivated successfully'),
        404: openapi.Response(description='Admin user not found'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Admin User Management']
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def admin_user_detail(request, user_id):
    """
    Get, update, or deactivate an admin user.
    Super Admin only.
    """
    try:
        # Check if user is Super Admin
        admin_profile = request.user.admin_profile
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied. Only Super Admins can manage admin users.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get admin user profile
        try:
            target_profile = AdminUserProfile.objects.select_related('user').get(user_id=user_id)
        except AdminUserProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Admin user not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Prevent self-deactivation or self-role-change
        if target_profile.user == request.user:
            if request.method == 'DELETE':
                return Response({
                    'success': False,
                    'error': 'You cannot deactivate your own account'
                }, status=status.HTTP_400_BAD_REQUEST)
            elif request.method == 'PUT' and 'admin_group' in request.data:
                return Response({
                    'success': False,
                    'error': 'You cannot change your own role'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        if request.method == 'GET':
            # Get admin user details
            serializer = AdminUserListSerializer(target_profile)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        elif request.method == 'PUT':
            # Update admin user
            serializer = AdminUserUpdateSerializer(target_profile, data=request.data, partial=True)
            if serializer.is_valid():
                updated_profile = serializer.save()
                
                # Log activity
                AdminActivityLog.log_activity(
                    user=request.user,
                    activity_type='user_management',
                    description=f'Updated admin user: {target_profile.user.email}',
                    request=request,
                    metadata={
                        'updated_user_id': target_profile.user.id,
                        'updated_user_email': target_profile.user.email,
                        'changes': request.data
                    }
                )
                
                response_serializer = AdminUserListSerializer(updated_profile)
                return Response({
                    'success': True,
                    'message': 'Admin user updated successfully',
                    'data': response_serializer.data
                }, status=status.HTTP_200_OK)
            
            return Response({
                'success': False,
                'error': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            # Deactivate admin user (soft delete)
            target_profile.is_active = False
            target_profile.user.is_active = False
            target_profile.save()
            target_profile.user.save()
            
            # Log activity
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='user_management',
                description=f'Deactivated admin user: {target_profile.user.email}',
                request=request,
                metadata={
                    'deactivated_user_id': target_profile.user.id,
                    'deactivated_user_email': target_profile.user.email
                }
            )
            
            return Response({
                'success': True,
                'message': 'Admin user deactivated successfully'
            }, status=status.HTTP_200_OK)
        
    except AdminUserProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Admin profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'success': False,
            'error': f'Failed to manage admin user: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    operation_summary="Reset admin user password",
    operation_description="Reset password for an admin user (SuperAdmin access only).",
    request_body=AdminUserPasswordResetSerializer,
    responses={
        200: openapi.Response(description='Password reset successfully'),
        400: openapi.Response(description='Bad request - validation error'),
        404: openapi.Response(description='Admin user not found'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Admin User Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_user_reset_password(request, user_id):
    """
    Reset password for an admin user.
    Super Admin only.
    """
    try:
        # Check if user is Super Admin
        admin_profile = request.user.admin_profile
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied. Only Super Admins can reset admin passwords.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get admin user profile
        try:
            target_profile = AdminUserProfile.objects.select_related('user').get(user_id=user_id)
        except AdminUserProfile.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Admin user not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        serializer = AdminUserPasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            new_password = serializer.validated_data['new_password']
            
            # Set new password
            target_profile.user.set_password(new_password)
            target_profile.user.save()
            
            # Log activity
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='user_management',
                description=f'Reset password for admin user: {target_profile.user.email}',
                request=request,
                metadata={
                    'reset_password_user_id': target_profile.user.id,
                    'reset_password_user_email': target_profile.user.email
                }
            )
            
            return Response({
                'success': True,
                'message': 'Password reset successfully'
            }, status=status.HTTP_200_OK)
        
        return Response({
            'success': False,
            'error': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except AdminUserProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Admin profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'success': False,
            'error': f'Failed to reset password: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    operation_summary="Create AdminUserProfile for existing user",
    operation_description="Create an AdminUserProfile for an existing User that doesn't have one (SuperAdmin access only).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the existing User'),
            'admin_group': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=['superadmin', 'moderator'],
                description='Admin group to assign'
            ),
        },
        required=['user_id', 'admin_group']
    ),
    responses={
        201: openapi.Response(description='AdminUserProfile created successfully'),
        400: openapi.Response(description='Bad request - validation error'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        404: openapi.Response(description='User not found'),
        409: openapi.Response(description='AdminUserProfile already exists'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Admin User Management']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_user_create_profile(request):
    """
    Create an AdminUserProfile for an existing User.
    Super Admin only.
    """
    try:
        # Check if user is Super Admin
        admin_profile = request.user.admin_profile
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied. Only Super Admins can create admin profiles.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        user_id = request.data.get('user_id')
        admin_group = request.data.get('admin_group')
        
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not admin_group or admin_group not in ['superadmin', 'moderator']:
            return Response({
                'success': False,
                'error': 'admin_group must be either "superadmin" or "moderator"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user exists
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'error': f'User with id {user_id} not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if AdminUserProfile already exists
        if hasattr(user, 'admin_profile'):
            return Response({
                'success': False,
                'error': f'AdminUserProfile already exists for user {user.email}'
            }, status=status.HTTP_409_CONFLICT)
        
        # Create AdminUserProfile
        with transaction.atomic():
            admin_user_profile = AdminUserProfile.objects.create(
                user=user,
                admin_group=admin_group,
                is_active=user.is_active
            )
            
            # Ensure user is staff
            user.is_staff = True
            user.save()
            
            # Log activity
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='user_management',
                description=f'Created AdminUserProfile for user: {user.email}',
                request=request,
                metadata={
                    'user_id': user.id,
                    'user_email': user.email,
                    'admin_group': admin_group
                }
            )
        
        return Response({
            'success': True,
            'message': 'AdminUserProfile created successfully',
            'data': {
                'id': user.id,
                'email': user.email,
                'name': f"{user.first_name} {user.last_name}".strip(),
                'admin_group': admin_user_profile.get_admin_group_display()
            }
        }, status=status.HTTP_201_CREATED)
        
    except AdminUserProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Admin profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'success': False,
            'error': f'Failed to create AdminUserProfile: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Permission Groups Management Views

@swagger_auto_schema(
    method='get',
    operation_summary="List Permission Groups",
    operation_description="Get list of all permission groups (Super Admin only).",
    responses={
        200: openapi.Response(description='List of permission groups'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Permission Groups']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def permission_groups_list(request):
    """
    Get list of all permission groups.
    Super Admin only.
    """
    try:
        # Check if user is Super Admin
        admin_profile = request.user.admin_profile
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied. Only Super Admins can view permission groups.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get all permission groups
        groups = AdminPermissionGroup.objects.all().order_by('name')
        
        # Filter by is_active if requested
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() == 'true'
            groups = groups.filter(is_active=is_active_bool)
        
        serializer = AdminPermissionGroupListSerializer(groups, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        }, status=status.HTTP_200_OK)
        
    except AdminUserProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Admin profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'success': False,
            'error': f'Failed to list permission groups: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='post',
    operation_summary="Create Permission Group",
    operation_description="Create a new permission group (Super Admin only).",
    request_body=AdminPermissionGroupSerializer,
    responses={
        201: openapi.Response(description='Permission group created successfully'),
        400: openapi.Response(description='Bad request - validation error'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Permission Groups']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def permission_group_create(request):
    """
    Create a new permission group.
    Super Admin only.
    """
    try:
        # Check if user is Super Admin
        admin_profile = request.user.admin_profile
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied. Only Super Admins can create permission groups.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = AdminPermissionGroupSerializer(data=request.data)
        if serializer.is_valid():
            group = serializer.save()
            
            # Log activity
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='permission_management',
                description=f'Created permission group: {group.name}',
                request=request,
                metadata={
                    'group_id': group.id,
                    'group_name': group.name,
                    'permission_count': len(group.permissions or [])
                }
            )
            
            return Response({
                'success': True,
                'message': 'Permission group created successfully',
                'data': AdminPermissionGroupSerializer(group).data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'error': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except AdminUserProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Admin profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'success': False,
            'error': f'Failed to create permission group: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary="Get Permission Group",
    operation_description="Get details of a specific permission group (Super Admin only).",
    responses={
        200: openapi.Response(description='Permission group details'),
        404: openapi.Response(description='Permission group not found'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Permission Groups']
)
@swagger_auto_schema(
    method='put',
    operation_summary="Update Permission Group",
    operation_description="Update a permission group (Super Admin only).",
    request_body=AdminPermissionGroupSerializer,
    responses={
        200: openapi.Response(description='Permission group updated successfully'),
        400: openapi.Response(description='Bad request - validation error'),
        404: openapi.Response(description='Permission group not found'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Permission Groups']
)
@swagger_auto_schema(
    method='delete',
    operation_summary="Delete Permission Group",
    operation_description="Delete a permission group (Super Admin only).",
    responses={
        200: openapi.Response(description='Permission group deleted successfully'),
        404: openapi.Response(description='Permission group not found'),
        403: openapi.Response(description='Access denied - Super Admin only'),
        400: openapi.Response(description='Bad request - group has members'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Permission Groups']
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def permission_group_detail(request, group_id):
    """
    Get, update, or delete a permission group.
    Super Admin only.
    """
    try:
        # Check if user is Super Admin
        admin_profile = request.user.admin_profile
        if admin_profile.admin_group != 'superadmin' and not request.user.is_superuser:
            return Response({
                'success': False,
                'error': 'Access denied. Only Super Admins can manage permission groups.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            group = AdminPermissionGroup.objects.get(id=group_id)
        except AdminPermissionGroup.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Permission group not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            serializer = AdminPermissionGroupSerializer(group)
            return Response({
                'success': True,
                'data': serializer.data
            }, status=status.HTTP_200_OK)
        
        elif request.method == 'PUT':
            serializer = AdminPermissionGroupSerializer(group, data=request.data, partial=True)
            if serializer.is_valid():
                updated_group = serializer.save()
                
                # Log activity
                AdminActivityLog.log_activity(
                    user=request.user,
                    activity_type='permission_management',
                    description=f'Updated permission group: {updated_group.name}',
                    request=request,
                    metadata={
                        'group_id': updated_group.id,
                        'group_name': updated_group.name,
                        'permission_count': len(updated_group.permissions or [])
                    }
                )
                
                return Response({
                    'success': True,
                    'message': 'Permission group updated successfully',
                    'data': AdminPermissionGroupSerializer(updated_group).data
                }, status=status.HTTP_200_OK)
            
            return Response({
                'success': False,
                'error': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            # Check if group has members
            member_count = group.members.filter(admin_group='moderator', is_active=True).count()
            if member_count > 0:
                return Response({
                    'success': False,
                    'error': f'Cannot delete permission group. It has {member_count} active member(s). Please reassign members first.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            group_name = group.name
            group.delete()
            
            # Log activity
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='permission_management',
                description=f'Deleted permission group: {group_name}',
                request=request,
                metadata={
                    'group_name': group_name
                }
            )
            
            return Response({
                'success': True,
                'message': 'Permission group deleted successfully'
            }, status=status.HTTP_200_OK)
        
    except AdminUserProfile.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Admin profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'success': False,
            'error': f'Failed to manage permission group: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary='List Mock PDF download report (admin)',
    operation_description='Returns stats (total, today, this week, this month) and paginated list of completed mock PDF downloads. Admin only.',
    manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description='Page number'),
        openapi.Parameter('page_size', openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description='Page size'),
    ],
    responses={200: openapi.Response(description='Mock PDF report data'), 403: openapi.Response(description='Admin required')},
    tags=['CoreAdmin Reports']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mock_pdf_reports_list(request):
    """List mock PDF downloads for admin report: stats + paginated list. Uses existing PDFDownload model only."""
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    base_qs = PDFDownload.objects.filter(status='completed')
    stats = {
        'total': base_qs.count(),
        'today': base_qs.filter(created_at__gte=today_start).count(),
        'this_week': base_qs.filter(created_at__gte=week_start).count(),
        'this_month': base_qs.filter(created_at__gte=month_start).count(),
    }

    page = int(request.GET.get('page', 1))
    page_size = min(int(request.GET.get('page_size', 20)), 100)
    paginator = Paginator(base_qs.order_by('-created_at'), page_size)
    page_obj = paginator.get_page(page)

    def build_logo_url(pdf_download, req):
        if pdf_download.customer_logo:
            try:
                return req.build_absolute_uri(pdf_download.customer_logo.url)
            except Exception:
                return None
        return None

    items = []
    for pdf in page_obj.object_list:
        items.append({
            'id': pdf.id,
            'customer_name': pdf.customer_name or '',
            'customer_mobile': pdf.customer_mobile or '',
            'customer_logo_url': build_logo_url(pdf, request),
            'number_of_designs': pdf.products_count or pdf.total_pages or 0,
            'total_pages': pdf.total_pages,
            'download_type': pdf.download_type,
            'status': pdf.status,
            'created_at': pdf.created_at.isoformat() if pdf.created_at else None,
            'completed_at': pdf.completed_at.isoformat() if pdf.completed_at else None,
        })

    return Response({
        'stats': stats,
        'downloads': items,
        'total_count': paginator.count,
        'total_pages': paginator.num_pages,
        'current_page': page,
    })

@swagger_auto_schema(
    method='get',
    operation_summary='Download Mock PDF file (admin)',
    operation_description='Download a completed mock PDF file by id. Admin only.',
    responses={200: openapi.Response(description='PDF file'), 403: openapi.Response(description='Admin required'), 404: openapi.Response(description='Not found')},
    tags=['CoreAdmin Reports']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mock_pdf_download_file(request, download_id):
    """Allow admin to download any completed mock PDF. Uses existing PDFDownload model and file storage."""
    try:
        admin_profile = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

    try:
        pdf_download = PDFDownload.objects.get(id=download_id)
    except PDFDownload.DoesNotExist:
        return Response({'error': 'PDF download not found'}, status=status.HTTP_404_NOT_FOUND)

    if pdf_download.status != 'completed':
        return Response({'error': f'PDF is not ready. Status: {pdf_download.status}'}, status=status.HTTP_400_BAD_REQUEST)

    file_path = None
    if pdf_download.pdf_file_path:
        file_path = os.path.join(settings.MEDIA_ROOT, pdf_download.pdf_file_path)
    if not file_path or not os.path.exists(file_path):
        user = pdf_download.get_user()
        if user:
            alt = os.path.join(settings.MEDIA_ROOT, str(user.id), 'pdfs', f'pdf_download_{download_id}.pdf')
            if os.path.exists(alt):
                file_path = alt
        if not file_path or not os.path.exists(file_path):
            alt = os.path.join(settings.MEDIA_ROOT, 'pdfs', f'pdf_download_{download_id}.pdf')
            if os.path.exists(alt):
                file_path = alt
        if not file_path or not os.path.exists(file_path):
            return Response({'error': 'PDF file not available'}, status=status.HTTP_404_NOT_FOUND)

    customer_name = (pdf_download.customer_name or '').strip()
    if customer_name:
        sanitized = re.sub(r'[^a-zA-Z0-9\s-]', '', customer_name)
        sanitized = re.sub(r'\s+', ' ', sanitized.strip())[:50]
        filename = f'{sanitized}.pdf'
    else:
        filename = f'designs_{download_id}.pdf'

    try:
        response = FileResponse(
            open(file_path, 'rb'),
            as_attachment=True,
            filename=filename,
            content_type='application/pdf'
        )
        from urllib.parse import quote
        response['Content-Disposition'] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}'
        response['X-Filename'] = filename
        return response
    except Exception as e:
        logger = logging.getLogger(__name__)

        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method="get",
    operation_summary="List PDF clients (admin)",
    operation_description="List PDF clients that can be used for admin-generated PDFs.",
    manual_parameters=[
        openapi.Parameter(
            "search",
            openapi.IN_QUERY,
            type=openapi.TYPE_STRING,
            description="Search by client name",
        ),
        openapi.Parameter(
            "page",
            openapi.IN_QUERY,
            type=openapi.TYPE_INTEGER,
            description="Page number",
        ),
        openapi.Parameter(
            "page_size",
            openapi.IN_QUERY,
            type=openapi.TYPE_INTEGER,
            description="Page size",
        ),
    ],
    responses={200: openapi.Response(description="List of PDF clients")},
    tags=["CoreAdmin PDF Clients"],
)
@swagger_auto_schema(
    method="post",
    operation_summary="Create PDF client (admin)",
    operation_description="Create a new PDF client that admins can use for generating PDFs.",
    request_body=PDFClientSerializer,
    responses={201: openapi.Response(description="Created PDF client")},
    tags=["CoreAdmin PDF Clients"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def pdf_clients_list_create(request):
    """List or create PDF clients for admin-generated PDFs."""
    try:
        _ = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        search = request.GET.get("search", "").strip()
        qs = PDFClient.objects.all().order_by("name")
        if search:
            qs = qs.filter(name__icontains=search)
        page = int(request.GET.get("page", 1))
        page_size = min(int(request.GET.get("page_size", 20)), 100)
        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)
        serializer = PDFClientSerializer(page_obj.object_list, many=True)
        return Response(
            {
                "results": serializer.data,
                "total_count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page_obj.number,
            }
        )

    # POST
    data = request.data.copy()
    serializer = PDFClientSerializer(data=data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    client = PDFClient.objects.create(
        name=serializer.validated_data["name"],
        created_by=request.user,
        updated_by=request.user,
    )
    out = PDFClientSerializer(client)
    return Response(out.data, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="get",
    operation_summary="List PDF client jobs (admin)",
    operation_description="List PDF client jobs with optional filter by client_id. Paginated.",
    manual_parameters=[
        openapi.Parameter("client_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Filter by PDF client ID"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Page number"),
        openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, description="Page size"),
    ],
    tags=["CoreAdmin PDF Clients"],
)
@swagger_auto_schema(
    method="post",
    operation_summary="Create PDF client job (admin)",
    operation_description="Create a new PDF generation job for a given PDF client. Accepts optional customer_logo file.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "data": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "client_id": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "number_of_pdfs": openapi.Schema(type=openapi.TYPE_INTEGER),
                    "designs_per_pdf": openapi.Schema(
                        type=openapi.TYPE_INTEGER,
                        description="Designs per PDF (20, 50, or 100). Defaults to 100.",
                    ),
                    "customer_name": openapi.Schema(type=openapi.TYPE_STRING),
                    "customer_mobile": openapi.Schema(type=openapi.TYPE_STRING),
                },
                required=["client_id", "number_of_pdfs", "customer_name", "customer_mobile"],
            )
        },
    ),
    tags=["CoreAdmin PDF Clients"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def pdf_client_jobs_create(request):
    """List (GET) or create (POST) PDF client jobs."""
    try:
        _ = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)

    if request.method == "GET":
        client_id = request.GET.get("client_id")
        qs = PDFClientJob.objects.select_related("client").order_by("-created_at")
        if client_id:
            try:
                qs = qs.filter(client_id=int(client_id))
            except ValueError:
                pass
        page = int(request.GET.get("page", 1))
        page_size = min(int(request.GET.get("page_size", 20)), 100)
        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)
        serializer = PDFClientJobStatusSerializer(page_obj.object_list, many=True)
        return Response({
            "results": serializer.data,
            "total_count": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page_obj.number,
        })

    # POST: create job
    payload = request.data
    if "data" in payload and isinstance(payload.get("data"), str):
        import json

        try:
            data = json.loads(payload["data"])
        except Exception:
            return Response({"error": "Invalid JSON in 'data' field"}, status=status.HTTP_400_BAD_REQUEST)
    else:
        data = payload

    serializer = PDFClientJobCreateSerializer(data=data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    client = PDFClient.objects.get(id=serializer.validated_data["client_id"])

    # Enforce per-client concurrency at creation time.
    # Only block when an existing job is actively processing so stale "pending" jobs don't block new ones.
    if PDFClientJob.objects.filter(
        client=client,
        status__in=["processing"],
    ).exists():
        return Response(
            {"error": "Another PDF generation job is already running for this client."},
            status=status.HTTP_409_CONFLICT,
        )

    designs_per_pdf = serializer.validated_data.get("designs_per_pdf") or 100
    customer_logo = request.FILES.get("customer_logo")

    job = PDFClientJob.objects.create(
        client=client,
        status="pending",
        designs_per_pdf=designs_per_pdf,
        requested_pdfs=serializer.validated_data["number_of_pdfs"],
        customer_name=serializer.validated_data["customer_name"],
        customer_mobile=serializer.validated_data["customer_mobile"],
        customer_logo=customer_logo,
        created_by=request.user,
    )

    # Trigger async generation
    from Catalog.tasks import generate_client_pdfs_task

    generate_client_pdfs_task.delay(job.id)

    out = PDFClientJobStatusSerializer(job)
    return Response(out.data, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method="get",
    operation_summary="Get PDF client job status (admin)",
    operation_description="Get status and progress information for a specific PDF client job.",
    responses={200: openapi.Response(description="Job status", schema=PDFClientJobStatusSerializer)},
    tags=["CoreAdmin PDF Clients"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pdf_client_job_status(request, job_id):
    """Return status of a PDF client job."""
    try:
        _ = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)

    try:
        job = PDFClientJob.objects.select_related("client").get(id=job_id)
    except PDFClientJob.DoesNotExist:
        return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = PDFClientJobStatusSerializer(job)
    return Response(serializer.data)


@swagger_auto_schema(
    method="get",
    operation_summary="Download PDF client job ZIP (admin)",
    operation_description="Download the ZIP archive containing all PDFs for a completed PDF client job.",
    responses={200: openapi.Response(description="ZIP file"), 404: openapi.Response(description="Not found")},
    tags=["CoreAdmin PDF Clients"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def pdf_client_job_download(request, job_id):
    """Download the ZIP file for a completed PDF client job."""
    try:
        _ = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)

    try:
        job = PDFClientJob.objects.select_related("client").get(id=job_id)
    except PDFClientJob.DoesNotExist:
        return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

    if job.status != "completed" or not job.zip_file_path:
        return Response(
            {"error": f"Job is not completed. Current status: {job.status}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    media_root = getattr(settings, "MEDIA_ROOT", None)
    if not media_root:
        return Response({"error": "MEDIA_ROOT is not configured"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    file_path = os.path.join(media_root, job.zip_file_path)
    if not os.path.exists(file_path):
        return Response({"error": "ZIP file not found"}, status=status.HTTP_404_NOT_FOUND)

    filename = f"{job.client.name.replace(' ', '_')}_pdfs_job_{job.id}.zip"

    try:
        response = FileResponse(
            open(file_path, "rb"),
            as_attachment=True,
            filename=filename,
            content_type="application/zip",
        )
        from urllib.parse import quote

        response["Content-Disposition"] = f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}'
        response["X-Filename"] = filename
        return response
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.info(f"pdf_client_job_download: error serving ZIP for job {job_id}: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method="delete",
    operation_summary="Delete PDF client job (admin)",
    operation_description="Delete a PDF client job. Allowed only for jobs with status 'pending' or 'failed'. Processing or completed jobs cannot be deleted.",
    responses={
        204: openapi.Response(description="Job deleted"),
        400: openapi.Response(description="Job cannot be deleted (e.g. processing or completed)"),
        404: openapi.Response(description="Job not found"),
    },
    tags=["CoreAdmin PDF Clients"],
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def pdf_client_job_delete(request, job_id):
    """Delete a pending or failed PDF client job. Cannot delete processing or completed jobs."""
    try:
        _ = request.user.admin_profile
    except AdminUserProfile.DoesNotExist:
        return Response({"error": "Admin access required"}, status=status.HTTP_403_FORBIDDEN)

    try:
        job = PDFClientJob.objects.get(id=job_id)
    except PDFClientJob.DoesNotExist:
        return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

    if job.status not in ("pending", "failed"):
        return Response(
            {"error": f"Cannot delete job with status '{job.status}'. Only pending or failed jobs can be deleted."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    job.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)
