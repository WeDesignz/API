from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import IntegrityError
from datetime import timedelta
import random
import string
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Email, MobileNumber, OTP
from .serializers import (
    SignupSerializer, LoginSerializer, EmailVerificationSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    MobileVerificationSerializer, AddMobileNumberSerializer,
    ResendOTPSerializer, UserProfileSerializer, ChangePasswordSerializer,
    EmailListSerializer, CustomerNotificationSerializer
)


def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))


def send_otp_email(email, otp, purpose):
    """Send OTP via email (non-blocking)"""
    import threading
    import logging
    import traceback
    
    logger = logging.getLogger(__name__)
    
    subject = f"WeDesignz - {purpose} OTP"
    message = f"""
    Your OTP for {purpose} is: {otp}
    
    This OTP is valid for 10 minutes.
    
    If you didn't request this, please ignore this email.
    
    Best regards,
    WeDesignz Team
    """
    
    def send_email_async():
        """Send email in background thread to avoid blocking the request"""
        try:
            # Use NO_REPLY_EMAIL for OTP messages
            from_email = settings.NO_REPLY_EMAIL
            logger.info(f"Attempting to send OTP email to {email} from {from_email}")
            logger.info(f"SMTP Config - Host: {settings.EMAIL_HOST}, Port: {settings.EMAIL_PORT}, SSL: {getattr(settings, 'EMAIL_USE_SSL', False)}, TLS: {settings.EMAIL_USE_TLS}, User: {settings.EMAIL_HOST_USER}")
            
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[email],
                fail_silently=False,
            )
            logger.info(f"OTP email sent successfully to {email}")
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Failed to send OTP email to {email}: {str(e)}")
            logger.error(f"Error traceback: {error_trace}")
            # Also print to console for immediate visibility
            print(f"EMAIL ERROR: Failed to send OTP to {email}: {str(e)}")
            print(f"EMAIL ERROR TRACEBACK: {error_trace}")
    
    # Start email sending in background thread to prevent request timeout
    thread = threading.Thread(target=send_email_async, daemon=True)
    thread.start()
    
    # Return True immediately - email is being sent in background
    return True


def send_otp_sms(mobile_number, otp, purpose):
    """Send OTP via WhatsApp"""
    from common.whatsapp_service import WhatsAppService
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        success = WhatsAppService.send_otp_message(
            phone_number=mobile_number,
            otp_code=otp,
            purpose=purpose
        )
        return success
    except Exception as e:
        logger.error(f"Failed to send OTP via WhatsApp: {str(e)}")
        return False


