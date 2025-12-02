from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Addresses, DesignerProfile, Studio, StudioBusinessDetails, StudioMember, Ratings, DesignProcessingTask
from Accounts.serializers import UserSerializer
from MediaFiles.serializers import MediaSerializer
from Catalog.serializers import ProductSerializer


class AddressesSerializer(serializers.ModelSerializer):
    """
    Serializer for Addresses model with full CRUD operations.
    Handles address creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Addresses
        fields = [
            'id', 'address_line_1', 'address_line_2', 'landmark', 'city', 'state',
            'country', 'postal_code', 'address_type', 'is_postal', 'is_permanent',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_address_line_1(self, value):
        """
        Validate address line 1 is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Address line 1 cannot be empty.")
        return value.strip()
    
    def validate_city(self, value):
        """
        Validate city is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("City cannot be empty.")
        return value.strip()
    
    def validate_state(self, value):
        """
        Validate state is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("State cannot be empty.")
        return value.strip()
    
    def validate_country(self, value):
        """
        Validate country is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Country cannot be empty.")
        return value.strip()
    
    def validate_postal_code(self, value):
        """
        Validate postal code is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Postal code cannot be empty.")
        return value.strip()


class AddressesListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Addresses model used in list views.
    """
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Addresses
        fields = [
            'id', 'address_line_1', 'city', 'state', 'country', 
            'postal_code', 'address_type', 'is_postal', 'is_permanent', 'created_at'
        ]


class DesignerProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for DesignerProfile model with full CRUD operations.
    Handles designer profile creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    media = serializers.SerializerMethodField()
    is_studio_owner = serializers.SerializerMethodField()
    is_studio_member = serializers.SerializerMethodField()
    profile_type = serializers.SerializerMethodField()
    has_full_console_access = serializers.SerializerMethodField()
    can_upload_designs = serializers.SerializerMethodField()
    
    class Meta:
        model = DesignerProfile
        fields = [
            'id', 'bio', 'date_of_birth', 'skill_tags', 'status', 'is_individual', 'onboarding_completed',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'media',
            'is_studio_owner', 'is_studio_member', 'profile_type',
            'has_full_console_access', 'can_upload_designs'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'onboarding_completed']
    
    def get_media(self, obj):
        """
        Get related media for the designer profile.
        """
        if obj:
            media = obj.get_media()
            return MediaSerializer(media, many=True).data
        return []
    
    def get_is_studio_owner(self, obj):
        """Check if this profile belongs to a studio owner."""
        return obj.is_studio_owner()
    
    def get_is_studio_member(self, obj):
        """Check if this profile belongs to a studio member."""
        return obj.is_studio_member()
    
    def get_profile_type(self, obj):
        """Get the profile type: 'owner', 'member', or 'individual'."""
        return obj.profile_type
    
    def get_has_full_console_access(self, obj):
        """Check if this profile has full console access."""
        return obj.has_full_console_access
    
    def get_can_upload_designs(self, obj):
        """Check if this profile can upload designs."""
        return obj.can_upload_designs
    
    def validate_skill_tags(self, value):
        """
        Validate skill tags format.
        """
        if not isinstance(value, list):
            raise serializers.ValidationError("Skill tags must be a list.")
        
        for tag in value:
            if not isinstance(tag, str) or not tag.strip():
                raise serializers.ValidationError("Each skill tag must be a non-empty string.")
        
        return value
    
    def validate_bio(self, value):
        """
        Validate bio is not empty if provided.
        """
        if value is not None and not value.strip():
            raise serializers.ValidationError("Bio cannot be empty.")
        return value.strip() if value else value


class DesignerProfileListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for DesignerProfile model used in list views.
    """
    created_by = UserSerializer(read_only=True)
    media_count = serializers.SerializerMethodField()
    
    class Meta:
        model = DesignerProfile
        fields = [
            'id', 'bio', 'skill_tags', 'status', 'created_by', 'created_at', 'media_count'
        ]
    
    def get_media_count(self, obj):
        """
        Get count of related media.
        """
        return len(obj.get_media())


