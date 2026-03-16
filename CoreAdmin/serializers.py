from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from .models import AdminUserProfile, AdminActivityLog, AdminSession, AdminPermissionGroup
from Catalog.models import PDFClient, PDFClientJob
import pyotp
import base64


class AdminLoginSerializer(serializers.Serializer):
    """
    Serializer for admin login (first step - email/password).
    Returns temporary token for 2FA verification.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            # Find user by email
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                raise serializers.ValidationError('Invalid credentials')
            
            # Check if user is active
            if not user.is_active:
                raise serializers.ValidationError('Account is deactivated')
            
            # Check if user has admin profile
            try:
                admin_profile = user.admin_profile
                if not admin_profile.is_active:
                    raise serializers.ValidationError('Admin access is deactivated')
            except AdminUserProfile.DoesNotExist:
                raise serializers.ValidationError('Invalid credentials')
            
            # Authenticate user
            user = authenticate(username=user.username, password=password)
            if not user:
                raise serializers.ValidationError('Invalid credentials')
            
            attrs['user'] = user
            attrs['admin_profile'] = admin_profile
            return attrs
        else:
            raise serializers.ValidationError('Must include email and password')


class Admin2FASetupSerializer(serializers.Serializer):
    """
    Serializer for 2FA setup process.
    """
    def to_representation(self, instance):
        """Generate QR code and setup data for 2FA"""
        if not hasattr(instance, 'admin_profile'):
            raise serializers.ValidationError('User does not have admin profile')
        
        admin_profile = instance.admin_profile
        
        # Check if we have a valid secret (can decrypt it)
        existing_secret = admin_profile.get_two_factor_secret()
        
        # Generate secret if not exists or cannot decrypt existing one
        if not existing_secret:
            # Clear old encrypted secret if it exists but can't be decrypted
            if admin_profile.two_factor_secret:
                admin_profile.two_factor_secret = ''
                admin_profile.save()
            
            # Generate new secret
            secret = pyotp.random_base32()
            admin_profile.set_two_factor_secret(secret)
            admin_profile.save()
        else:
            secret = existing_secret
        
        # Generate QR code - this should work now since we have a valid secret
        qr_code_data = admin_profile.generate_qr_code()
        if not qr_code_data:
            raise serializers.ValidationError('Failed to generate QR code for 2FA setup')
        
        qr_code_base64 = base64.b64encode(qr_code_data).decode('utf-8')
        
        # Get the secret again to ensure we have the latest (in case it was just generated)
        secret_key = admin_profile.get_two_factor_secret()
        if not secret_key:
            raise serializers.ValidationError('Failed to retrieve 2FA secret key')
        
        return {
            'user_id': instance.id,
            'email': instance.email,
            'secret_key': secret_key,
            'qr_code': f"data:image/png;base64,{qr_code_base64}",
            'backup_codes': admin_profile.backup_codes
        }


class Admin2FAVerifySerializer(serializers.Serializer):
    """
    Serializer for 2FA verification during login.
    """
    user_id = serializers.IntegerField()
    totp_code = serializers.CharField(
        max_length=6, 
        min_length=6,
        label='2FA code',
        error_messages={
            'min_length': '2FA code must be 6 characters',
            'max_length': '2FA code must be 6 characters',
            'required': '2FA code is required',
        }
    )
    
    def validate_totp_code(self, value):
        """Validate 2FA code format"""
        if not value.isdigit():
            raise serializers.ValidationError('2FA code must be numeric')
        return value
    
    def validate(self, attrs):
        user_id = attrs.get('user_id')
        totp_code = attrs.get('totp_code')
        
        try:
            user = User.objects.get(id=user_id)
            admin_profile = user.admin_profile
        except (User.DoesNotExist, AdminUserProfile.DoesNotExist):
            raise serializers.ValidationError('Invalid user')
        
        if not admin_profile.is_2fa_enabled:
            raise serializers.ValidationError('2FA is not enabled for this user')
        
        # Verify 2FA code
        if not admin_profile.verify_totp(totp_code):
            raise serializers.ValidationError('Invalid 2FA code')
        
        attrs['user'] = user
        attrs['admin_profile'] = admin_profile
        return attrs


class Admin2FAEnableSerializer(serializers.Serializer):
    """
    Serializer for enabling 2FA.
    """
    totp_code = serializers.CharField(
        max_length=6, 
        min_length=6,
        label='2FA code',
        error_messages={
            'min_length': '2FA code must be 6 characters',
            'max_length': '2FA code must be 6 characters',
            'required': '2FA code is required',
        }
    )
    
    def validate_totp_code(self, value):
        """Validate 2FA code format"""
        if not value.isdigit():
            raise serializers.ValidationError('2FA code must be numeric')
        return value
    
    def validate(self, attrs):
        user = self.context['request'].user
        totp_code = attrs.get('totp_code')
        
        try:
            admin_profile = user.admin_profile
        except AdminUserProfile.DoesNotExist:
            raise serializers.ValidationError('User does not have admin profile')
        
        # Get the secret - if we can't decrypt it, we need to regenerate
        secret = admin_profile.get_two_factor_secret()
        
        # If we can't decrypt the secret (e.g., encryption key changed), 
        # we need to verify the 2FA code using the secret from the setup
        # For now, if secret is None, we'll try to verify anyway (verify_totp handles this)
        # But ideally, the secret should be available from setup
        
        # Verify 2FA code
        if not admin_profile.verify_totp(totp_code):
            # If verification fails and we don't have a decryptable secret,
            # it might be because the encryption key changed
            if not secret:
                raise serializers.ValidationError(
                    'Cannot verify 2FA code. The encryption key may have changed. '
                    'Please set up 2FA again from the Settings page.'
                )
            raise serializers.ValidationError('Invalid 2FA code')
        
        # Generate backup codes
        backup_codes = admin_profile.generate_backup_codes()
        
        # Enable 2FA
        admin_profile.is_2fa_enabled = True
        admin_profile.save()
        
        attrs['backup_codes'] = backup_codes
        return attrs


class Admin2FADisableSerializer(serializers.Serializer):
    """
    Serializer for disabling 2FA.
    """
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        user = self.context['request'].user
        password = attrs.get('password')
        
        # Verify password
        if not user.check_password(password):
            raise serializers.ValidationError('Invalid password')
        
        return attrs


class AdminLogoutSerializer(serializers.Serializer):
    """
    Serializer for admin logout.
    """
    refresh_token = serializers.CharField()


class AdminProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for admin user profile.
    """
    user = serializers.SerializerMethodField()
    admin_group_display = serializers.CharField(source='get_admin_group_display', read_only=True)
    is_2fa_enabled = serializers.BooleanField(read_only=True)
    
    permissions = serializers.SerializerMethodField()
    permission_group = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminUserProfile
        fields = [
            'id', 'user', 'admin_group', 'admin_group_display', 'is_2fa_enabled', 
            'last_2fa_verification', 'is_active', 'permissions', 'permission_group', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_permission_group(self, obj):
        """Get permission group info"""
        if obj.permission_group:
            return {
                'id': obj.permission_group.id,
                'name': obj.permission_group.name,
                'description': obj.permission_group.description,
            }
        return None
    
    def get_permissions(self, obj):
        """Get all permissions (group + individual)"""
        return obj.get_all_permissions()
    
    def get_user(self, obj):
        # Get primary mobile number if exists
        mobile_number = ''
        try:
            from Authentication.models import MobileNumber
            # Query mobile numbers directly via ForeignKey (created_by)
            # Also check if there's a relation in the Relation table as fallback
            primary_mobile = MobileNumber.objects.filter(
                created_by=obj.user,
                is_primary=True
            ).first()
            
            if not primary_mobile:
                # Fallback: try to get any mobile number for this user
                any_mobile = MobileNumber.objects.filter(created_by=obj.user).first()
                if any_mobile:
                    primary_mobile = any_mobile
            
            if primary_mobile:
                mobile_number = primary_mobile.mobile_number
        except Exception as e:
            pass
        
        # Get profile photo URL if exists
        profile_photo_url = None
        try:
            from MediaFiles.models import Relation, Media
            request = self.context.get('request') if self.context else None
            profile_photo_relations = Relation.objects.filter(
                relation_type='AdminUserProfile:Media',
                id_1=obj.pk
            )
            for relation in profile_photo_relations:
                if relation.meta and relation.meta.get('type') == 'profile_photo':
                    try:
                        profile_photo = Media.objects.get(pk=relation.id_2)
                        if profile_photo.file:
                            try:
                                from django.conf import settings
                                # Use Django's file.url property which correctly handles MEDIA_URL
                                url = profile_photo.file.url
                                # Build absolute URL using SITE_URL from settings if available
                                site_url = getattr(settings, 'SITE_URL', None)
                                if site_url and url.startswith('/'):
                                    site_url = site_url.rstrip('/')
                                    profile_photo_url = f"{site_url}{url}"
                                elif request:
                                    if url.startswith('/'):
                                        profile_photo_url = request.build_absolute_uri(url)
                                    elif url.startswith('http'):
                                        profile_photo_url = url
                                    else:
                                        profile_photo_url = request.build_absolute_uri('/' + url)
                                else:
                                    profile_photo_url = url
                            except (ValueError, AttributeError, Exception):
                                profile_photo_url = None
                            break
                    except Media.DoesNotExist:
                        continue
        except Exception:
            pass
        
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'email': obj.user.email,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
            'mobile_number': mobile_number,
            'profile_photo_url': profile_photo_url,
            'is_active': obj.user.is_active,
            'is_staff': obj.user.is_staff,
            'is_superuser': obj.user.is_superuser,
        }


class AdminProfileUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating admin user profile.
    """
    first_name = serializers.CharField(max_length=30, required=False)
    last_name = serializers.CharField(max_length=30, required=False)
    email = serializers.EmailField(required=False)
    mobile_number = serializers.CharField(max_length=15, required=False, allow_blank=True)
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        user = self.context['request'].user
        from django.contrib.auth.models import User
        if User.objects.filter(email=value).exclude(id=user.id).exists():
            raise serializers.ValidationError('Email already exists')
        return value
    
    def validate_mobile_number(self, value):
        """Validate mobile number format and uniqueness"""
        if value:
            # Remove any non-digit characters for validation
            digits_only = ''.join(filter(str.isdigit, value))
            # Check if it's a 10-digit number (without country code)
            if len(digits_only) != 10:
                raise serializers.ValidationError("Mobile number must be exactly 10 digits.")
            
            # Check if mobile number already exists and belongs to another user
            from Authentication.models import MobileNumber
            user = self.context['request'].user
            existing_mobile = MobileNumber.objects.filter(mobile_number=value).exclude(created_by=user).first()
            if existing_mobile:
                raise serializers.ValidationError("This mobile number is already associated with another account.")
        return value
    
    def update(self, instance, validated_data):
        """Update admin user profile"""
        user = instance.user
        
        # Update user fields
        if 'first_name' in validated_data:
            user.first_name = validated_data['first_name']
        if 'last_name' in validated_data:
            user.last_name = validated_data['last_name']
        if 'email' in validated_data:
            user.email = validated_data['email']
        
        user.save()
        
        # Update mobile number if provided
        if 'mobile_number' in validated_data:
            mobile_number = validated_data['mobile_number']
            from Authentication.models import MobileNumber
            
            try:
                # Query mobile numbers directly via ForeignKey (created_by)
                primary_mobile = MobileNumber.objects.filter(
                    created_by=user,
                    is_primary=True
                ).first()
                
                if mobile_number:
                    # Check if this mobile number already exists for this user
                    existing_mobile = MobileNumber.objects.filter(
                        mobile_number=mobile_number,
                        created_by=user
                    ).first()
                    
                    if existing_mobile:
                        # Mobile number already exists for this user - make it primary if it isn't
                        if not existing_mobile.is_primary:
                            # Remove primary status from other mobile numbers
                            MobileNumber.objects.filter(
                                created_by=user,
                                is_primary=True
                            ).update(is_primary=False)
                            existing_mobile.is_primary = True
                            existing_mobile.updated_by = user
                            existing_mobile.save()
                    elif primary_mobile:
                        # Update existing primary mobile number
                        # Check if the new number conflicts with another user's number
                        conflicting_mobile = MobileNumber.objects.filter(
                            mobile_number=mobile_number
                        ).exclude(created_by=user).first()
                        
                        if conflicting_mobile:
                            raise serializers.ValidationError({
                                'mobile_number': ['This mobile number is already associated with another account.']
                            })
                        
                        primary_mobile.mobile_number = mobile_number
                        primary_mobile.updated_by = user
                        primary_mobile.save()
                    else:
                        # Create new primary mobile number
                        # Check if the number already exists (should be caught in validation, but double-check)
                        conflicting_mobile = MobileNumber.objects.filter(
                            mobile_number=mobile_number
                        ).exclude(created_by=user).first()
                        
                        if conflicting_mobile:
                            raise serializers.ValidationError({
                                'mobile_number': ['This mobile number is already associated with another account.']
                            })
                        
                        MobileNumber.objects.create(
                            mobile_number=mobile_number,
                            is_primary=True,
                            created_by=user,
                            updated_by=user
                        )
                elif primary_mobile:
                    # If mobile_number is empty, remove primary mobile
                    primary_mobile.delete()
            except serializers.ValidationError:
                # Re-raise validation errors
                raise
            except Exception as e:
                # Handle database errors and other exceptions
                error_message = str(e)
                if 'unique constraint' in error_message.lower() or 'duplicate key' in error_message.lower():
                    raise serializers.ValidationError({
                        'mobile_number': ['This mobile number is already associated with another account.']
                    })
                else:
                    raise serializers.ValidationError({
                        'mobile_number': [f'Failed to update mobile number: {error_message}']
                    })
        
        return instance


class AdminActivityLogSerializer(serializers.ModelSerializer):
    """
    Serializer for admin activity logs (read-only for superusers).
    """
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)
    
    class Meta:
        model = AdminActivityLog
        fields = [
            'id', 'user_name', 'user_email', 'activity_type', 
            'activity_type_display', 'description', 'ip_address', 
            'user_agent', 'metadata', 'timestamp'
        ]
        read_only_fields = [
            'id', 'user_name', 'user_email', 'activity_type', 
            'activity_type_display', 'description', 'ip_address', 
            'user_agent', 'metadata', 'timestamp'
        ]


class AdminSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for admin sessions.
    """
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminSession
        fields = [
            'id', 'user_name', 'user_email', 'session_key', 
            'ip_address', 'user_agent', 'is_active', 
            'last_activity', 'created_at', 'is_expired'
        ]
        read_only_fields = [
            'id', 'user_name', 'user_email', 'session_key', 
            'ip_address', 'user_agent', 'is_active', 
            'last_activity', 'created_at', 'is_expired'
        ]
    
    def get_is_expired(self, obj):
        return obj.is_expired()


