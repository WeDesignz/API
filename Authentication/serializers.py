from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
import random
import string
from .models import Email, MobileNumber, OTP


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for Django User model with basic user information.
    Used for nested serialization in other models.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class EmailSerializer(serializers.ModelSerializer):
    """
    Serializer for Email model with full CRUD operations.
    Handles email verification and primary status management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Email
        fields = [
            'id', 'email', 'is_verified', 'is_primary', 
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'email', 'created_at', 'updated_at']
    
    def validate_email(self, value):
        """
        Validate email format and uniqueness.
        """
        if Email.objects.filter(email=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Email already exists.")
        return value
    
    def validate(self, attrs):
        """
        Validate that only one email can be primary per user.
        """
        if attrs.get('is_primary', False):
            # Get user from context or instance
            user = self.context.get('user')
            if not user and self.instance:
                user = self.instance.created_by
            
            # Also check created_by_id from attrs
            created_by_id = attrs.get('created_by_id')
            if not user and created_by_id:
                from django.contrib.auth.models import User
                try:
                    user = User.objects.get(id=created_by_id)
                except User.DoesNotExist:
                    pass
            
            if user:
                # Unset other primary emails for this user
                # This is handled in the view, but we do it here too for safety
                Email.objects.filter(
                    created_by=user, 
                    is_primary=True
                ).exclude(pk=self.instance.pk if self.instance else None).update(is_primary=False)
            elif not self.instance:
                # If no user and no instance, we can't proceed
                raise serializers.ValidationError("User context is required to set primary email.")
        return attrs


class EmailListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Email model used in list views.
    """
    class Meta:
        model = Email
        fields = ['id', 'email', 'is_verified', 'is_primary', 'created_at']


class MobileNumberSerializer(serializers.ModelSerializer):
    """
    Serializer for MobileNumber model with full CRUD operations.
    Handles mobile number verification and primary status management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = MobileNumber
        fields = [
            'id', 'mobile_number', 'is_verified', 'is_primary',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_mobile_number(self, value):
        """
        Validate mobile number format and uniqueness.
        """
        if MobileNumber.objects.filter(mobile_number=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Mobile number already exists.")
        return value
    
    def validate(self, attrs):
        """
        Validate that only one mobile number can be primary per user.
        """
        if attrs.get('is_primary', False):
            created_by_id = attrs.get('created_by_id') or self.context.get('user_id')
            if created_by_id:
                MobileNumber.objects.filter(
                    created_by_id=created_by_id, 
                    is_primary=True
                ).exclude(pk=self.instance.pk if self.instance else None).update(is_primary=False)
        return attrs


class MobileNumberListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for MobileNumber model used in list views.
    """
    class Meta:
        model = MobileNumber
        fields = ['id', 'mobile_number', 'is_verified', 'is_primary', 'created_at']


class OTPSerializer(serializers.ModelSerializer):
    """
    Serializer for OTP model with full CRUD operations.
    Handles OTP generation, verification, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = OTP
        fields = [
            'id', 'otp', 'otp_type', 'otp_for', 'is_verified',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_otp(self, value):
        """
        Validate OTP format (numeric, 4-6 digits).
        """
        if not value.isdigit() or len(value) < 4 or len(value) > 6:
            raise serializers.ValidationError("OTP must be 4-6 digits.")
        return value


class OTPListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for OTP model used in list views.
    """
    class Meta:
        model = OTP
        fields = ['id', 'otp_type', 'otp_for', 'is_verified', 'created_at']