@swagger_auto_schema(
    method='post',
    operation_summary="User Registration",
    operation_description="Register a new user account without email/mobile verification. Creates User, Email, and MobileNumber records. Verification happens during designer onboarding. Returns JWT tokens for immediate login.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='User email address',
                example='john.doe@example.com'
            ),
            'first_name': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='User first name',
                example='John'
            ),
            'last_name': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='User last name',
                example='Doe'
            ),
            'mobile_number': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='User mobile number',
                example='+1234567890'
            ),
            'password': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='User password (minimum 8 characters)',
                example='password123'
            ),
            'confirm_password': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Password confirmation',
                example='password123'
            )
        },
        required=['email', 'first_name', 'last_name', 'mobile_number', 'password', 'confirm_password']
    ),
    responses={
        201: openapi.Response(
            description="User registered successfully",
            examples={
                "application/json": {
                    "message": "User registered successfully. You can now start designer onboarding.",
                    "user": {
                        "id": 1,
                        "username": "john.doe",
                        "email": "john.doe@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "is_active": True
                    },
                    "tokens": {
                        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
                    }
                }
            }
        ),
        400: openapi.Response(description="Bad request - validation errors")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """
    User registration without email/mobile verification.
    Creates User, Email, and MobileNumber records.
    Verification will be done during designer onboarding.
    """
    from django.db import transaction
    
    serializer = SignupSerializer(data=request.data)
    
    if serializer.is_valid():
        with transaction.atomic():
            # Create user with username from email (left part of @)
            email = serializer.validated_data['email']
            mobile_number = serializer.validated_data['mobile_number']
            username = email.split('@')[0]  # Use left part of email as username
            
            # Ensure username is unique by adding numbers if needed
            original_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{original_username}{counter}"
                counter += 1
            
            # Create user as active (no verification required at signup)
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=serializer.validated_data['first_name'],
                last_name=serializer.validated_data['last_name'],
                password=serializer.validated_data['password'],
                is_active=True  # User is active immediately, verification happens during onboarding
            )
            
            # Create email record (not verified yet)
            email_obj = Email.objects.create(
                email=user.email,
                is_primary=True,
                is_verified=False,  # Will be verified during onboarding
                created_by=user
            )
            
            # Create mobile number record (not verified yet)
            mobile_obj = MobileNumber.objects.create(
                mobile_number=mobile_number,
                is_primary=True,
                is_verified=False,  # Will be verified during onboarding
                created_by=user
            )
            
            # Generate JWT tokens for automatic login
            refresh = RefreshToken.for_user(user)
            
            # Serialize full user profile with emails and mobile_numbers
            user_serializer = UserProfileSerializer(user)
            
            return Response({
                'message': 'User registered successfully. You can now start designer onboarding.',
                'user': user_serializer.data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
            }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary="User Login",
    operation_description="Authenticate user with username/email/mobile and password. Returns JWT tokens.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'username': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Username, email, or mobile number',
                example='john.doe@example.com'
            ),
            'password': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='User password',
                example='password123'
            ),
            'remember_me': openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description='If true, access token expires in 24 hours and refresh token in 30 days. If false, uses default lifetimes (60 minutes access, 7 days refresh).',
                example=False
            )
        },
        required=['username', 'password']
    ),
    responses={
        200: openapi.Response(
            description="Login successful",
            examples={
                "application/json": {
                    "message": "Login successful",
                    "user": {
                        "id": 1,
                        "username": "john.doe",
                        "email": "john.doe@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "is_active": True
                    },
                    "tokens": {
                        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
                    }
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid credentials")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    User login with username/email/mobile + password.
    Returns full user profile including emails and mobile_numbers.
    Supports remember_me option for extended token lifetimes.
    """
    serializer = LoginSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        remember_me = serializer.validated_data.get('remember_me', False)
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # If remember_me is True, set extended token lifetimes
        if remember_me:
            # Access token: 24 hours, Refresh token: 30 days
            from datetime import timedelta
            refresh.set_exp(lifetime=timedelta(days=30))
            access = refresh.access_token
            access.set_exp(lifetime=timedelta(hours=24))
        else:
            # Use default lifetimes from settings (60 minutes access, 7 days refresh)
            access = refresh.access_token
        
        # Serialize full user profile with emails and mobile_numbers
        user_serializer = UserProfileSerializer(user)
        
        return Response({
            'message': 'Login successful',
            'user': user_serializer.data,
            'tokens': {
                'access': str(access),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary="User Logout",
    operation_description="Logout user by blacklisting the refresh token.",
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
        200: openapi.Response(
            description="Logout successful",
            examples={
                "application/json": {
                    "message": "Logout successful"
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid token")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    User logout - blacklist refresh token.
    """
    try:
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'Invalid token'
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary="Verify Email",
    operation_description="Verify user email address using OTP sent during registration.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='User email address',
                example='john.doe@example.com'
            ),
            'otp': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='6-digit OTP received via email',
                example='123456'
            )
        },
        required=['email', 'otp']
    ),
    responses={
        200: openapi.Response(
            description="Email verified successfully",
            examples={
                "application/json": {
                    "message": "Email verified successfully",
                    "user": {
                        "id": 1,
                        "username": "john.doe",
                        "email": "john.doe@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "is_active": True
                    }
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid OTP or email")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """
    Verify email with OTP sent via email.
    """
    serializer = EmailVerificationSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        otp_obj = serializer.validated_data.get('otp_obj')
        email = serializer.validated_data['email']  # Get the email being verified
        
        # Delete OTP record after successful verification
        if otp_obj:
            otp_obj.delete()
        
        # Get or create email record and mark as verified
        # Use get_or_create to handle cases where Email record doesn't exist yet (e.g., during onboarding)
        email_obj, created = Email.objects.get_or_create(
            email=email,
            created_by=user,
            defaults={
                'is_primary': (email == user.email),  # Set as primary if it matches user.email
                'is_verified': True
            }
        )
        
        # If email record already existed, just mark it as verified
        if not created:
            email_obj.is_verified = True
            email_obj.save()
        
        # If this is the user's primary email, update user.email
        if email == user.email or email_obj.is_primary:
            user.email = email
            user.is_active = True
            user.save()
        
        return Response({
            'message': 'Email verified successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_active': user.is_active,
            }
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary="Request Password Reset",
    operation_description="Request password reset by sending OTP to user's verified email address or WhatsApp.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='User email address (required when delivery_method is email)',
                example='john.doe@example.com'
            ),
            'delivery_method': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='OTP delivery method',
                example='email',
                enum=['email', 'whatsapp'],
                default='email'
            ),
            'phone_number': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='10-digit phone number (required when delivery_method is whatsapp)',
                example='9876543210'
            )
        },
        required=[]
    ),
    responses={
        200: openapi.Response(
            description="Password reset OTP sent successfully",
            examples={
                "application/json": {
                    "message": "OTP sent to your verified email address",
                    "delivery_method": "email"
                }
            }
        ),
        400: openapi.Response(description="Bad request - email not found or not verified")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """
    Request password reset - send OTP to verified email or WhatsApp.
    """
    serializer = PasswordResetRequestSerializer(data=request.data)
    
    if serializer.is_valid():
        delivery_method = serializer.validated_data.get('delivery_method', 'email')
        
        # Generate and send OTP
        otp = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)
        
        if delivery_method == 'whatsapp':
            user = serializer.validated_data.get('user')
            mobile_number = serializer.validated_data.get('mobile_number')
            
            if user and mobile_number:
                # Format phone number with country code if needed
                # Ensure it starts with country code (default to +91 for India)
                if not mobile_number.startswith('+'):
                    # Extract digits only
                    digits_only = ''.join(filter(str.isdigit, mobile_number))
                    # If it's 10 digits, add +91
                    if len(digits_only) == 10:
                        mobile_number = '+91' + digits_only
                    else:
                        mobile_number = '+' + digits_only
                
                # Create mobile OTP
                OTP.objects.create(
                    otp=otp,
                    otp_type='M',
                    otp_for='password_reset',
                    expires_at=expires_at,
                    created_by=user
                )
                
                # Send OTP via WhatsApp
                send_otp_sms(mobile_number, otp, "Password Reset")
                
                return Response({
                    'message': f'OTP sent to your WhatsApp ({mobile_number})',
                    'delivery_method': 'whatsapp'
                }, status=status.HTTP_200_OK)
        
        # Default: Send via email
        email = serializer.validated_data['email']
        user = User.objects.get(email__iexact=email)
        
        OTP.objects.create(
            otp=otp,
            otp_type='E',
            otp_for='password_reset',
            expires_at=expires_at,
            created_by=user
        )
        
        # Send OTP email
        send_otp_email(email, otp, "Password Reset")
        
        return Response({
            'message': 'OTP sent to your verified email address',
            'delivery_method': 'email'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary="Verify Password Reset OTP",
    operation_description="Verify OTP for password reset without setting password.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='User email address (required when OTP was sent via email)',
                example='john.doe@example.com'
            ),
            'phone_number': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='10-digit phone number (required when OTP was sent via WhatsApp)',
                example='9876543210'
            ),
            'otp': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='6-digit OTP received via email or WhatsApp',
                example='123456'
            )
        },
        required=['otp']
    ),
    responses={
        200: openapi.Response(
            description="OTP verified successfully",
            examples={
                "application/json": {
                    "message": "OTP verified successfully",
                    "verified": True
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid OTP")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_password_reset_otp(request):
    """
    Verify OTP for password reset without setting password.
    """
    
    email = request.data.get('email')
    phone_number = request.data.get('phone_number')
    otp = request.data.get('otp')
    
    if not otp:
        return Response({
            'error': 'OTP is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = None
    
    # Find user by email or phone number
    if email:
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response({
                'error': 'User with this email does not exist.'
            }, status=status.HTTP_400_BAD_REQUEST)
    elif phone_number:
        phone_digits = ''.join(filter(str.isdigit, phone_number))
        if len(phone_digits) != 10:
            return Response({
                'error': 'Phone number must be exactly 10 digits.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        verified_mobiles = MobileNumber.objects.filter(is_verified=True)
        mobile_obj = None
        for mobile in verified_mobiles:
            stored_digits = ''.join(filter(str.isdigit, mobile.mobile_number))
            if len(stored_digits) >= 10 and stored_digits[-10:] == phone_digits:
                mobile_obj = mobile
                break
        
        if not mobile_obj:
            return Response({
                'error': 'User with this phone number does not exist.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = mobile_obj.created_by
    else:
        return Response({
            'error': 'Either email or phone number is required.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Try to find OTP from either email or mobile
    otp_obj = None
    try:
        otp_obj = OTP.objects.get(
            otp=otp,
            otp_type='E',
            otp_for='password_reset',
            created_by=user,
            is_verified=False
        )
    except OTP.DoesNotExist:
        try:
            otp_obj = OTP.objects.get(
                otp=otp,
                otp_type='M',
                otp_for='password_reset',
                created_by=user,
                is_verified=False
            )
        except OTP.DoesNotExist:
            return Response({
                'error': 'Invalid OTP. Please check the code and try again.'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    if otp_obj.is_expired():
        return Response({
            'error': 'OTP has expired. Please request a new OTP.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Mark OTP as verified (but don't delete it yet - we'll use it in password reset)
    otp_obj.is_verified = True
    otp_obj.save()
    
    return Response({
        'message': 'OTP verified successfully',
        'verified': True
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    operation_summary="Confirm Password Reset",
    operation_description="Confirm password reset using OTP and set new password.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='User email address (required when OTP was sent via email)',
                example='john.doe@example.com'
            ),
            'phone_number': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='10-digit phone number (required when OTP was sent via WhatsApp)',
                example='9876543210'
            ),
            'otp': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='6-digit OTP received via email or WhatsApp',
                example='123456'
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
        required=['otp', 'new_password', 'confirm_password']
    ),
    responses={
        200: openapi.Response(
            description="Password reset successfully",
            examples={
                "application/json": {
                    "message": "Password reset successfully"
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid OTP or password mismatch")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_password_reset(request):
    """
    Confirm password reset with OTP.
    """
    serializer = PasswordResetConfirmSerializer(data=request.data)
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        otp_obj = serializer.validated_data['otp_obj']
        new_password = serializer.validated_data['new_password']
        
        # OTP is already verified from the previous step, just update password
        # Update password
        user.set_password(new_password)
        user.save()
        
        # Delete OTP after successful password reset
        otp_obj.delete()
        
        return Response({
            'message': 'Password reset successfully'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary="Add Mobile Number",
    operation_description="Add mobile number to user account and send verification OTP.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'mobile_number': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Mobile number with country code',
                example='+1234567890'
            )
        },
        required=['mobile_number']
    ),
    responses={
        200: openapi.Response(
            description="Mobile number added and OTP sent",
            examples={
                "application/json": {
                    "message": "Mobile number added. OTP sent for verification."
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid mobile number or already exists")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_mobile_number(request):
    """
    Add mobile number to user account.
    """
    try:
        serializer = AddMobileNumberSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            mobile_number = serializer.validated_data['mobile_number']
            
            # Check if mobile number already exists (globally unique)
            try:
                existing_mobile = MobileNumber.objects.get(mobile_number=mobile_number)
                
                # If it exists and belongs to current user, just send OTP
                if existing_mobile.created_by == request.user:
                    # Generate and send OTP
                    otp = generate_otp()
                    expires_at = timezone.now() + timedelta(minutes=10)
                    
                    OTP.objects.create(
                        otp=otp,
                        otp_type='M',
                        otp_for='mobile_verification',
                        expires_at=expires_at,
                        created_by=request.user
                    )
                    
                    # Send OTP via WhatsApp
                    send_otp_sms(mobile_number, otp, "Mobile Verification")
                    
                    return Response({
                        'message': 'OTP sent to your mobile number.',
                        'mobile_number': mobile_number
                    }, status=status.HTTP_200_OK)
                else:
                    # Mobile number exists but belongs to another user
                    return Response({
                        'error': 'This mobile number is already registered with another account.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            except MobileNumber.DoesNotExist:
                # Mobile number doesn't exist, create it
                pass
            
            # Check if user already has mobile numbers
            existing_mobiles = MobileNumber.objects.filter(created_by=request.user)
            is_first_mobile = existing_mobiles.count() == 0
            
            # Create mobile number record
            # Only set as primary if it's the first mobile number
            mobile_obj = MobileNumber.objects.create(
                mobile_number=mobile_number,
                is_primary=is_first_mobile,
                created_by=request.user
            )
            
            # Generate and send OTP
            otp = generate_otp()
            expires_at = timezone.now() + timedelta(minutes=10)
            
            OTP.objects.create(
                otp=otp,
                otp_type='M',
                otp_for='mobile_verification',
                expires_at=expires_at,
                created_by=request.user
            )
            
            # Send OTP via WhatsApp
            send_otp_sms(mobile_number, otp, "Mobile Verification")
            
            return Response({
                'message': 'Mobile number added. Please verify with OTP sent to your mobile.',
                'mobile_number': mobile_number
            }, status=status.HTTP_201_CREATED)
        
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
            'error': error_message or 'Invalid mobile number. Please check your input and try again.',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    except IntegrityError as e:
        # Handle unique constraint violation more gracefully
        if 'mobile_number' in str(e):
            return Response({
                'error': 'This mobile number is already registered. Please use a different number or verify the existing one.'
            }, status=status.HTTP_400_BAD_REQUEST)
        raise
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error adding mobile number: {str(e)}\n{traceback.format_exc()}")
        return Response({
            'error': f'An error occurred while adding mobile number: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_summary="Verify Mobile Number",
    operation_description="Verify mobile number using OTP sent via WhatsApp.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'mobile_number': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Mobile number with country code',
                example='+1234567890'
            ),
            'otp': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='6-digit OTP received via WhatsApp',
                example='123456'
            )
        },
        required=['mobile_number', 'otp']
    ),
    responses={
        200: openapi.Response(
            description="Mobile number verified successfully",
            examples={
                "application/json": {
                    "message": "Mobile number verified successfully"
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid OTP or mobile number")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_mobile_number(request):
    """
    Verify mobile number with OTP sent via WhatsApp.
    """
    serializer = MobileVerificationSerializer(data=request.data)
    
    if serializer.is_valid():
        mobile_obj = serializer.validated_data['mobile_obj']
        otp_obj = serializer.validated_data.get('otp_obj')
        
        # Mark OTP as verified
        if otp_obj:
            otp_obj.is_verified = True
            otp_obj.save()
            # Delete OTP record after successful verification
            otp_obj.delete()
        
        # Mark mobile number as verified
        mobile_obj.is_verified = True
        mobile_obj.save()
        
        return Response({
            'message': 'Mobile number verified successfully'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='delete',
    operation_summary="Delete Mobile Number",
    operation_description="Delete a mobile number from user account.",
    responses={
        200: openapi.Response(
            description="Mobile number deleted successfully",
            examples={
                "application/json": {
                    "message": "Mobile number deleted successfully"
                }
            }
        ),
        400: openapi.Response(description="Bad request - cannot delete primary or only mobile"),
        401: openapi.Response(description="Unauthorized - authentication required"),
        404: openapi.Response(description="Mobile number not found")
    },
    tags=['Authentication']
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_mobile_number(request, mobile_id):
    """
    Delete a mobile number from user account.
    Rules:
    - User can delete any unverified mobile number
    - If there are 2 verified numbers, one must be primary and cannot be deleted
    - The other verified number can be deleted
    - At least one mobile number must remain
    """
    try:
        mobile_obj = MobileNumber.objects.get(id=mobile_id, created_by=request.user)
    except MobileNumber.DoesNotExist:
        return Response({
            'error': 'Mobile number not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if this is the only mobile number
    total_mobiles = MobileNumber.objects.filter(created_by=request.user).count()
    if total_mobiles <= 1:
        return Response({
            'error': 'Cannot delete the only mobile number'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get all verified mobile numbers for this user
    verified_mobiles = MobileNumber.objects.filter(
        created_by=request.user,
        is_verified=True
    )
    verified_count = verified_mobiles.count()
    
    # If this is a verified mobile number
    if mobile_obj.is_verified:
        # If there are 2 verified numbers, the primary one cannot be deleted
        if verified_count == 2 and mobile_obj.is_primary:
            return Response({
                'error': 'Cannot delete primary verified mobile number. There must be at least one verified primary mobile number.'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Unverified numbers can always be deleted (if not the only one)
    # Verified non-primary numbers can be deleted
    # Primary verified numbers can only be deleted if there's another verified number to take its place
    
    mobile_obj.delete()
    
    return Response({
        'message': 'Mobile number deleted successfully'
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='put',
    operation_summary="Update Mobile Number",
    operation_description="Update mobile number details (e.g., set as primary).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'is_primary': openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description='Set as primary mobile number',
                example=True
            ),
        }
    ),
    responses={
        200: openapi.Response(
            description="Mobile number updated successfully",
            examples={
                "application/json": {
                    "message": "Mobile number updated successfully",
                    "mobile_number": {
                        "id": 1,
                        "mobile_number": "+1234567890",
                        "is_verified": True,
                        "is_primary": True,
                        "created_at": "2024-01-01T00:00:00Z"
                    }
                }
            }
        ),
        400: openapi.Response(description="Bad request - validation errors"),
        404: openapi.Response(description="Mobile number not found")
    },
    tags=['Authentication']
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_mobile_number(request, mobile_id):
    """
    Update mobile number details.
    """
    try:
        mobile_obj = MobileNumber.objects.get(id=mobile_id, created_by=request.user)
    except MobileNumber.DoesNotExist:
        return Response({
            'error': 'Mobile number not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    try:
        # Manually update fields to avoid serializer issues
        is_primary = request.data.get('is_primary', False)
        
        # Before saving, if setting as primary, unset other primary mobile numbers
        if is_primary:
            MobileNumber.objects.filter(
                created_by=request.user,
                is_primary=True
            ).exclude(id=mobile_id).update(is_primary=False)
            mobile_obj.is_primary = True
        
        # Update updated_by field
        mobile_obj.updated_by = request.user
        mobile_obj.save()
        
        return Response({
            'message': 'Mobile number updated successfully',
            'mobile_number': {
                'id': mobile_obj.id,
                'mobile_number': mobile_obj.mobile_number,
                'is_verified': mobile_obj.is_verified,
                'is_primary': mobile_obj.is_primary,
                'created_at': mobile_obj.created_at
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating mobile number: {str(e)}\n{traceback.format_exc()}")
        return Response({
            'error': f'An error occurred while updating mobile number: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_summary="Resend OTP",
    operation_description="Resend OTP for email or mobile verification.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='User email address (for email verification)',
                example='john.doe@example.com'
            ),
            'mobile_number': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Mobile number with country code (for mobile verification)',
                example='+1234567890'
            ),
            'otp_for': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Purpose of OTP',
                example='email_verification',
                enum=['email_verification', 'mobile_verification', 'password_reset']
            ),
            'delivery_method': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='OTP delivery method (for password reset)',
                example='email',
                enum=['email', 'whatsapp']
            )
        },
        required=['otp_for']
    ),
    responses={
        200: openapi.Response(
            description="OTP resent successfully",
            examples={
                "application/json": {
                    "message": "OTP resent successfully"
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid email/mobile or rate limit exceeded")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resend_otp(request):
    """
    Resend OTP for email or mobile verification.
    """
    serializer = ResendOTPSerializer(data=request.data)
    
    if serializer.is_valid():
        email = serializer.validated_data.get('email')
        mobile_number = serializer.validated_data.get('mobile_number')
        otp_for = serializer.validated_data['otp_for']
        
        if email:
            # Check if email exists in Email model (for additional emails)
            try:
                email_obj = Email.objects.get(email__iexact=email, created_by=request.user)
                user = request.user
            except Email.DoesNotExist:
                # Fallback to User model (for primary email)
                if request.user.email.lower() == email.lower():
                    user = request.user
                else:
                    return Response({
                        'error': 'Email address not found or does not belong to you'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate and send OTP
            otp = generate_otp()
            expires_at = timezone.now() + timedelta(minutes=10)
            
            OTP.objects.create(
                otp=otp,
                otp_type='E',
                otp_for=otp_for,
                expires_at=expires_at,
                created_by=user
            )
            
            send_otp_email(email, otp, otp_for.replace('_', ' ').title())
            
            return Response({
                'message': f'OTP sent to {email}'
            }, status=status.HTTP_200_OK)
        
        elif mobile_number:
            try:
                # Security: Only allow users to resend OTP for their own mobile numbers
                mobile_obj = MobileNumber.objects.get(mobile_number=mobile_number, created_by=request.user)
            except MobileNumber.DoesNotExist:
                return Response({
                    'error': 'Mobile number not found or does not belong to you'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if mobile is verified for password reset
            if otp_for == 'password_reset' and not mobile_obj.is_verified:
                return Response({
                    'error': 'Mobile number must be verified to receive password reset OTP via WhatsApp. Please use email instead.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate and send OTP
            otp = generate_otp()
            expires_at = timezone.now() + timedelta(minutes=10)
            
            OTP.objects.create(
                otp=otp,
                otp_type='M',
                otp_for=otp_for,
                expires_at=expires_at,
                created_by=request.user
            )
            
            # Send OTP via WhatsApp
            if otp_for == 'password_reset':
                send_otp_sms(mobile_number, otp, "Password Reset")
            else:
                send_otp_sms(mobile_number, otp, "Mobile Verification")
            
            return Response({
                'message': f'OTP sent to {mobile_number}'
            }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_summary="Get User Profile",
    operation_description="Get current user's profile information.",
    responses={
        200: openapi.Response(
            description="User profile retrieved successfully",
            examples={
                "application/json": {
                    "id": 1,
                    "username": "john.doe",
                    "email": "john.doe@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                    "is_active": True,
                    "date_joined": "2024-01-01T00:00:00Z"
                }
            }
        ),
        401: openapi.Response(description="Unauthorized - authentication required")
    },
    tags=['Authentication']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Get user profile information.
    """
    from Profiles.models import DesignerProfile
    from MediaFiles.models import Media, Relation
    
    serializer = UserProfileSerializer(request.user)
    data = serializer.data.copy()
    
    # Get designer profile for bio, date_of_birth, and profile photo
    try:
        designer_profile = DesignerProfile.objects.get(created_by=request.user)
        data['bio'] = designer_profile.bio
        data['date_of_birth'] = designer_profile.date_of_birth
        
        # Get profile photo URL
        profile_photo_url = None
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
        
        data['profile_photo_url'] = profile_photo_url
    except DesignerProfile.DoesNotExist:
        pass
    
    return Response(data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='put',
    operation_summary="Update User Profile",
    operation_description="Update current user's profile information.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'first_name': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='User first name',
                example='John'
            ),
            'last_name': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='User last name',
                example='Doe'
            ),
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='User email address',
                example='john.doe@example.com'
            )
        }
    ),
    responses={
        200: openapi.Response(
            description="Profile updated successfully",
            examples={
                "application/json": {
                    "message": "Profile updated successfully",
                    "user": {
                        "id": 1,
                        "username": "john.doe",
                        "email": "john.doe@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "is_active": True
                    }
                }
            }
        ),
        400: openapi.Response(description="Bad request - validation errors"),
        401: openapi.Response(description="Unauthorized - authentication required")
    },
    tags=['Authentication']
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """
    Update user profile information.
    """
    from Profiles.models import DesignerProfile
    from Authentication.user_relations import get_user_mobile_numbers
    
    # Extract mobile_number, bio, and date_of_birth from request data
    data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
    mobile_number = data.pop('mobile_number', None)
    bio = data.pop('bio', None)
    date_of_birth = data.pop('date_of_birth', None)
    
    # Update basic user profile
    serializer = UserProfileSerializer(request.user, data=data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        
        # Update mobile number if provided
        if mobile_number:
            mobile_numbers = get_user_mobile_numbers(request.user)
            primary_mobile = mobile_numbers.filter(is_primary=True).first()
            
            if primary_mobile:
                # Update existing primary mobile number
                primary_mobile.mobile_number = mobile_number
                primary_mobile.updated_by = request.user
                primary_mobile.save()
            else:
                # Create new primary mobile number
                MobileNumber.objects.create(
                    mobile_number=mobile_number,
                    is_primary=True,
                    created_by=request.user,
                    updated_by=request.user
                )
        
        # Update designer profile bio and date_of_birth if provided
        if bio is not None or date_of_birth is not None:
            try:
                designer_profile = DesignerProfile.objects.get(created_by=request.user)
                if bio is not None:
                    designer_profile.bio = bio
                if date_of_birth is not None:
                    designer_profile.date_of_birth = date_of_birth
                designer_profile.updated_by = request.user
                designer_profile.save()
            except DesignerProfile.DoesNotExist:
                # Create designer profile if it doesn't exist
                DesignerProfile.objects.create(
                    bio=bio if bio is not None else '',
                    date_of_birth=date_of_birth if date_of_birth is not None else None,
                    created_by=request.user,
                    updated_by=request.user
                )
        
        return Response({
            'message': 'Profile updated successfully',
            'user': serializer.data
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary="Upload Profile Photo",
    operation_description="Upload a profile photo for the user.",
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
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_photo(request):
    """
    Upload profile photo for the user.
    """
    from Profiles.models import DesignerProfile
    from MediaFiles.models import Media
    from common.relations import attach_relation
    
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
        # Get or create designer profile
        try:
            designer_profile = DesignerProfile.objects.get(created_by=request.user)
        except DesignerProfile.DoesNotExist:
            designer_profile = DesignerProfile.objects.create(
                created_by=request.user,
                updated_by=request.user
            )
        
        # Remove old profile photo if exists
        from MediaFiles.models import Relation
        old_relations = Relation.objects.filter(
            relation_type='DesignerProfile:Media',
            id_1=designer_profile.pk
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
        attach_relation('DesignerProfile:Media', designer_profile, profile_photo, 
                      meta={'type': 'profile_photo'}, created_by=request.user)
        
        # Build profile photo URL
        profile_photo_url = None
        if hasattr(profile_photo.file, 'url'):
            relative_url = profile_photo.file.url
            if relative_url.startswith('/'):
                profile_photo_url = request.build_absolute_uri(relative_url)
            elif relative_url.startswith('http'):
                profile_photo_url = relative_url
            else:
                profile_photo_url = request.build_absolute_uri('/' + relative_url)
        
        return Response({
            'message': 'Profile photo uploaded successfully',
            'profile_photo_url': profile_photo_url
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'error': f'Failed to upload profile photo: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_summary="Change Password",
    operation_description="Change user password by providing old and new password.",
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
        200: openapi.Response(
            description="Password changed successfully",
            examples={
                "application/json": {
                    "message": "Password changed successfully"
                }
            }
        ),
        400: openapi.Response(description="Bad request - old password incorrect or validation errors"),
        401: openapi.Response(description="Unauthorized - authentication required")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password.
    """
    serializer = ChangePasswordSerializer(data=request.data)
    
    if serializer.is_valid():
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']
        
        # Verify old password
        if not request.user.check_password(old_password):
            return Response({
                'error': 'Old password is incorrect'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update password
        request.user.set_password(new_password)
        request.user.save()
        
        return Response({
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary="Refresh Token",
    operation_description="Refresh JWT access token using refresh token.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'refresh_token': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='JWT refresh token',
                example='eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...'
            )
        },
        required=['refresh_token']
    ),
    responses={
        200: openapi.Response(
            description="Token refreshed successfully",
            examples={
                "application/json": {
                    "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid refresh token")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """
    Refresh JWT access token.
    """
    try:
        refresh_token = request.data.get('refresh_token')
        if not refresh_token:
            return Response({
                'error': 'Refresh token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        token = RefreshToken(refresh_token)
        new_access_token = token.access_token
        
        return Response({
            'access': str(new_access_token),
            'refresh': str(token)
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'Invalid refresh token'
        }, status=status.HTTP_400_BAD_REQUEST)


# Email Management Endpoints
@swagger_auto_schema(
    method='post',
    operation_summary="Add Email Address",
    operation_description="Add a new email address to user account.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='Email address to add',
                example='newemail@example.com'
            ),
            'is_primary': openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description='Set as primary email address',
                example=False
            )
        },
        required=['email']
    ),
    responses={
        201: openapi.Response(
            description="Email address added successfully",
            examples={
                "application/json": {
                    "message": "Email address added successfully",
                    "email": {
                        "id": 1,
                        "email": "newemail@example.com",
                        "is_verified": False,
                        "is_primary": False,
                        "created_at": "2024-01-01T00:00:00Z"
                    }
                }
            }
        ),
        400: openapi.Response(description="Bad request - email already exists or validation errors"),
        401: openapi.Response(description="Unauthorized - authentication required")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_email_address(request):
    """
    Add a new email address to user account and send OTP for verification.
    """
    from .serializers import AddEmailAddressSerializer
    
    serializer = AddEmailAddressSerializer(data=request.data, context={'user': request.user})
    
    if serializer.is_valid():
        email_obj = serializer.save()
        
        # If this is set as primary, update Django User.email
        if email_obj.is_primary:
            request.user.email = email_obj.email
            request.user.save()
        
        # Generate and send OTP for email verification
        otp = generate_otp()
        expires_at = timezone.now() + timedelta(minutes=10)
        
        OTP.objects.create(
            otp=otp,
            otp_type='E',
            otp_for='email_verification',
            expires_at=expires_at,
            created_by=request.user
        )
        
        # Send OTP email
        send_otp_email(email_obj.email, otp, "Email Verification")
        
        return Response({
            'message': 'Email address added successfully. OTP sent for verification.',
            'email': {
                'id': email_obj.id,
                'email': email_obj.email,
                'is_verified': email_obj.is_verified,
                'is_primary': email_obj.is_primary,
                'created_at': email_obj.created_at
            }
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_summary="List Email Addresses",
    operation_description="Get all email addresses for the authenticated user.",
    responses={
        200: openapi.Response(
            description="Email addresses retrieved successfully",
            examples={
                "application/json": {
                    "emails": [
                        {
                            "id": 1,
                            "email": "primary@example.com",
                            "is_verified": True,
                            "is_primary": True,
                            "created_at": "2024-01-01T00:00:00Z"
                        },
                        {
                            "id": 2,
                            "email": "secondary@example.com",
                            "is_verified": False,
                            "is_primary": False,
                            "created_at": "2024-01-02T00:00:00Z"
                        }
                    ]
                }
            }
        ),
        401: openapi.Response(description="Unauthorized - authentication required")
    },
    tags=['Authentication']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_email_addresses(request):
    """
    Get all email addresses for the authenticated user.
    """
    emails = Email.objects.filter(created_by=request.user).order_by('-is_primary', '-created_at')
    serializer = EmailListSerializer(emails, many=True)
    
    return Response({
        'emails': serializer.data
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='put',
    operation_summary="Update Email Address",
    operation_description="Update email address details.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'is_primary': openapi.Schema(
                type=openapi.TYPE_BOOLEAN,
                description='Set as primary email address',
                example=True
            )
        }
    ),
    responses={
        200: openapi.Response(
            description="Email address updated successfully",
            examples={
                "application/json": {
                    "message": "Email address updated successfully",
                    "email": {
                        "id": 1,
                        "email": "updated@example.com",
                        "is_verified": True,
                        "is_primary": True,
                        "created_at": "2024-01-01T00:00:00Z"
                    }
                }
            }
        ),
        400: openapi.Response(description="Bad request - validation errors"),
        401: openapi.Response(description="Unauthorized - authentication required"),
        404: openapi.Response(description="Email address not found")
    },
    tags=['Authentication']
)
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_email_address(request, email_id):
    """
    Update email address details.
    """
    try:
        email_obj = Email.objects.get(id=email_id, created_by=request.user)
    except Email.DoesNotExist:
        return Response({
            'error': 'Email address not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    try:
        # Manually update fields to avoid serializer issues
        is_primary = request.data.get('is_primary', False)
        is_verified = request.data.get('is_verified')
        
        # Before saving, if setting as primary, unset other primary emails
        if is_primary:
            Email.objects.filter(
                created_by=request.user,
                is_primary=True
            ).exclude(id=email_id).update(is_primary=False)
            email_obj.is_primary = True
        
        # Update is_verified if provided
        if is_verified is not None:
            email_obj.is_verified = is_verified
        
        # Update updated_by field
        email_obj.updated_by = request.user
        email_obj.save()
        
        # If this is set as primary, update Django User.email
        if email_obj.is_primary:
            request.user.email = email_obj.email
            request.user.save()
        
        return Response({
            'message': 'Email address updated successfully',
            'email': {
                'id': email_obj.id,
                'email': email_obj.email,
                'is_verified': email_obj.is_verified,
                'is_primary': email_obj.is_primary,
                'created_at': email_obj.created_at
            }
        }, status=status.HTTP_200_OK)
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating email address: {str(e)}\n{traceback.format_exc()}")
        return Response({
            'error': f'An error occurred while updating email address: {str(e)}',
            'detail': traceback.format_exc() if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='delete',
    operation_summary="Delete Email Address",
    operation_description="Delete an email address from user account.",
    responses={
        200: openapi.Response(
            description="Email address deleted successfully",
            examples={
                "application/json": {
                    "message": "Email address deleted successfully"
                }
            }
        ),
        400: openapi.Response(description="Bad request - cannot delete primary or only email"),
        401: openapi.Response(description="Unauthorized - authentication required"),
        404: openapi.Response(description="Email address not found")
    },
    tags=['Authentication']
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_email_address(request, email_id):
    """
    Delete an email address from user account.
    Ensures at least one verified email remains.
    """
    try:
        email_obj = Email.objects.get(id=email_id, created_by=request.user)
    except Email.DoesNotExist:
        return Response({
            'error': 'Email address not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if this is the only email
    total_emails = Email.objects.filter(created_by=request.user).count()
    if total_emails <= 1:
        return Response({
            'error': 'Cannot delete the only email address'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if this is the primary email
    if email_obj.is_primary:
        return Response({
            'error': 'Cannot delete primary email. Set another email as primary first.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if this is verified and if it's the only verified email
    if email_obj.is_verified:
        verified_emails_count = Email.objects.filter(
            created_by=request.user,
            is_verified=True
        ).count()
        if verified_emails_count <= 1:
            return Response({
                'error': 'Cannot delete the only verified email address. At least one verified email must remain.'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    email_obj.delete()
    
    return Response({
        'message': 'Email address deleted successfully'
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    operation_summary="Verify Email Address",
    operation_description="Verify an email address with OTP.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'email': openapi.Schema(
                type=openapi.TYPE_STRING,
                format=openapi.FORMAT_EMAIL,
                description='Email address to verify',
                example='newemail@example.com'
            ),
            'otp': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='6-digit OTP received via email',
                example='123456'
            )
        },
        required=['email', 'otp']
    ),
    responses={
        200: openapi.Response(
            description="Email address verified successfully",
            examples={
                "application/json": {
                    "message": "Email address verified successfully"
                }
            }
        ),
        400: openapi.Response(description="Bad request - invalid OTP or email"),
        401: openapi.Response(description="Unauthorized - authentication required")
    },
    tags=['Authentication']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_email_address(request):
    """
    Verify an email address using OTP.
    """
    from .serializers import EmailAddressVerificationSerializer
    
    serializer = EmailAddressVerificationSerializer(data=request.data, context={'user': request.user})
    
    if serializer.is_valid():
        email_obj = serializer.validated_data['email_obj']
        otp_obj = serializer.validated_data['otp_obj']
        
        # Delete OTP record after successful verification
        otp_obj.delete()
        
        # Mark email as verified
        email_obj.is_verified = True
        email_obj.save()
        
        return Response({
            'message': 'Email address verified successfully'
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==================== CUSTOMER NOTIFICATIONS ====================

@swagger_auto_schema(
    method='get',
    operation_summary='Get Customer Notifications',
    operation_description='Get customer notifications with filtering and pagination.',
    manual_parameters=[
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by status: unread, read, or all',
            type=openapi.TYPE_STRING,
            enum=['unread', 'read', 'all'],
            default='all'
        ),
        openapi.Parameter(
            'type',
            openapi.IN_QUERY,
            description='Filter by notification type',
            type=openapi.TYPE_STRING,
            required=False
        ),
        openapi.Parameter(
            'page',
            openapi.IN_QUERY,
            description='Page number',
            type=openapi.TYPE_INTEGER,
            default=1
        ),
        openapi.Parameter(
            'limit',
            openapi.IN_QUERY,
            description='Number of notifications per page',
            type=openapi.TYPE_INTEGER,
            default=20
        ),
    ],
    responses={
        200: openapi.Response(description='Notifications retrieved successfully'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Customer Notifications']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_notifications(request):
    """
    Get customer notifications with filtering and pagination.
    """
    try:
        from CoreAdmin.models import CustomerNotification
        from django.core.paginator import Paginator
        
        # Get query parameters
        status_filter = request.GET.get('status', 'all')  # 'unread', 'read', 'all'
        notification_type = request.GET.get('type')
        try:
            page = int(request.GET.get('page', 1))
        except (ValueError, TypeError):
            page = 1
        try:
            limit = int(request.GET.get('limit', 20))
        except (ValueError, TypeError):
            limit = 20
        
        # Get customer notifications for the authenticated user
        import logging
        logger = logging.getLogger(__name__)
        
        # SECURITY: Always filter by the authenticated user's ID to ensure users can only see their own notifications
        user_id = request.user.id
        logger.info(f"🔔 [NOTIFICATIONS] 🔍 Querying for user ID: {user_id}, Email: {request.user.email}, Username: {request.user.username}")
        
        # Query by customer_id - SECURITY: Only return notifications for the logged-in user
        notifications = CustomerNotification.objects.filter(customer_id=user_id)
        
        # Additional security check: Verify user is authenticated
        if not request.user.is_authenticated:
            logger.error(f"🚨 [NOTIFICATIONS] ⚠️ SECURITY: Unauthenticated request!")
            return Response({
                'error': 'Authentication required'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Log initial query result
        total_before_filters = notifications.count()
        logger.info(f"🔔 [NOTIFICATIONS] ✅ Found: {total_before_filters} notifications for user ID {request.user.id}")
        
        # Debug: Log notification details to verify customer_id matches
        if total_before_filters > 0:
            notification_details = list(notifications.values('id', 'customer_id', 'title')[:10])
            logger.info(f"🔔 [NOTIFICATIONS] 📋 Notification details (first 10): {notification_details}")
            
            # Verify each notification belongs to the current user
            for notif_detail in notification_details:
                if notif_detail['customer_id'] != request.user.id:
                    logger.error(f"🚨 [NOTIFICATIONS] ⚠️ SECURITY ISSUE: Notification {notif_detail['id']} has customer_id={notif_detail['customer_id']} but query was for user_id={request.user.id}")
                else:
                    logger.info(f"🔔 [NOTIFICATIONS] ✓ Notification {notif_detail['id']} correctly belongs to user {request.user.id}")
        
        # Apply status filter
        if status_filter == 'unread':
            notifications = notifications.filter(is_read=False)
        elif status_filter == 'read':
            notifications = notifications.filter(is_read=True)
        
        # Apply type filter
        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)
        
        # Order by created_at descending
        notifications = notifications.order_by('-created_at')
        
        # Paginate
        paginator = Paginator(notifications, limit)
        page_obj = paginator.get_page(page)
        
        # Serialize notifications
        serializer = CustomerNotificationSerializer(page_obj.object_list, many=True)
        
        # Log serialized data count and details
        serialized_count = len(serializer.data)
        logger.info(f"🔔 [SERIALIZE] Serialized {serialized_count} notifications for response")
        
        if serialized_count > 0:
            first_notif = serializer.data[0]
            logger.info(f"🔔 [SERIALIZE] First notification - ID: {first_notif.get('id')}, Title: {first_notif.get('title')}, Customer ID: {first_notif.get('customer_id')}, Customer Name: {first_notif.get('customer_name')}, Request User ID: {request.user.id}, Request User Email: {request.user.email}")
            
            # Check if customer_id matches logged-in user
            if first_notif.get('customer_id') != request.user.id:
                logger.error(f"🚨 [SERIALIZE] ⚠️ SECURITY ISSUE: Notification customer_id={first_notif.get('customer_id')} does NOT match logged-in user_id={request.user.id}")
            
            # Log all notifications customer IDs
            all_customer_ids = [n.get('customer_id') for n in serializer.data]
            logger.info(f"🔔 [SERIALIZE] All customer IDs in response: {set(all_customer_ids)}")
            
            # Log full first notification for debugging
            import json
            logger.info(f"🔔 [SERIALIZE] First notification full data: {json.dumps(first_notif, default=str)}")
        else:
            logger.warning(f"🔔 [SERIALIZE] No notifications to serialize! Query returned {page_obj.object_list.count()} objects")
            
            # Debug: Check what the queryset contains
            all_notifications = list(notifications.values('id', 'customer_id', 'title', 'is_read')[:5])
            logger.info(f"🔔 [DEBUG] Sample notifications from queryset: {all_notifications}")
        
        # Get unread count - simple direct query
        unread_count = CustomerNotification.objects.filter(customer_id=request.user.id, is_read=False).count()
        
        logger.info(f"🔔 Unread count: {unread_count}")
        
        return Response({
            'notifications': serializer.data,
            'unread_count': unread_count,
            'total_count': paginator.count,
            'page': page,
            'pages': paginator.num_pages,
            'filters_applied': {
                'status': status_filter,
                'type': notification_type
            }
        })
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f'Error in customer_notifications: {e}')
        logger.error(traceback.format_exc())
        return Response({
            'error': 'An error occurred while retrieving notifications',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_summary='Get Customer Notification Count',
    operation_description='Get unread notification count for the customer.',
    responses={
        200: openapi.Response(description='Notification count retrieved successfully'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Customer Notifications']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def customer_notification_count(request):
    """
    Get unread notification count for the customer.
    """
    try:
        from CoreAdmin.models import CustomerNotification
        import logging
        logger = logging.getLogger(__name__)
        
        # Get unread count - simple direct query by customer_id
        unread_count = CustomerNotification.objects.filter(customer_id=request.user.id, is_read=False).count()
        
        logger.info(f"🔔 [NOTIFICATION COUNT] User: {request.user.id} | Unread count: {unread_count}")
        
        return Response({
            'unread_count': unread_count
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error in customer_notification_count: {e}')
        return Response({
            'error': 'An error occurred while retrieving notification count',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_summary='Mark Customer Notification as Read',
    operation_description='Mark a specific customer notification as read.',
    responses={
        200: openapi.Response(description='Notification marked as read'),
        404: openapi.Response(description='Notification not found'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Customer Notifications']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_customer_notification_read(request, notification_id):
    """
    Mark a specific customer notification as read.
    """
    try:
        from CoreAdmin.models import CustomerNotification
        
        notification = CustomerNotification.objects.get(
            id=notification_id,
            customer_id=request.user.id
        )
        
        if not notification.is_read:
            notification.mark_as_read()
        
        return Response({
            'message': 'Notification marked as read'
        })
    except CustomerNotification.DoesNotExist:
        return Response({
            'error': 'Notification not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error in mark_customer_notification_read: {e}')
        return Response({
            'error': 'An error occurred while marking notification as read',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_summary='Mark All Customer Notifications as Read',
    operation_description='Mark all customer notifications as read.',
    responses={
        200: openapi.Response(description='All notifications marked as read'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Customer Notifications']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_customer_notifications_read(request):
    """
    Mark all customer notifications as read.
    """
    try:
        from CoreAdmin.models import CustomerNotification
        
        updated_count = CustomerNotification.objects.filter(
            customer_id=request.user.id,
            is_read=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return Response({
            'message': 'All notifications marked as read',
            'updated_count': updated_count
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'Error in mark_all_customer_notifications_read: {e}')
        return Response({
            'error': 'An error occurred while marking all notifications as read',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