class AdminUserCreateSerializer(serializers.Serializer):
    """
    Serializer for creating admin users.
    """
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True, min_length=8)
    admin_group = serializers.ChoiceField(choices=AdminUserProfile.ADMIN_GROUP_CHOICES)
    permission_group_id = serializers.IntegerField(required=False, allow_null=True)
    permissions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('User with this email already exists')
        return value
    
    def validate_permission_group_id(self, value):
        """Validate permission group ID"""
        if value is None:
            return value
        try:
            group = AdminPermissionGroup.objects.get(id=value, is_active=True)
            return value
        except AdminPermissionGroup.DoesNotExist:
            raise serializers.ValidationError('Permission group not found or inactive')
    
    def create(self, validated_data):
        """Create admin user"""
        admin_group = validated_data.pop('admin_group')
        permission_group_id = validated_data.pop('permission_group_id', None)
        permissions = validated_data.pop('permissions', [])
        
        # Create user
        user = User.objects.create_user(
            username=validated_data['email'].split('@')[0],
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
            password=validated_data['password'],
            is_active=True,
            is_staff=True  # Admin users are staff
        )
        
        # Get permission group if provided
        permission_group = None
        if permission_group_id:
            try:
                permission_group = AdminPermissionGroup.objects.get(id=permission_group_id, is_active=True)
            except AdminPermissionGroup.DoesNotExist:
                pass  # Will be None if not found
        
        # Create admin profile
        AdminUserProfile.objects.create(
            user=user,
            admin_group=admin_group,
            permission_group=permission_group,
            permissions=permissions
        )
        
        return user