class OTPVerificationSerializer(serializers.Serializer):
    """
    Serializer for OTP verification process.
    """
    otp = serializers.CharField(max_length=10)
    otp_type = serializers.ChoiceField(choices=OTP.OTP_TYPE_CHOICES)
    otp_for = serializers.ChoiceField(choices=OTP.OTP_FOR_CHOICES)
    
    def validate(self, attrs):
        """
        Validate OTP exists and is not expired.
        """
        otp = attrs.get('otp')
        otp_type = attrs.get('otp_type')
        otp_for = attrs.get('otp_for')
        
        try:
            otp_obj = OTP.objects.get(
                otp=otp,
                otp_type=otp_type,
                otp_for=otp_for,
                is_verified=False
            )
            # Check if OTP is not expired (assuming 10 minutes validity)
            from django.utils import timezone
            from datetime import timedelta
            if otp_obj.created_at < timezone.now() - timedelta(minutes=10):
                raise serializers.ValidationError("OTP has expired.")
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")
        
        attrs['otp_obj'] = otp_obj
        return attrs


# Authentication Serializers
class SignupSerializer(serializers.Serializer):
    """
    Serializer for user registration without email/mobile verification.
    Verification will be done during designer onboarding.
    """
    first_name = serializers.CharField(max_length=30, required=True)
    last_name = serializers.CharField(max_length=30, required=True)
    email = serializers.EmailField(required=True)
    mobile_number = serializers.CharField(max_length=15, required=True)
    password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value
    
    def validate_mobile_number(self, value):
        """Validate mobile number uniqueness"""
        if MobileNumber.objects.filter(mobile_number=value).exists():
            raise serializers.ValidationError("Mobile number already exists.")
        return value
    
    def validate(self, attrs):
        """Validate password confirmation"""
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        
        if password != confirm_password:
            raise serializers.ValidationError("Passwords don't match.")
        
        # Validate password strength
        try:
            validate_password(password)
        except ValidationError as e:
            raise serializers.ValidationError({'password': e.messages})
        
        return attrs


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login with username/email/mobile + password.
    """
    username = serializers.CharField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    remember_me = serializers.BooleanField(required=False, default=False)
    
    def validate(self, attrs):
        """Validate user credentials"""
        username = attrs.get('username')
        password = attrs.get('password')
        
        # Try to authenticate with username/email/mobile
        user = None
        
        # First try with username (could be actual username or email left part)
        user = authenticate(username=username, password=password)
        
        # If not found, try with email
        if not user:
            try:
                user_obj = User.objects.get(email=username)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        # If still not found, try with mobile number
        if not user:
            try:
                mobile_obj = MobileNumber.objects.get(mobile_number=username, is_verified=True)
                user = authenticate(username=mobile_obj.created_by.username, password=password)
            except MobileNumber.DoesNotExist:
                pass
        
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        
        if not user.is_active:
            raise serializers.ValidationError("Account is deactivated.")
        
        attrs['user'] = user
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """
    Serializer for email verification with OTP.
    """
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=10, required=True)
    
    def validate(self, attrs):
        """Validate email and OTP"""
        email = attrs.get('email')
        otp = attrs.get('otp')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        
        # DUMMY MODE: Accept sample OTP 123456 for now
        if otp == '123456' and len(otp) == 6:
            attrs['user'] = user
            attrs['otp_obj'] = None  # No OTP object needed in dummy mode
            return attrs
        
        try:
            otp_obj = OTP.objects.get(
                otp=otp,
                otp_type='E',
                otp_for='email_verification',
                created_by=user,
                is_verified=False
            )
            
            if otp_obj.is_expired():
                raise serializers.ValidationError("OTP has expired.")
                
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")
        
        attrs['user'] = user
        attrs['otp_obj'] = otp_obj
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer for password reset request.
    """
    email = serializers.EmailField(required=True)
    
    def validate_email(self, value):
        """Validate email exists and is verified"""
        try:
            user = User.objects.get(email=value)
            # Check if email is verified
            email_obj = Email.objects.get(email=value, created_by=user, is_verified=True)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        except Email.DoesNotExist:
            raise serializers.ValidationError("Email is not verified.")
        
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer for password reset confirmation with OTP.
    """
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=10, required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)
    
    def validate(self, attrs):
        """Validate OTP and password"""
        email = attrs.get('email')
        otp = attrs.get('otp')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError("Passwords don't match.")
        
        # Validate password strength
        try:
            validate_password(new_password)
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': e.messages})
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        
        try:
            otp_obj = OTP.objects.get(
                otp=otp,
                otp_type='E',
                otp_for='password_reset',
                created_by=user,
                is_verified=False
            )
            
            if otp_obj.is_expired():
                raise serializers.ValidationError("OTP has expired.")
                
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")
        
        attrs['user'] = user
        attrs['otp_obj'] = otp_obj
        return attrs


class MobileVerificationSerializer(serializers.Serializer):
    """
    Serializer for mobile number verification with OTP.
    """
    mobile_number = serializers.CharField(max_length=15, required=True)
    otp = serializers.CharField(max_length=10, required=True)
    
    def validate(self, attrs):
        """Validate mobile number and OTP"""
        mobile_number = attrs.get('mobile_number')
        otp = attrs.get('otp')
        
        try:
            mobile_obj = MobileNumber.objects.get(mobile_number=mobile_number)
        except MobileNumber.DoesNotExist:
            raise serializers.ValidationError("Mobile number not found.")
        
        # DUMMY MODE: Accept sample OTP 123456 for now
        if otp == '123456' and len(otp) == 6:
            attrs['mobile_obj'] = mobile_obj
            attrs['otp_obj'] = None  # No OTP object needed in dummy mode
            return attrs
        
        try:
            otp_obj = OTP.objects.get(
                otp=otp,
                otp_type='M',
                otp_for='mobile_verification',
                created_by=mobile_obj.created_by,
                is_verified=False
            )
            
            if otp_obj.is_expired():
                raise serializers.ValidationError("OTP has expired.")
                
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")
        
        attrs['mobile_obj'] = mobile_obj
        attrs['otp_obj'] = otp_obj
        return attrs


class AddMobileNumberSerializer(serializers.Serializer):
    """
    Serializer for adding mobile number to user account.
    """
    mobile_number = serializers.CharField(max_length=15, required=True)
    
    def validate_mobile_number(self, value):
        """Validate mobile number format and uniqueness per user"""
        # Remove any non-digit characters for validation
        digits_only = ''.join(filter(str.isdigit, value))
        
        # Check if it's a 10-digit number (without country code)
        if len(digits_only) != 10:
            raise serializers.ValidationError("Mobile number must be exactly 10 digits.")
        
        # Check uniqueness per user (get user from context)
        request = self.context.get('request') if self.context else None
        user = request.user if request and hasattr(request, 'user') else None
        if user:
            if MobileNumber.objects.filter(mobile_number=value, created_by=user).exists():
                raise serializers.ValidationError("This mobile number is already associated with your account.")
        else:
            # Fallback: check global uniqueness if no user context
            if MobileNumber.objects.filter(mobile_number=value).exists():
                raise serializers.ValidationError("Mobile number already exists.")
        return value


class ResendOTPSerializer(serializers.Serializer):
    """
    Serializer for resending OTP.
    """
    email = serializers.EmailField(required=False)
    mobile_number = serializers.CharField(max_length=15, required=False)
    otp_for = serializers.ChoiceField(choices=[
        ('email_verification', 'Email Verification'),
        ('password_reset', 'Password Reset'),
        ('mobile_verification', 'Mobile Verification'),
    ], required=True)
    
    def validate(self, attrs):
        """Validate that either email or mobile is provided"""
        email = attrs.get('email')
        mobile_number = attrs.get('mobile_number')
        
        if not email and not mobile_number:
            raise serializers.ValidationError("Either email or mobile number is required.")
        
        if email and mobile_number:
            raise serializers.ValidationError("Provide either email or mobile number, not both.")
        
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile information.
    """
    emails = EmailListSerializer(source='created_emails', many=True, read_only=True)
    mobile_numbers = MobileNumberListSerializer(source='created_mobile_numbers', many=True, read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name', 'email', 
            'is_active', 'date_joined', 'emails', 'mobile_numbers'
        ]
        read_only_fields = ['id', 'username', 'date_joined']


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for changing password.
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)
    
    def validate(self, attrs):
        """Validate password change"""
        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError("New passwords don't match.")
        
        # Validate new password strength
        try:
            validate_password(new_password)
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': e.messages})
        
        return attrs