class StudioSerializer(serializers.ModelSerializer):
    """
    Serializer for Studio model with full CRUD operations.
    Handles studio creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    media = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Studio
        fields = [
            'id', 'name', 'wedesignz_auto_name', 'studio_industry_type', 'status',
            'daily_design_generation_capacity', 'remarks', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'created_by_id', 'updated_by_id', 'media', 'members_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_media(self, obj):
        """
        Get related media for the studio.
        """
        if obj:
            media = obj.get_media()
            return MediaSerializer(media, many=True).data
        return []
    
    def get_members_count(self, obj):
        """
        Get count of studio members.
        """
        return obj.members.count()
    
    def validate_name(self, value):
        """
        Validate studio name is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Studio name cannot be empty.")
        return value.strip()
    
    def validate_wedesignz_auto_name(self, value):
        """
        Validate WeDesignz auto name is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("WeDesignz auto name cannot be empty.")
        return value.strip()
    
    def validate_daily_design_generation_capacity(self, value):
        """
        Validate daily design generation capacity is non-negative.
        """
        if value < 0:
            raise serializers.ValidationError("Daily design generation capacity cannot be negative.")
        return value


class StudioListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Studio model used in list views.
    """
    created_by = UserSerializer(read_only=True)
    media_count = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Studio
        fields = [
            'id', 'name', 'wedesignz_auto_name', 'studio_industry_type', 'status',
            'daily_design_generation_capacity', 'created_by', 'created_at',
            'media_count', 'members_count'
        ]
    
    def get_media_count(self, obj):
        """
        Get count of related media.
        """
        return len(obj.get_media())
    
    def get_members_count(self, obj):
        """
        Get count of studio members.
        """
        return obj.members.count()