class AdminPermissionGroupSerializer(serializers.ModelSerializer):
    """
    Serializer for permission groups.
    """
    permission_count = serializers.IntegerField(source='get_permission_count', read_only=True)
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminPermissionGroup
        fields = ['id', 'name', 'description', 'permissions', 'is_active', 
                  'permission_count', 'member_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        """Get the number of moderators in this group"""
        return obj.members.filter(admin_group='moderator', is_active=True).count()


class AdminPermissionGroupListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing permission groups.
    """
    permission_count = serializers.IntegerField(source='get_permission_count', read_only=True)
    member_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminPermissionGroup
        fields = ['id', 'name', 'description', 'permission_count', 'member_count', 
                  'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_member_count(self, obj):
        """Get the number of moderators in this group"""
        return obj.members.filter(admin_group='moderator', is_active=True).count()


class AdminUserListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing admin users.
    """
    id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    full_name = serializers.SerializerMethodField()
    admin_group_display = serializers.CharField(source='get_admin_group_display', read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    is_2fa_enabled = serializers.BooleanField(read_only=True)
    last_login = serializers.DateTimeField(source='user.last_login', read_only=True, allow_null=True)
    permission_group = serializers.SerializerMethodField()
    
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = AdminUserProfile
        fields = ['id', 'email', 'first_name', 'last_name', 'full_name', 'admin_group', 
                  'admin_group_display', 'is_active', 'is_2fa_enabled', 'permissions', 
                  'permission_group', 'created_at', 'updated_at', 'last_login']
    
    def get_full_name(self, obj):
        """Get full name from user"""
        return f"{obj.user.first_name} {obj.user.last_name}".strip()
    
    def get_permission_group(self, obj):
        """Get permission group info"""
        if obj.permission_group:
            return {
                'id': obj.permission_group.id,
                'name': obj.permission_group.name,
                'description': obj.permission_group.description,
            }
        return None
    
    def get_permissions(self, obj):
        """Get all permissions (group + individual)"""
        return obj.get_all_permissions()


class AdminUserUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating admin users.
    """
    first_name = serializers.CharField(max_length=30, required=False)
    last_name = serializers.CharField(max_length=30, required=False)
    admin_group = serializers.ChoiceField(
        choices=AdminUserProfile.ADMIN_GROUP_CHOICES, 
        required=False
    )
    is_active = serializers.BooleanField(required=False)
    permissions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
    
    def update(self, instance, validated_data):
        """Update admin user"""
        # Update user fields
        if 'first_name' in validated_data:
            instance.user.first_name = validated_data['first_name']
        if 'last_name' in validated_data:
            instance.user.last_name = validated_data['last_name']
        if 'is_active' in validated_data:
            instance.user.is_active = validated_data['is_active']
        
        instance.user.save()
        
        # Update permission group
        if 'permission_group_id' in validated_data:
            permission_group_id = validated_data['permission_group_id']
            if permission_group_id is None:
                instance.permission_group = None
            else:
                try:
                    instance.permission_group = AdminPermissionGroup.objects.get(
                        id=permission_group_id, 
                        is_active=True
                    )
                except AdminPermissionGroup.DoesNotExist:
                    raise serializers.ValidationError('Permission group not found or inactive')
        
        # Update permission group
        if 'permission_group_id' in validated_data:
            permission_group_id = validated_data['permission_group_id']
            if permission_group_id is None:
                instance.permission_group = None
            else:
                try:
                    instance.permission_group = AdminPermissionGroup.objects.get(
                        id=permission_group_id, 
                        is_active=True
                    )
                except AdminPermissionGroup.DoesNotExist:
                    raise serializers.ValidationError('Permission group not found or inactive')
        
        # Update admin profile
        if 'admin_group' in validated_data:
            instance.admin_group = validated_data['admin_group']
            # Clear permission group if switching to superadmin
            if validated_data['admin_group'] == 'superadmin':
                instance.permission_group = None
        if 'is_active' in validated_data:
            instance.is_active = validated_data['is_active']
        if 'permissions' in validated_data:
            instance.permissions = validated_data['permissions']
        
        instance.save()
        return instance


class AdminUserPasswordResetSerializer(serializers.Serializer):
    """
    Serializer for resetting admin user password (by Super Admin).
    """
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """Validate password reset"""
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError('New passwords do not match')
        
        return attrs


class PDFClientSerializer(serializers.ModelSerializer):
    """Serializer for admin-configured PDF clients."""

    created_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = PDFClient
        fields = ["id", "name", "customer_mobile", "created_at", "created_by"]
        read_only_fields = ["id", "created_at", "created_by"]


class PDFClientJobStatusSerializer(serializers.ModelSerializer):
    """Serializer for PDF client job status polling."""

    client_name = serializers.CharField(source="client.name", read_only=True)

    class Meta:
        model = PDFClientJob
        fields = [
            "id",
            "client",
            "client_name",
            "status",
            "designs_per_pdf",
            "requested_pdfs",
            "generated_pdfs",
            "total_designs_requested",
            "total_designs_used",
            "progress_percent",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "client",
            "client_name",
            "generated_pdfs",
            "total_designs_requested",
            "total_designs_used",
            "progress_percent",
            "error_message",
            "created_at",
            "updated_at",
        ]


class PDFClientJobCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a PDF client job.
    File upload (customer_logo) is handled directly in the view.
    """

    client_id = serializers.IntegerField()
    number_of_pdfs = serializers.IntegerField(min_value=1, max_value=10)
    designs_per_pdf = serializers.IntegerField(required=False)
    customer_name = serializers.CharField(max_length=255)
    customer_mobile = serializers.CharField(max_length=20)

    def validate_client_id(self, value):
        try:
            PDFClient.objects.get(id=value)
        except PDFClient.DoesNotExist:
            raise serializers.ValidationError("PDF client does not exist.")
        return value


class AdminPasswordChangeSerializer(serializers.Serializer):
    """
    Serializer for changing admin password.
    """
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        """Validate password change"""
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')
        
        if new_password != confirm_password:
            raise serializers.ValidationError('New passwords do not match')
        
        return attrs
    
    def validate_old_password(self, value):
        """Validate old password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect')
        return value


class AdminNotificationCreateSerializer(serializers.Serializer):
    """
    Serializer for creating admin notifications.
    """
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    priority = serializers.ChoiceField(
        choices=['low', 'medium', 'high', 'critical'], 
        default='medium'
    )
    recipients = serializers.DictField(
        child=serializers.BooleanField(),
        help_text="Dict with 'designers' and 'customers' keys"
    )
    sendType = serializers.ChoiceField(choices=['immediate', 'scheduled'])
    scheduledAt = serializers.DateTimeField(required=False, allow_null=True)
    deliveryMethod = serializers.ChoiceField(
        choices=['in_app', 'email', 'both'],
        default='both',
        help_text="How to deliver notification: 'in_app' (app only), 'email' (email only), or 'both'"
    )
    
    def validate_recipients(self, value):
        """Validate recipients dict"""
        if not isinstance(value, dict):
            raise serializers.ValidationError('Recipients must be a dictionary')
        
        designers = value.get('designers', False)
        customers = value.get('customers', False)
        
        if not designers and not customers:
            raise serializers.ValidationError(
                'Please select at least one recipient type (designers or customers)'
            )
        
        return value
    
    def validate(self, attrs):
        """Validate scheduled notification"""
        send_type = attrs.get('sendType')
        scheduled_at = attrs.get('scheduledAt')
        
        if send_type == 'scheduled':
            if not scheduled_at:
                raise serializers.ValidationError({
                    'scheduledAt': 'Scheduled date and time is required for scheduled notifications'
                })
            
            from django.utils import timezone
            if scheduled_at <= timezone.now():
                raise serializers.ValidationError({
                    'scheduledAt': 'Scheduled time must be in the future'
                })
        
        return attrs