# Email Management Serializers
class AddEmailAddressSerializer(serializers.Serializer):
    """
    Serializer for adding email address to user account.
    """
    email = serializers.EmailField(required=True)
    is_primary = serializers.BooleanField(default=False)
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if Email.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value
    
    def validate(self, attrs):
        """Validate primary email logic"""
        is_primary = attrs.get('is_primary', False)
        user = self.context.get('user')
        
        if is_primary and user:
            # If setting as primary, unset other primary emails
            Email.objects.filter(created_by=user, is_primary=True).update(is_primary=False)
        
        return attrs
    
    def save(self):
        """Save email address"""
        user = self.context.get('user')
        email = self.validated_data['email']
        is_primary = self.validated_data['is_primary']
        
        email_obj = Email.objects.create(
            email=email,
            is_primary=is_primary,
            created_by=user
        )
        
        return email_obj


class EmailAddressVerificationSerializer(serializers.Serializer):
    """
    Serializer for verifying email address with OTP.
    """
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(max_length=10, required=True)
    
    def validate(self, attrs):
        """Validate email and OTP"""
        email = attrs.get('email')
        otp = attrs.get('otp')
        user = self.context.get('user')
        
        try:
            email_obj = Email.objects.get(email=email, created_by=user)
        except Email.DoesNotExist:
            raise serializers.ValidationError("Email address not found for this user.")
        
        try:
            otp_obj = OTP.objects.get(
                otp=otp,
                otp_type='E',
                otp_for='email_verification',
                created_by=user,
                is_verified=False
            )
            
            if otp_obj.is_expired():
                raise serializers.ValidationError("OTP has expired.")
                
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")
        
        attrs['email_obj'] = email_obj
        attrs['otp_obj'] = otp_obj
        return attrs