class StudioBusinessDetailsSerializer(serializers.ModelSerializer):
    """
    Serializer for StudioBusinessDetails model with full CRUD operations.
    Handles studio business details creation, updates, and management.
    """
    studio = StudioSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    studio_id = serializers.IntegerField(write_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = StudioBusinessDetails
        fields = [
            'id', 'studio', 'studio_id', 'studio_email', 'studio_mobile_number',
            'legal_business_name', 'business_type', 'business_category',
            'business_sub_category', 'business_model', 'registered_addresses_json',
            'pan_number', 'pan_card', 'gst_number', 'msme_udyam_number',
            'msme_certificate_annexure', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_studio_id(self, value):
        """
        Validate that studio exists.
        """
        try:
            Studio.objects.get(id=value)
        except Studio.DoesNotExist:
            raise serializers.ValidationError("Studio does not exist.")
        return value
    
    def validate_studio_email(self, value):
        """
        Validate studio email format.
        Allow empty for individuals.
        """
        if value and value.strip():
            return value.strip()
        return value  # Allow None/empty for individuals
    
    def validate_studio_mobile_number(self, value):
        """
        Validate studio mobile number is not empty.
        Allow empty for individuals.
        """
        if value and value.strip():
            return value.strip()
        return value  # Allow None/empty for individuals
    
    def validate_legal_business_name(self, value):
        """
        Validate legal business name is not empty.
        Allow empty for individuals.
        """
        if value and value.strip():
            return value.strip()
        return value  # Allow None/empty for individuals
    
    def validate(self, attrs):
        """
        Cross-field validation.
        For individuals, most business fields are optional.
        """
        business_type = attrs.get('business_type')
        is_individual = business_type == 'individual'
        
        # For individuals, these fields are optional
        if is_individual:
            # Allow None/empty for individuals
            return attrs
        
        # For companies, validate required fields
        if not attrs.get('studio_email'):
            raise serializers.ValidationError({
                'studio_email': 'Studio email is required for companies.'
            })
        if not attrs.get('studio_mobile_number'):
            raise serializers.ValidationError({
                'studio_mobile_number': 'Studio mobile number is required for companies.'
            })
        if not attrs.get('legal_business_name'):
            raise serializers.ValidationError({
                'legal_business_name': 'Legal business name is required for companies.'
            })
        
        return attrs


class StudioBusinessDetailsListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for StudioBusinessDetails model used in list views.
    """
    studio = StudioListSerializer(read_only=True)
    
    class Meta:
        model = StudioBusinessDetails
        fields = [
            'id', 'studio', 'studio_email', 'studio_mobile_number',
            'legal_business_name', 'business_type', 'business_category',
            'created_at'
        ]


class StudioMemberSerializer(serializers.ModelSerializer):
    """
    Serializer for StudioMember model with full CRUD operations.
    Handles studio member creation, updates, and management.
    """
    studio = StudioSerializer(read_only=True)
    member = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    studio_id = serializers.IntegerField(write_only=True)
    member_id = serializers.IntegerField(write_only=True, required=True, help_text='The user ID of the member being added to the studio')
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = StudioMember
        fields = [
            'id', 'studio', 'studio_id', 'member', 'member_id', 'role', 'status',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_studio_id(self, value):
        """
        Validate that studio exists.
        """
        try:
            Studio.objects.get(id=value)
        except Studio.DoesNotExist:
            raise serializers.ValidationError("Studio does not exist.")
        return value
    
    def validate_member_id(self, value):
        """
        Validate that member user exists.
        """
        try:
            User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Member user does not exist.")
        return value


class CreateStudioMemberWithUserSerializer(serializers.Serializer):
    """
    Serializer for creating a new studio member with a new user account.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True)
    first_name = serializers.CharField(max_length=30, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=30, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=StudioMember.ROLE_CHOICES, default='designer')
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    
    def validate(self, attrs):
        """Validate password confirmation"""
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        
        if password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match."})
        
        # Validate password strength
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        try:
            validate_password(password)
        except ValidationError as e:
            raise serializers.ValidationError({"password": e.messages})
        
        return attrs


class StudioMemberListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for StudioMember model used in list views.
    """
    studio = StudioListSerializer(read_only=True)
    member = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = StudioMember
        fields = ['id', 'studio', 'member', 'role', 'status', 'created_by', 'created_at']


class RatingsSerializer(serializers.ModelSerializer):
    """
    Serializer for Ratings model with full CRUD operations.
    Handles rating creation, updates, and management.
    """
    studio = StudioSerializer(read_only=True)
    studio_member = StudioMemberSerializer(read_only=True)
    product = ProductSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    studio_id = serializers.IntegerField(write_only=True, required=False)
    studio_member_id = serializers.IntegerField(write_only=True, required=False)
    product_id = serializers.IntegerField(write_only=True, required=False)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Ratings
        fields = [
            'id', 'studio', 'studio_id', 'studio_member', 'studio_member_id',
            'product', 'product_id', 'rating_type', 'rating_value', 'rating_title',
            'rating_description', 'tags', 'status', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_rating_value(self, value):
        """
        Validate rating value is within valid range.
        """
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating value must be between 1 and 5.")
        return value
    
    def validate_rating_title(self, value):
        """
        Validate rating title is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Rating title cannot be empty.")
        return value.strip()
    
    def validate_rating_description(self, value):
        """
        Validate rating description is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Rating description cannot be empty.")
        return value.strip()
    
    def validate_tags(self, value):
        """
        Validate tags format.
        """
        if not isinstance(value, list):
            raise serializers.ValidationError("Tags must be a list.")
        
        for tag in value:
            if not isinstance(tag, str) or not tag.strip():
                raise serializers.ValidationError("Each tag must be a non-empty string.")
        
        return value
    
    def validate(self, attrs):
        """
        Validate business logic for ratings.
        """
        rating_type = attrs.get('rating_type')
        studio_id = attrs.get('studio_id')
        studio_member_id = attrs.get('studio_member_id')
        product_id = attrs.get('product_id')
        
        # Validate that at least one target is specified
        if not any([studio_id, studio_member_id, product_id]):
            raise serializers.ValidationError("At least one target (studio, studio_member, or product) must be specified.")
        
        # Validate that only one target is specified per rating type
        targets_specified = sum([bool(studio_id), bool(studio_member_id), bool(product_id)])
        if targets_specified > 1:
            raise serializers.ValidationError("Only one target can be specified per rating.")
        
        # Validate target exists based on rating type
        if rating_type == 'studio' and not studio_id:
            raise serializers.ValidationError("Studio ID is required for studio ratings.")
        elif rating_type == 'member' and not studio_member_id:
            raise serializers.ValidationError("Studio member ID is required for member ratings.")
        elif rating_type == 'product' and not product_id:
            raise serializers.ValidationError("Product ID is required for product ratings.")
        
        return attrs


class RatingsListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Ratings model used in list views.
    """
    studio = StudioListSerializer(read_only=True)
    studio_member = StudioMemberListSerializer(read_only=True)
    product = ProductSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Ratings
        fields = [
            'id', 'studio', 'studio_member', 'product', 'rating_type',
            'rating_value', 'rating_title', 'status', 'created_by', 'created_at'
        ]


class ProfileSearchSerializer(serializers.Serializer):
    """
    Serializer for profile search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    profile_type = serializers.ChoiceField(
        choices=['designer', 'studio', 'address'],
        required=False
    )
    status = serializers.ChoiceField(
        choices=DesignerProfile.STATUS_CHOICES,
        required=False
    )
    skill_tags = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False
    )
    studio_industry_type = serializers.ChoiceField(
        choices=Studio.INDUSTRY_TYPE_CHOICES,
        required=False
    )
    address_type = serializers.ChoiceField(
        choices=Addresses.ADDRESS_TYPE_CHOICES,
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        return attrs


class ProfileFilterSerializer(serializers.Serializer):
    """
    Serializer for profile filtering functionality.
    """
    statuses = serializers.ListField(
        child=serializers.ChoiceField(choices=DesignerProfile.STATUS_CHOICES),
        required=False
    )
    studio_industry_types = serializers.ListField(
        child=serializers.ChoiceField(choices=Studio.INDUSTRY_TYPE_CHOICES),
        required=False
    )
    address_types = serializers.ListField(
        child=serializers.ChoiceField(choices=Addresses.ADDRESS_TYPE_CHOICES),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )


class ProfileAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for profile analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['status', 'created_by', 'profile_type'],
        required=False
    )
    
    def validate(self, attrs):
        """
        Validate date range and grouping options.
        """
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class BulkProfileUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk profile updates.
    """
    profile_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    profile_type = serializers.ChoiceField(
        choices=['designer', 'studio', 'address'],
        required=False
    )
    updates = serializers.DictField()
    
    def validate_profile_ids(self, value):
        """
        Validate that all profiles exist.
        """
        # This would need to be implemented based on the specific profile type
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['status', 'bio', 'skill_tags']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class DesignerProfileCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating designer profiles with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = DesignerProfile
        fields = ['bio', 'skill_tags', 'created_by_id']
    
    def validate_skill_tags(self, value):
        """
        Validate skill tags format.
        """
        if not isinstance(value, list):
            raise serializers.ValidationError("Skill tags must be a list.")
        
        for tag in value:
            if not isinstance(tag, str) or not tag.strip():
                raise serializers.ValidationError("Each skill tag must be a non-empty string.")
        
        return value


class StudioCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating studios with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Studio
        fields = [
            'name', 'wedesignz_auto_name', 'studio_industry_type',
            'daily_design_generation_capacity', 'remarks', 'created_by_id'
        ]
    
    def validate_name(self, value):
        """
        Validate studio name is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Studio name cannot be empty.")
        return value.strip()
    
    def validate_wedesignz_auto_name(self, value):
        """
        Validate WeDesignz auto name is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("WeDesignz auto name cannot be empty.")
        return value.strip()


class AddressCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating addresses with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Addresses
        fields = [
            'address_line_1', 'address_line_2', 'landmark', 'city', 'state',
            'country', 'postal_code', 'address_type', 'is_postal', 'is_permanent', 'created_by_id'
        ]
    
    def validate_address_line_1(self, value):
        """
        Validate address line 1 is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Address line 1 cannot be empty.")
        return value.strip()
from django.contrib.auth.models import User
from django.db.models import Sum
from Profiles.models import DesignerProfile
from Wallet.models import Wallet, WalletTransaction, WalletWithdrawalRequest
from Authentication.user_relations import get_user_wallets
from common.relations import get_related
from CoreAdmin.models import (
    DesignerOnboardingStatus, DesignerPayoutRequest, DesignerAccountSuspension,
    DesignerNotification, AdminUserProfile
)


class DesignerManagementSerializer(serializers.ModelSerializer):
    """
    Serializer for designer management list view.
    """
    designer_status = serializers.SerializerMethodField()
    designer_bio = serializers.SerializerMethodField()
    skill_tags = serializers.SerializerMethodField()
    joined_date = serializers.DateTimeField(source='date_joined', read_only=True)
    last_login = serializers.DateTimeField(read_only=True)
    total_earnings = serializers.SerializerMethodField()
    pending_withdrawals = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'designer_status', 'designer_bio', 'skill_tags',
            'joined_date', 'last_login', 'total_earnings', 'pending_withdrawals', 'wallet_balance'
        ]
    
    def get_designer_status(self, obj):
        """Get designer profile status"""
        profile = obj.created_designer_profiles.first()
        return profile.status if profile else None
    
    def get_designer_bio(self, obj):
        """Get designer profile bio"""
        profile = obj.created_designer_profiles.first()
        return profile.bio if profile else None
    
    def get_skill_tags(self, obj):
        """Get designer profile skill tags"""
        profile = obj.created_designer_profiles.first()
        return profile.skill_tags if profile else []
    
    def get_total_earnings(self, obj):
        """Calculate total lifetime earnings for the designer"""
        wallets = get_user_wallets(obj)
        if not wallets.exists():
            return 0
        
        total = WalletTransaction.objects.filter(
            wallet__in=wallets,
            wallet_transaction_type='credit'
        ).aggregate(total=Sum('amount'))['total']
        
        return float(total) if total else 0
    
    def get_pending_withdrawals(self, obj):
        """Calculate pending withdrawal amount"""
        wallets = get_user_wallets(obj)
        if not wallets.exists():
            return 0
        
        pending = WalletWithdrawalRequest.objects.filter(
            wallet__in=wallets,
            status='pending'
        ).aggregate(total=Sum('amount'))['total']
        
        return float(pending) if pending else 0
    
    def get_wallet_balance(self, obj):
        """Get current wallet balance"""
        wallets = get_user_wallets(obj)
        if not wallets.exists():
            return 0
        
        primary_wallet = wallets.first()
        return float(primary_wallet.balance)


class DesignerDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed designer information.
    """
    designer_profile = serializers.SerializerMethodField()
    wallet_info = serializers.SerializerMethodField()
    business_documents = serializers.SerializerMethodField()
    transaction_summary = serializers.SerializerMethodField()
    withdrawal_requests = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'is_active', 'date_joined', 'last_login', 'is_staff',
            'designer_profile', 'wallet_info', 'business_documents',
            'transaction_summary', 'withdrawal_requests'
        ]
    
    def get_designer_profile(self, obj):
        """Get designer profile information"""
        try:
            # Use the correct reverse relation name from DesignerProfile model
            # DesignerProfile has related_name='created_designer_profiles'
            profile = obj.created_designer_profiles.first()
            if not profile:
                return None
            return {
                'id': profile.id,
                'bio': profile.bio,
                'skill_tags': profile.skill_tags,
                'status': profile.status,
                'status_display': profile.get_status_display(),
                'created_at': profile.created_at,
                'updated_at': profile.updated_at,
                'media_count': len(profile.get_media())
            }
        except (DesignerProfile.DoesNotExist, AttributeError):
            return None
    
    def get_wallet_info(self, obj):
        """Get wallet information and financial summary"""
        wallets = get_user_wallets(obj)
        if not wallets.exists():
            return {
                'has_wallet': False,
                'balance': 0,
                'total_earnings': 0,
                'pending_withdrawals': 0
            }
        
        primary_wallet = wallets.first()
        
        # Calculate financial metrics
        total_earnings = WalletTransaction.objects.filter(
            wallet=primary_wallet,
            wallet_transaction_type='credit'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        pending_withdrawals = WalletWithdrawalRequest.objects.filter(
            wallet=primary_wallet,
            status='pending'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return {
            'has_wallet': True,
            'wallet_id': primary_wallet.id,
            'balance': float(primary_wallet.balance),
            'total_earnings': float(total_earnings),
            'pending_withdrawals': float(pending_withdrawals),
            'available_balance': float(primary_wallet.balance) - float(pending_withdrawals)
        }
    
    def get_business_documents(self, obj):
        """Get business documents and verification status"""
        # This would integrate with document verification system
        # For now, return placeholder data
        return {
            'pan_verified': False,
            'aadhar_verified': False,
            'bank_account_verified': False,
            'business_documents': [],
            'verification_status': 'pending'
        }
    
    def get_transaction_summary(self, obj):
        """Get transaction summary for the designer"""
        wallets = get_user_wallets(obj)
        if not wallets.exists():
            return {
                'total_transactions': 0,
                'credit_transactions': 0,
                'debit_transactions': 0,
                'last_transaction_date': None
            }
        
        transactions = WalletTransaction.objects.filter(wallet__in=wallets)
        
        credit_count = transactions.filter(wallet_transaction_type='credit').count()
        debit_count = transactions.filter(wallet_transaction_type='debit').count()
        
        last_transaction = transactions.order_by('-created_at').first()
        
        return {
            'total_transactions': transactions.count(),
            'credit_transactions': credit_count,
            'debit_transactions': debit_count,
            'last_transaction_date': last_transaction.created_at if last_transaction else None
        }
    
    def get_withdrawal_requests(self, obj):
        """Get recent withdrawal requests"""
        wallets = get_user_wallets(obj)
        if not wallets.exists():
            return []
        
        recent_withdrawals = WalletWithdrawalRequest.objects.filter(
            wallet__in=wallets
        ).order_by('-created_at')[:5]
        
        return DesignerWithdrawalSerializer(recent_withdrawals, many=True).data


class DesignerWalletSerializer(serializers.Serializer):
    """
    Serializer for designer wallet information.
    """
    wallet_id = serializers.IntegerField(source='wallet.id', read_only=True)
    balance = serializers.DecimalField(source='wallet.balance', max_digits=10, decimal_places=2, read_only=True)
    total_earnings = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    pending_withdrawals = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    available_balance = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(source='wallet.created_at', read_only=True)
    
    def get_available_balance(self, obj):
        """Calculate available balance (current balance - pending withdrawals)"""
        balance = float(obj['wallet'].balance)
        pending = float(obj['pending_withdrawals'])
        return balance - pending


class DesignerTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for designer wallet transactions.
    """
    transaction_type_display = serializers.CharField(source='get_wallet_transaction_type_display', read_only=True)
    wallet_id = serializers.IntegerField(source='wallet.id', read_only=True)
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'wallet_transaction_type', 'transaction_type_display',
            'amount', 'description', 'reference_id', 'wallet_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = '__all__'


class DesignerWithdrawalSerializer(serializers.ModelSerializer):
    """
    Serializer for designer withdrawal requests.
    """
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    wallet_id = serializers.IntegerField(source='wallet.id', read_only=True)
    designer_name = serializers.SerializerMethodField()
    
    class Meta:
        model = WalletWithdrawalRequest
        fields = [
            'id', 'amount', 'status', 'status_display', 'wallet_id',
            'designer_name', 'created_at', 'updated_at'
        ]
        read_only_fields = '__all__'
    
    def get_designer_name(self, obj):
        """Get designer name from wallet owner"""
        try:
            return obj.wallet.created_by.get_full_name()
        except:
            return "Unknown Designer"


class DesignerStatsSerializer(serializers.Serializer):
    """
    Serializer for designer statistics and analytics.
    """
    total_designers = serializers.IntegerField()
    verified_designers = serializers.IntegerField()
    pending_designers = serializers.IntegerField()
    suspended_designers = serializers.IntegerField()
    active_designers = serializers.IntegerField()
    total_earnings = serializers.DecimalField(max_digits=15, decimal_places=2)
    pending_withdrawals = serializers.DecimalField(max_digits=15, decimal_places=2)
    recent_registrations = serializers.IntegerField()
    top_earners = serializers.ListField(child=serializers.DictField())


class DesignerSearchSerializer(serializers.Serializer):
    """
    Serializer for designer search functionality.
    """
    query = serializers.CharField(max_length=255)
    filters = serializers.DictField(required=False)
    sort_by = serializers.CharField(max_length=50, required=False)
    sort_order = serializers.CharField(max_length=10, required=False)
    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False)


# Enhanced Designer Management Serializers

class DesignerOnboardingSerializer(serializers.ModelSerializer):
    """
    Serializer for designer onboarding status.
    """
    designer_name = serializers.CharField(source='designer.get_full_name', read_only=True)
    designer_email = serializers.CharField(source='designer.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Verification details
    superadmin_verified_by_name = serializers.CharField(source='superadmin_verified_by.get_full_name', read_only=True)
    moderator_verified_by_name = serializers.CharField(source='moderator_verified_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    rejected_by_name = serializers.CharField(source='rejected_by.get_full_name', read_only=True)
    
    class Meta:
        model = DesignerOnboardingStatus
        fields = [
            'id', 'designer', 'designer_name', 'designer_email', 'status', 'status_display',
            'superadmin_verified', 'moderator_verified', 'final_approval',
            'razorpay_linked_account_id', 'razorpay_account_verified',
            'rejection_reason', 'rejected_by', 'rejected_by_name', 'rejected_at',
            'approved_by', 'approved_by_name', 'approved_at',
            'superadmin_verified_by', 'superadmin_verified_by_name', 'superadmin_verified_at',
            'moderator_verified_by', 'moderator_verified_by_name', 'moderator_verified_at',
            'bank_ifsc_code', 'bank_account_holder_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = '__all__'


class DesignerOnboardingDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for designer onboarding with sensitive information (SuperAdmin only).
    """
    designer_name = serializers.CharField(source='designer.get_full_name', read_only=True)
    designer_email = serializers.CharField(source='designer.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Verification details
    superadmin_verified_by_name = serializers.CharField(source='superadmin_verified_by.get_full_name', read_only=True)
    moderator_verified_by_name = serializers.CharField(source='moderator_verified_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    rejected_by_name = serializers.CharField(source='rejected_by.get_full_name', read_only=True)
    
    class Meta:
        model = DesignerOnboardingStatus
        fields = [
            'id', 'designer', 'designer_name', 'designer_email', 'status', 'status_display',
            'superadmin_verified', 'moderator_verified', 'final_approval',
            'razorpay_linked_account_id', 'razorpay_account_verified',
            'rejection_reason', 'rejected_by', 'rejected_by_name', 'rejected_at',
            'approved_by', 'approved_by_name', 'approved_at',
            'superadmin_verified_by', 'superadmin_verified_by_name', 'superadmin_verified_at',
            'moderator_verified_by', 'moderator_verified_by_name', 'moderator_verified_at',
            'bank_account_number', 'bank_ifsc_code', 'bank_account_holder_name',
            'contact_phone', 'contact_address', 'pan_number', 'aadhar_number',
            'created_at', 'updated_at'
        ]
        read_only_fields = '__all__'


class DesignerPayoutRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for designer payout requests.
    """
    designer_name = serializers.CharField(source='designer.get_full_name', read_only=True)
    designer_email = serializers.CharField(source='designer.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    
    class Meta:
        model = DesignerPayoutRequest
        fields = [
            'id', 'designer', 'designer_name', 'designer_email', 'amount', 'status', 'status_display',
            'scheduled_for', 'processed_at', 'razorpay_payout_id', 'razorpay_reference_id',
            'processing_notes', 'failure_reason', 'approved_by', 'approved_by_name', 'approved_at',
            'celery_task_id', 'created_at', 'updated_at'
        ]
        read_only_fields = '__all__'


class DesignerAccountSuspensionSerializer(serializers.ModelSerializer):
    """
    Serializer for designer account suspensions.
    """
    designer_name = serializers.CharField(source='designer.get_full_name', read_only=True)
    designer_email = serializers.CharField(source='designer.email', read_only=True)
    suspension_reason_display = serializers.CharField(source='get_suspension_reason_display', read_only=True)
    deletion_reason_display = serializers.CharField(source='get_deletion_reason_display', read_only=True)
    suspended_by_name = serializers.CharField(source='suspended_by.get_full_name', read_only=True)
    deleted_by_name = serializers.CharField(source='deleted_by.get_full_name', read_only=True)
    
    class Meta:
        model = DesignerAccountSuspension
        fields = [
            'id', 'designer', 'designer_name', 'designer_email',
            'is_suspended', 'is_deleted', 'suspension_reason', 'suspension_reason_display',
            'suspension_notes', 'suspended_by', 'suspended_by_name', 'suspended_at',
            'deletion_reason', 'deletion_reason_display', 'deletion_notes',
            'deleted_by', 'deleted_by_name', 'deleted_at',
            'ip_address', 'user_agent', 'created_at', 'updated_at'
        ]
        read_only_fields = '__all__'


class DesignerNotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for designer notifications.
    """
    designer_name = serializers.CharField(source='designer.get_full_name', read_only=True)
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    
    class Meta:
        model = DesignerNotification
        fields = [
            'id', 'designer_id', 'designer_name', 'notification_type', 'notification_type_display',
            'title', 'message', 'priority', 'email_sent', 'email_sent_at', 'push_sent', 'push_sent_at',
            'is_read', 'read_at', 'created_at', 'scheduled_at', 'is_scheduled'
        ]
        read_only_fields = [
            'id', 'designer_id', 'designer_name', 'notification_type', 'notification_type_display',
            'title', 'message', 'priority', 'email_sent', 'email_sent_at', 'push_sent', 'push_sent_at',
            'is_read', 'read_at', 'created_at', 'scheduled_at', 'is_scheduled'
        ]


class DesignerOnboardingVerificationSerializer(serializers.Serializer):
    """
    Serializer for designer onboarding verification.
    """
    verification_type = serializers.ChoiceField(choices=[
        ('superadmin', 'Super Admin Verification'),
        ('moderator', 'Moderator Verification'),
        ('final_approval', 'Final Approval'),
        ('reject', 'Reject Onboarding')
    ])
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    rejection_reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate(self, data):
        verification_type = data.get('verification_type')
        rejection_reason = data.get('rejection_reason')
        
        if verification_type == 'reject' and not rejection_reason:
            raise serializers.ValidationError("Rejection reason is required when rejecting onboarding.")
        
        return data


class DesignerPayoutProcessSerializer(serializers.Serializer):
    """
    Serializer for processing designer payouts.
    """
    payout_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of payout request IDs to process"
    )
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)
    processing_notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_payout_ids(self, value):
        """Validate that payout IDs exist and can be processed"""
        if not value:
            raise serializers.ValidationError("At least one payout ID is required.")
        
        # Check if all payout IDs exist
        existing_payouts = DesignerPayoutRequest.objects.filter(id__in=value)
        if existing_payouts.count() != len(value):
            raise serializers.ValidationError("One or more payout IDs do not exist.")
        
        # Check if all payouts can be processed
        for payout in existing_payouts:
            if not payout.can_be_processed():
                raise serializers.ValidationError(f"Payout {payout.id} cannot be processed.")
        
        return value


class DesignerAccountActionSerializer(serializers.Serializer):
    """
    Serializer for designer account actions (suspend/delete).
    """
    action = serializers.ChoiceField(choices=[
        ('suspend', 'Suspend Account'),
        ('delete', 'Delete Account')
    ])
    reason = serializers.ChoiceField(choices=DesignerAccountSuspension.SUSPENSION_REASON_CHOICES)
    notes = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    def validate(self, data):
        action = data.get('action')
        reason = data.get('reason')
        notes = data.get('notes', '')
        
        if action in ['suspend', 'delete'] and not notes.strip():
            raise serializers.ValidationError("Notes are required for account actions.")
        
        return data


class DesignerWalletSummarySerializer(serializers.Serializer):
    """
    Serializer for designer wallet summary.
    """
    wallet_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    pending_payout = serializers.DecimalField(max_digits=10, decimal_places=2)
    available_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    razorpay_account_verified = serializers.BooleanField()
    can_request_payout = serializers.BooleanField()


class DesignerOnboardingListSerializer(serializers.ModelSerializer):
    """
    Serializer for designer onboarding list view.
    """
    designer_name = serializers.CharField(source='designer.get_full_name', read_only=True)
    designer_email = serializers.CharField(source='designer.email', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    verification_progress = serializers.SerializerMethodField()
    
    class Meta:
        model = DesignerOnboardingStatus
        fields = [
            'id', 'designer', 'designer_name', 'designer_email', 'status', 'status_display',
            'superadmin_verified', 'moderator_verified', 'final_approval',
            'razorpay_account_verified', 'verification_progress',
            'created_at', 'updated_at'
        ]
        read_only_fields = '__all__'
    
    def get_verification_progress(self, obj):
        """Calculate verification progress percentage"""
        progress = 0
        if obj.superadmin_verified:
            progress += 50
        if obj.moderator_verified:
            progress += 50
        return progress


class DesignProcessingTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for DesignProcessingTask model.
    """
    progress_percentage = serializers.ReadOnlyField()
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = DesignProcessingTask
        fields = [
            'id', 'user', 'zip_file_path', 'total_designs', 'processed_designs',
            'failed_designs', 'status', 'error_message', 'progress_percentage',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'total_designs', 'processed_designs', 'failed_designs',
            'status', 'error_message', 'progress_percentage', 'created_at', 'updated_at'
        ]