from rest_framework import serializers
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from .models import Email, MobileNumber, OTP
from CoreAdmin.models import (
    CustomerAccountStatus, CustomerViewHistory, CustomerDownloadHistory,
    CustomerNotification, AdminUserProfile
)
from Plans.models import Plan, Subscription
from Orders.models import Cart, Order, OrderTransaction
from Catalog.models import Product
from Authentication.user_relations import get_user_addresses, get_user_subscriptions
from common.relations import get_related


class CustomerListSerializer(serializers.ModelSerializer):
    """
    Serializer for customer list view with basic information.
    """
    name = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    account_status = serializers.SerializerMethodField()
    account_status_display = serializers.SerializerMethodField()
    plan_status = serializers.SerializerMethodField()
    plan_status_display = serializers.SerializerMethodField()
    total_orders = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()
    last_activity = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'name',
            'phone_number',
            'is_active', 'date_joined', 'last_login',
            'account_status', 'account_status_display', 'plan_status', 'plan_status_display',
            'total_orders', 'total_spent', 'last_activity'
        ]
        read_only_fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'name',
            'phone_number',
            'is_active', 'date_joined', 'last_login',
            'account_status', 'account_status_display', 'plan_status', 'plan_status_display',
            'total_orders', 'total_spent', 'last_activity'
        ]
    
    def get_name(self, obj):
        """Get full name"""
        if obj.first_name or obj.last_name:
            return f"{obj.first_name or ''} {obj.last_name or ''}".strip()
        return obj.username or obj.email
    
    def get_phone_number(self, obj):
        """Get primary phone number"""
        try:
            from .models import MobileNumber
            primary_mobile = MobileNumber.objects.filter(
                created_by=obj,
                is_primary=True
            ).first()
            if primary_mobile:
                return primary_mobile.mobile_number
            # Fallback to any mobile number
            any_mobile = MobileNumber.objects.filter(created_by=obj).first()
            return any_mobile.mobile_number if any_mobile else None
        except:
            return None
    
    def get_account_status(self, obj):
        """Get account status"""
        try:
            from .models import CustomerAccountStatus
            from common.relations import get_related
            
            account_statuses = get_related(obj, 'User:CustomerAccountStatus', CustomerAccountStatus)
            if account_statuses.exists():
                return account_statuses.first().status
            else:
                return 'active'
        except:
            return 'active'
    
    def get_account_status_display(self, obj):
        """Get account status display"""
        try:
            from .models import CustomerAccountStatus
            from common.relations import get_related
            
            account_statuses = get_related(obj, 'User:CustomerAccountStatus', CustomerAccountStatus)
            if account_statuses.exists():
                return account_statuses.first().get_status_display()
            else:
                return 'Active'
        except:
            return 'Active'
    
    def get_plan_status(self, obj):
        """Get current subscription plan status"""
        try:
            subscription = Subscription.objects.filter(
                created_by=obj,
                status='active'
            ).first()
            
            if subscription:
                return {
                    'status': 'active',
                    'plan_name': subscription.plan.get_plan_name_display(),
                    'plan_duration': subscription.plan.get_plan_duration_display(),
                    'expires_at': subscription.created_at + timedelta(days=30 if subscription.plan.plan_duration == 'monthly' else 365)
                }
            else:
                return {'status': 'none'}
        except:
            return {'status': 'none'}
    
    def get_plan_status_display(self, obj):
        """Get plan status as string for frontend"""
        plan_status = self.get_plan_status(obj)
        if isinstance(plan_status, dict):
            return plan_status.get('status', 'none')
        return 'none'
    
    def get_total_orders(self, obj):
        """Get total number of orders"""
        return Order.objects.filter(created_by=obj).count()
    
    def get_total_spent(self, obj):
        """Get total amount spent"""
        total = Order.objects.filter(
            created_by=obj,
            status='success'
        ).aggregate(total=Sum('total_amount'))['total']
        return float(total) if total else 0.0
    
    def get_last_activity(self, obj):
        """Get last activity timestamp"""
        # Check last login, last order, last download
        last_login = obj.last_login
        last_order = Order.objects.filter(created_by=obj).order_by('-created_at').first()
        
        # Get last download using relation system
        download_history = get_related(obj, 'User:CustomerDownloadHistory', CustomerDownloadHistory)
        last_download = download_history.order_by('-downloaded_at').first()
        
        activities = []
        if last_login:
            activities.append(last_login)
        if last_order:
            activities.append(last_order.created_at)
        if last_download:
            activities.append(last_download.downloaded_at)
        
        return max(activities) if activities else None


class CustomerDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed customer information.
    """
    account_status = serializers.SerializerMethodField()
    personal_details = serializers.SerializerMethodField()
    subscription_details = serializers.SerializerMethodField()
    purchase_summary = serializers.SerializerMethodField()
    download_summary = serializers.SerializerMethodField()
    wishlist_items = serializers.SerializerMethodField()
    cart_items = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'date_joined', 'last_login',
            'account_status', 'personal_details', 'subscription_details',
            'purchase_summary', 'download_summary', 'wishlist_items', 'cart_items'
        ]
        read_only_fields = '__all__'
    
    def get_account_status(self, obj):
        """Get account status details"""
        try:
            from .models import CustomerAccountStatus
            from common.relations import get_related
            
            account_statuses = get_related(obj, 'User:CustomerAccountStatus', CustomerAccountStatus)
            if account_statuses.exists():
                status = account_statuses.first()
                return {
                    'status': status.status,
                    'status_display': status.get_status_display(),
                    'deactivation_reason': status.deactivation_reason,
                    'deactivation_notes': status.deactivation_notes,
                    'deactivated_by': status.deactivated_by_id,
                    'deactivated_at': status.deactivated_at,
                    'reactivated_by': status.reactivated_by_id,
                    'reactivated_at': status.reactivated_at
                }
            else:
                return {
                    'status': 'active',
                    'status_display': 'Active',
                    'deactivation_reason': None,
                    'deactivation_notes': None,
                    'deactivated_by': None,
                    'deactivated_at': None,
                    'reactivated_by': None,
                    'reactivated_at': None
                }
        except:
            return {
                'status': 'active',
                'status_display': 'Active',
                'deactivation_reason': None,
                'deactivation_notes': None,
                'deactivated_by': None,
                'deactivated_at': None,
                'reactivated_by': None,
                'reactivated_at': None
            }
    
    def get_personal_details(self, obj):
        """Get personal details including addresses"""
        addresses = get_user_addresses(obj)
        return {
            'addresses': [
                {
                    'id': addr.id,
                    'address_line_1': addr.address_line_1,
                    'address_line_2': addr.address_line_2,
                    'city': addr.city,
                    'state': addr.state,
                    'pincode': addr.pincode,
                    'country': addr.country,
                    'is_permanent': addr.is_permanent,
                    'created_at': addr.created_at
                } for addr in addresses
            ]
        }
    
    def get_subscription_details(self, obj):
        """Get subscription plan details"""
        try:
            subscription = Subscription.objects.filter(
                created_by=obj,
                status='active'
            ).select_related('plan').first()
            
            if subscription:
                return {
                    'has_active_subscription': True,
                    'plan_name': subscription.plan.get_plan_name_display(),
                    'plan_duration': subscription.plan.get_plan_duration_display(),
                    'price': float(subscription.plan.price),
                    'auto_renew': subscription.auto_renew,
                    'created_at': subscription.created_at,
                    'expires_at': subscription.created_at + timedelta(
                        days=30 if subscription.plan.plan_duration == 'monthly' else 365
                    )
                }
            else:
                return {'has_active_subscription': False}
        except:
            return {'has_active_subscription': False}
    
    def get_purchase_summary(self, obj):
        """Get purchase summary"""
        orders = Order.objects.filter(created_by=obj).order_by('-created_at')
        
        return {
            'total_orders': orders.count(),
            'successful_orders': orders.filter(status='success').count(),
            'total_spent': float(orders.filter(status='success').aggregate(total=Sum('total_amount'))['total'] or 0),
            'recent_orders': [
                {
                    'id': order.id,
                    'total_amount': float(order.total_amount),
                    'status': order.status,
                    'created_at': order.created_at
                } for order in orders[:5]
            ]
        }
    
    def get_download_summary(self, obj):
        """Get download summary"""
        downloads = CustomerDownloadHistory.objects.filter(customer=obj).order_by('-downloaded_at')
        
        return {
            'total_downloads': downloads.count(),
            'recent_downloads': [
                {
                    'id': download.id,
                    'item_title': download.item_title,
                    'download_type': download.download_type,
                    'file_name': download.file_name,
                    'downloaded_at': download.downloaded_at
                } for download in downloads[:5]
            ]
        }
    
    def get_wishlist_items(self, obj):
        """Get wishlist items"""
        wishlist_items = Cart.objects.filter(
            created_by=obj,
            cart_type='wishlist'
        ).select_related('product')
        
        return [
            {
                'id': item.id,
                'product_id': item.product.id,
                'product_title': item.product.title,
                'product_price': float(item.product.price) if item.product.price else 0,
                'added_at': item.created_at
            } for item in wishlist_items
        ]
    
    def get_cart_items(self, obj):
        """Get cart items"""
        cart_items = Cart.objects.filter(
            created_by=obj,
            cart_type='cart'
        ).select_related('product')
        
        return [
            {
                'id': item.id,
                'product_id': item.product.id,
                'product_title': item.product.title,
                'product_price': float(item.product.price) if item.product.price else 0,
                'added_at': item.created_at
            } for item in cart_items
        ]


class CustomerHistorySerializer(serializers.Serializer):
    """
    Serializer for customer activity history.
    """
    view_history = serializers.SerializerMethodField()
    purchase_history = serializers.SerializerMethodField()
    download_history = serializers.SerializerMethodField()
    active_plan = serializers.SerializerMethodField()
    wishlist_items = serializers.SerializerMethodField()
    cart_items = serializers.SerializerMethodField()
    
    def get_view_history(self, obj):
        """Get view history"""
        from .models import CustomerViewHistory
        from common.relations import get_related
        
        views = get_related(obj, 'User:CustomerViewHistory', CustomerViewHistory).order_by('-viewed_at')
        return [
            {
                'id': view.id,
                'view_type': view.view_type,
                'item_title': view.item_title,
                'item_category': view.item_category,
                'viewed_at': view.viewed_at
            } for view in views
        ]
    
    def get_purchase_history(self, obj):
        """Get purchase history"""
        orders = Order.objects.filter(created_by=obj).order_by('-created_at')
        return [
            {
                'id': order.id,
                'total_amount': float(order.total_amount),
                'status': order.status,
                'created_at': order.created_at
            } for order in orders
        ]
    
    def get_download_history(self, obj):
        """Get download history"""
        downloads = get_related(obj, 'User:CustomerDownloadHistory', CustomerDownloadHistory).order_by('-downloaded_at')
        return [
            {
                'id': download.id,
                'download_type': download.download_type,
                'item_title': download.item_title,
                'file_name': download.file_name,
                'file_size': download.file_size,
                'downloaded_at': download.downloaded_at
            } for download in downloads
        ]
    
    def get_active_plan(self, obj):
        """Get active subscription plan"""
        try:
            subscription = Subscription.objects.filter(
                created_by=obj,
                status='active'
            ).select_related('plan').first()
            
            if subscription:
                return {
                    'plan_name': subscription.plan.get_plan_name_display(),
                    'plan_duration': subscription.plan.get_plan_duration_display(),
                    'price': float(subscription.plan.price),
                    'auto_renew': subscription.auto_renew,
                    'created_at': subscription.created_at,
                    'expires_at': subscription.created_at + timedelta(
                        days=30 if subscription.plan.plan_duration == 'monthly' else 365
                    )
                }
            else:
                return None
        except:
            return None
    
    def get_wishlist_items(self, obj):
        """Get wishlist items"""
        wishlist_items = Cart.objects.filter(
            created_by=obj,
            cart_type='wishlist'
        ).select_related('product')
        
        return [
            {
                'id': item.id,
                'product_id': item.product.id,
                'product_title': item.product.title,
                'product_price': float(item.product.price) if item.product.price else 0,
                'added_at': item.created_at
            } for item in wishlist_items
        ]
    
    def get_cart_items(self, obj):
        """Get cart items"""
        cart_items = Cart.objects.filter(
            created_by=obj,
            cart_type='cart'
        ).select_related('product')
        
        return [
            {
                'id': item.id,
                'product_id': item.product.id,
                'product_title': item.product.title,
                'product_price': float(item.product.price) if item.product.price else 0,
                'added_at': item.created_at
            } for item in cart_items
        ]


class CustomerAccountActionSerializer(serializers.Serializer):
    """
    Serializer for customer account actions (activate/deactivate).
    """
    action = serializers.ChoiceField(choices=[
        ('activate', 'Activate Account'),
        ('deactivate', 'Deactivate Account')
    ])
    reason = serializers.ChoiceField(choices=CustomerAccountStatus.DEACTIVATION_REASON_CHOICES, required=False)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    def validate(self, data):
        action = data.get('action')
        reason = data.get('reason')
        notes = data.get('notes', '')
        
        if action == 'deactivate' and not reason:
            raise serializers.ValidationError("Deactivation reason is required when deactivating account.")
        
        if action == 'deactivate' and not notes.strip():
            raise serializers.ValidationError("Notes are required for account deactivation.")
        
        return data


class CustomerViewHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for customer view history.
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    view_type_display = serializers.CharField(source='get_view_type_display', read_only=True)
    
    class Meta:
        model = CustomerViewHistory
        fields = [
            'id', 'customer', 'customer_name', 'view_type', 'view_type_display',
            'item_id', 'item_title', 'item_category', 'session_id',
            'ip_address', 'user_agent', 'viewed_at'
        ]
        read_only_fields = '__all__'


class CustomerDownloadHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for customer download history.
    """
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    download_type_display = serializers.CharField(source='get_download_type_display', read_only=True)
    
    class Meta:
        model = CustomerDownloadHistory
        fields = [
            'id', 'customer', 'customer_name', 'download_type', 'download_type_display',
            'item_id', 'item_title', 'file_name', 'file_size', 'download_source',
            'ip_address', 'user_agent', 'downloaded_at'
        ]
        read_only_fields = '__all__'


class CustomerNotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for customer notifications.
    """
    customer_name = serializers.SerializerMethodField()
    notification_type_display = serializers.SerializerMethodField()
    read = serializers.BooleanField(source='is_read', read_only=True)  # Alias for frontend compatibility
    type = serializers.SerializerMethodField()  # Map notification_type to type for frontend
    timestamp = serializers.DateTimeField(source='created_at', read_only=True)  # Alias for frontend
    
    class Meta:
        model = CustomerNotification
        fields = [
            'id', 'customer_id', 'customer_name', 'notification_type', 'notification_type_display',
            'title', 'message', 'priority', 'type', 'email_sent', 'email_sent_at', 'push_sent', 'push_sent_at',
            'is_read', 'read', 'read_at', 'created_at', 'timestamp', 'scheduled_at', 'is_scheduled'
        ]
        read_only_fields = [
            'id', 'customer_id', 'notification_type', 'title', 'message', 'priority', 'type',
            'email_sent', 'email_sent_at', 'push_sent', 'push_sent_at',
            'is_read', 'read', 'read_at', 'created_at', 'timestamp', 'scheduled_at', 'is_scheduled'
        ]
    
    def get_customer_name(self, obj):
        """Get customer name safely."""
        try:
            from django.contrib.auth.models import User
            if hasattr(obj, 'customer_id') and obj.customer_id:
                try:
                    customer = User.objects.get(id=obj.customer_id)
                    full_name = customer.get_full_name()
                    if full_name:
                        return full_name
                    return customer.username or customer.email or 'Unknown'
                except User.DoesNotExist:
                    return 'Unknown'
            return 'Unknown'
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error getting customer name: {e}')
            return 'Unknown'
    
    def get_notification_type_display(self, obj):
        """Get notification type display name safely."""
        try:
            if hasattr(obj, 'get_notification_type_display'):
                return obj.get_notification_type_display()
            return obj.notification_type if hasattr(obj, 'notification_type') else 'Unknown'
        except Exception:
            return obj.notification_type if hasattr(obj, 'notification_type') else 'Unknown'
    
    def get_type(self, obj):
        """Map notification_type to frontend type format."""
        notification_type = obj.notification_type if hasattr(obj, 'notification_type') else 'other'
        
        # Map backend notification types to frontend types
        type_mapping = {
            'system_update': 'info',
            'account_deactivated': 'error',
            'account_reactivated': 'success',
            'subscription_paused': 'warning',
            'subscription_resumed': 'success',
            'payment_successful': 'success',
            'payment_failed': 'error',
            'download_available': 'success',
            'other': 'info',
        }
        
        return type_mapping.get(notification_type, 'info')


class CustomerSearchSerializer(serializers.Serializer):
    """
    Serializer for customer search functionality.
    """
    query = serializers.CharField(max_length=255)
    status = serializers.ChoiceField(choices=CustomerAccountStatus.ACCOUNT_STATUS_CHOICES, required=False)
    plan_status = serializers.ChoiceField(choices=[('active', 'Active'), ('expired', 'Expired'), ('none', 'None')], required=False)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False)


class CustomerAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for customer analytics.
    """
    total_customers = serializers.IntegerField()
    active_customers = serializers.IntegerField()
    deactivated_customers = serializers.IntegerField()
    blocked_customers = serializers.IntegerField()
    customers_with_subscriptions = serializers.IntegerField()
    customers_without_subscriptions = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    recent_registrations = serializers.IntegerField()
    top_customers = serializers.ListField(child=serializers.DictField())
