from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Plan, Subscription
from Accounts.serializers import UserSerializer


class PlanSerializer(serializers.ModelSerializer):
    """
    Serializer for Plan model with full CRUD operations.
    Handles plan creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    subscriptions_count = serializers.SerializerMethodField()
    plan_name_display = serializers.CharField(source='get_plan_name_display', read_only=True)
    
    class Meta:
        model = Plan
        fields = [
            'id', 'plan_name', 'plan_name_display', 'description', 'price', 'plan_duration', 'status',
            'discount', 'custom_design_hour', 'mock_pdf_count', 'no_of_free_downloads',
            'is_most_popular',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'subscriptions_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_subscriptions_count(self, obj):
        """
        Get count of active subscriptions for this plan.
        """
        return obj.subscriptions.filter(status='active').count()
    
    def validate_price(self, value):
        """
        Validate price is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Price must be positive.")
        return value
    
    def validate_description(self, value):
        """
        Validate description is not empty.
        """
        if not value:
            raise serializers.ValidationError("Description cannot be empty.")
        return value
    
    def validate_discount(self, value):
        """Validate discount is between 0 and 100."""
        if value < 0 or value > 100:
            raise serializers.ValidationError("Discount must be between 0 and 100.")
        return value
    
    def validate_custom_design_hour(self, value):
        """Validate custom design hour is positive."""
        if value <= 0:
            raise serializers.ValidationError("Custom design hour must be positive.")
        return value
    
    def validate_mock_pdf_count(self, value):
        """Validate mock PDF count is non-negative."""
        if value < 0:
            raise serializers.ValidationError("Mock PDF count cannot be negative.")
        return value
    
    def validate_no_of_free_downloads(self, value):
        """Validate free downloads count is non-negative."""
        if value < 0:
            raise serializers.ValidationError("Number of free downloads cannot be negative.")
        return value
    
    def validate(self, attrs):
        """
        Validate business logic for plans.
        """
        plan_name = attrs.get('plan_name')
        plan_duration = attrs.get('plan_duration')
        
        # Check for duplicate plan name and duration combination
        if Plan.objects.filter(
            plan_name=plan_name, 
            plan_duration=plan_duration
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Plan with this name and duration already exists.")
        
        return attrs


class PlanListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Plan model used in list views.
    """
    subscriptions_count = serializers.SerializerMethodField()
    plan_name_display = serializers.CharField(source='get_plan_name_display', read_only=True)
    
    class Meta:
        model = Plan
        fields = [
            'id', 'plan_name', 'plan_name_display', 'description', 'price', 'plan_duration', 
            'status', 'discount', 'custom_design_hour', 'mock_pdf_count', 'no_of_free_downloads',
            'created_at', 'subscriptions_count'
        ]
    
    def get_subscriptions_count(self, obj):
        """
        Get count of active subscriptions for this plan.
        """
        return obj.subscriptions.filter(status='active').count()


class PlanCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating plans with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Plan
        fields = ['plan_name', 'description', 'price', 'plan_duration', 'discount', 'custom_design_hour', 'mock_pdf_count', 'no_of_free_downloads', 'created_by_id']
    
    def validate_price(self, value):
        """
        Validate price is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Price must be positive.")
        return value


class PlanUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating plans with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Plan
        fields = ['description', 'price', 'status', 'discount', 'custom_design_hour', 'mock_pdf_count', 'no_of_free_downloads', 'updated_by_id']
    
    def validate_price(self, value):
        """
        Validate price is positive.
        """
        if value is not None and value <= 0:
            raise serializers.ValidationError("Price must be positive.")
        return value


class SubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for Subscription model with full CRUD operations.
    Handles subscription creation, updates, and management.
    """
    plan = PlanSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    plan_id = serializers.IntegerField(write_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    # Add usage tracking fields
    free_downloads_used = serializers.IntegerField(read_only=True)
    mock_pdf_downloads_used = serializers.IntegerField(read_only=True)
    remaining_free_downloads = serializers.SerializerMethodField()
    remaining_mock_pdf_downloads = serializers.SerializerMethodField()
    
    # Monthly period fields for annual plans
    current_period_downloads_used = serializers.SerializerMethodField()
    current_period_downloads_allowed = serializers.SerializerMethodField()
    current_period_remaining = serializers.SerializerMethodField()
    current_period_start = serializers.SerializerMethodField()
    current_period_end = serializers.SerializerMethodField()
    next_period_reset_date = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'plan_id', 'status', 'auto_renew',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id',
            'free_downloads_used', 'mock_pdf_downloads_used',
            'remaining_free_downloads', 'remaining_mock_pdf_downloads',
            'current_period_downloads_used', 'current_period_downloads_allowed',
            'current_period_remaining', 'current_period_start', 'current_period_end',
            'next_period_reset_date'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_remaining_free_downloads(self, obj):
        """Get remaining free downloads."""
        return obj.get_remaining_free_downloads()
    
    def get_remaining_mock_pdf_downloads(self, obj):
        """Get remaining mock PDF downloads."""
        return obj.get_remaining_mock_pdf_downloads()
    
    def get_current_period_downloads_used(self, obj):
        """Get downloads used in current period (for annual plans only)."""
        if obj.plan.plan_duration == 'annually':
            return obj.get_current_period_downloads_used()
        return None
    
    def get_current_period_downloads_allowed(self, obj):
        """Get monthly download limit (for annual plans only)."""
        if obj.plan.plan_duration == 'annually':
            return obj.get_monthly_download_limit()
        return None
    
    def get_current_period_remaining(self, obj):
        """Get remaining downloads in current period (for annual plans only)."""
        if obj.plan.plan_duration == 'annually':
            return obj.get_remaining_monthly_downloads()
        return None
    
    def get_current_period_start(self, obj):
        """Get current period start date (for annual plans only)."""
        if obj.plan.plan_duration == 'annually':
            period_start, _ = obj.get_current_settlement_period()
            return period_start.strftime('%Y-%m-%d') if period_start else None
        return None
    
    def get_current_period_end(self, obj):
        """Get current period end date (for annual plans only)."""
        if obj.plan.plan_duration == 'annually':
            _, period_end = obj.get_current_settlement_period()
            return period_end.strftime('%Y-%m-%d') if period_end else None
        return None
    
    def get_next_period_reset_date(self, obj):
        """Get next period reset date (for annual plans only)."""
        if obj.plan.plan_duration == 'annually':
            _, period_end = obj.get_current_settlement_period()
            return period_end.strftime('%Y-%m-%d') if period_end else None
        return None
    
    def validate_plan_id(self, value):
        """
        Validate that plan exists and is active.
        """
        try:
            plan = Plan.objects.get(id=value)
            if plan.status != 'active':
                raise serializers.ValidationError("Plan is not active.")
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Plan does not exist.")
        return value
    
    def validate(self, attrs):
        """
        Validate business logic for subscriptions.
        """
        plan_id = attrs.get('plan_id')
        created_by_id = attrs.get('created_by_id')
        
        # Check for existing active subscription for the same plan
        if created_by_id and plan_id:
            existing_subscription = Subscription.objects.filter(
                plan_id=plan_id,
                created_by_id=created_by_id,
                status='active'
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_subscription.exists():
                raise serializers.ValidationError("Active subscription already exists for this plan.")
        
        return attrs


class SubscriptionListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Subscription model used in list views.
    """
    plan = PlanListSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'status', 'auto_renew', 'created_by', 'created_at'
        ]


class SubscriptionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating subscriptions with minimal required fields.
    """
    plan_id = serializers.IntegerField()
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Subscription
        fields = ['plan_id', 'auto_renew', 'created_by_id']
    
    def validate_plan_id(self, value):
        """
        Validate that plan exists and is active.
        """
        try:
            plan = Plan.objects.get(id=value)
            if plan.status != 'active':
                raise serializers.ValidationError("Plan is not active.")
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Plan does not exist.")
        return value


class SubscriptionUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating subscriptions with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Subscription
        fields = ['status', 'auto_renew', 'updated_by_id']


class SubscriptionStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating subscription status.
    """
    status = serializers.ChoiceField(choices=Subscription.STATUS_CHOICES)
    updated_by_id = serializers.IntegerField(required=False)
    
    def validate_status(self, value):
        """
        Validate status transition is allowed.
        """
        # Add business logic for status transitions here
        # For example, prevent moving from 'expired' to 'active'
        return value


class PlanSearchSerializer(serializers.Serializer):
    """
    Serializer for plan search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    plan_name = serializers.ChoiceField(
        choices=Plan.PLAN_NAME_CHOICES,
        required=False
    )
    plan_duration = serializers.ChoiceField(
        choices=Plan.DURATION_CHOICES,
        required=False
    )
    status = serializers.ChoiceField(
        choices=Plan.STATUS_CHOICES,
        required=False
    )
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        min_price = attrs.get('min_price')
        max_price = attrs.get('max_price')
        
        if min_price is not None and max_price is not None:
            if min_price > max_price:
                raise serializers.ValidationError("Min price cannot be greater than max price.")
        
        return attrs


class SubscriptionSearchSerializer(serializers.Serializer):
    """
    Serializer for subscription search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    status = serializers.ChoiceField(
        choices=Subscription.STATUS_CHOICES,
        required=False
    )
    plan_id = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
    auto_renew = serializers.BooleanField(required=False)
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


class PlanFilterSerializer(serializers.Serializer):
    """
    Serializer for plan filtering functionality.
    """
    plan_names = serializers.ListField(
        child=serializers.ChoiceField(choices=Plan.PLAN_NAME_CHOICES),
        required=False
    )
    plan_durations = serializers.ListField(
        child=serializers.ChoiceField(choices=Plan.DURATION_CHOICES),
        required=False
    )
    statuses = serializers.ListField(
        child=serializers.ChoiceField(choices=Plan.STATUS_CHOICES),
        required=False
    )
    price_range = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2),
        required=False
    )
    
    def validate_price_range(self, value):
        """
        Validate price range format.
        """
        if value:
            if 'min' not in value or 'max' not in value:
                raise serializers.ValidationError("Price range must have 'min' and 'max' keys.")
            if value['min'] > value['max']:
                raise serializers.ValidationError("Min price cannot be greater than max price.")
        return value


class SubscriptionFilterSerializer(serializers.Serializer):
    """
    Serializer for subscription filtering functionality.
    """
    statuses = serializers.ListField(
        child=serializers.ChoiceField(choices=Subscription.STATUS_CHOICES),
        required=False
    )
    plan_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    auto_renew = serializers.BooleanField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)


class PlanAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for plan analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['plan_name', 'plan_duration', 'status'],
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


class SubscriptionAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for subscription analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['status', 'plan', 'created_by'],
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


class BulkPlanUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk plan updates.
    """
    plan_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_plan_ids(self, value):
        """
        Validate that all plans exist.
        """
        existing_plans = Plan.objects.filter(id__in=value).count()
        if existing_plans != len(value):
            raise serializers.ValidationError("One or more plans do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['status', 'price']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class BulkSubscriptionUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk subscription updates.
    """
    subscription_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_subscription_ids(self, value):
        """
        Validate that all subscriptions exist.
        """
        existing_subscriptions = Subscription.objects.filter(id__in=value).count()
        if existing_subscriptions != len(value):
            raise serializers.ValidationError("One or more subscriptions do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['status', 'auto_renew']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class PlanComparisonSerializer(serializers.Serializer):
    """
    Serializer for comparing multiple plans.
    """
    plan_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    
    def validate_plan_ids(self, value):
        """
        Validate that all plans exist.
        """
        existing_plans = Plan.objects.filter(id__in=value).count()
        if existing_plans != len(value):
            raise serializers.ValidationError("One or more plans do not exist.")
        return value


class SubscriptionRenewalSerializer(serializers.Serializer):
    """
    Serializer for subscription renewal process.
    """
    subscription_id = serializers.IntegerField()
    renew_by_id = serializers.IntegerField(required=False)
    
    def validate_subscription_id(self, value):
        """
        Validate that subscription exists and is active.
        """
        try:
            subscription = Subscription.objects.get(id=value)
            if subscription.status != 'active':
                raise serializers.ValidationError("Subscription is not active.")
        except Subscription.DoesNotExist:
            raise serializers.ValidationError("Subscription does not exist.")
        return value


class PlanRecommendationSerializer(serializers.Serializer):
    """
    Serializer for plan recommendation based on user preferences.
    """
    user_id = serializers.IntegerField(required=False)
    budget = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    duration_preference = serializers.ChoiceField(
        choices=Plan.DURATION_CHOICES,
        required=False
    )
    features_required = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False
    )
    
    def validate_budget(self, value):
        """
        Validate budget is positive.
        """
        if value is not None and value <= 0:
            raise serializers.ValidationError("Budget must be positive.")
        return value
from django.contrib.auth.models import User
from Plans.models import Plan, Subscription
from Accounts.serializers import UserSerializer


class SubscriptionPlanListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing subscription plans in admin panel.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    subscriptions_count = serializers.SerializerMethodField()
    active_subscriptions_count = serializers.SerializerMethodField()
    revenue_generated = serializers.SerializerMethodField()
    
    class Meta:
        model = Plan
        fields = [
            'id', 'plan_name', 'description', 'price', 'plan_duration', 'status',
            'discount', 'custom_design_hour', 'mock_pdf_count', 'no_of_free_downloads',
            'is_most_popular',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'subscriptions_count', 'active_subscriptions_count', 'revenue_generated'
        ]
    
    def get_subscriptions_count(self, obj):
        """Get total count of subscriptions for this plan."""
        return obj.subscriptions.count()
    
    def get_active_subscriptions_count(self, obj):
        """Get count of active subscriptions for this plan."""
        return obj.subscriptions.filter(status='active').count()
    
    def get_revenue_generated(self, obj):
        """Get total revenue generated from this plan."""
        active_subscriptions = obj.subscriptions.filter(status='active')
        total_revenue = sum(subscription.plan.price for subscription in active_subscriptions)
        return float(total_revenue)


class SubscriptionPlanDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed subscription plan information in admin panel.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    subscriptions_count = serializers.SerializerMethodField()
    active_subscriptions_count = serializers.SerializerMethodField()
    cancelled_subscriptions_count = serializers.SerializerMethodField()
    expired_subscriptions_count = serializers.SerializerMethodField()
    revenue_generated = serializers.SerializerMethodField()
    recent_subscriptions = serializers.SerializerMethodField()
    
    class Meta:
        model = Plan
        fields = [
            'id', 'plan_name', 'description', 'price', 'plan_duration', 'status',
            'discount', 'custom_design_hour', 'mock_pdf_count', 'no_of_free_downloads',
            'is_most_popular',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'subscriptions_count', 'active_subscriptions_count', 'cancelled_subscriptions_count',
            'expired_subscriptions_count', 'revenue_generated', 'recent_subscriptions'
        ]
    
    def get_subscriptions_count(self, obj):
        """Get total count of subscriptions for this plan."""
        return obj.subscriptions.count()
    
    def get_active_subscriptions_count(self, obj):
        """Get count of active subscriptions for this plan."""
        return obj.subscriptions.filter(status='active').count()
    
    def get_cancelled_subscriptions_count(self, obj):
        """Get count of cancelled subscriptions for this plan."""
        return obj.subscriptions.filter(status='cancelled').count()
    
    def get_expired_subscriptions_count(self, obj):
        """Get count of expired subscriptions for this plan."""
        return obj.subscriptions.filter(status='expired').count()
    
    def get_revenue_generated(self, obj):
        """Get total revenue generated from this plan."""
        active_subscriptions = obj.subscriptions.filter(status='active')
        total_revenue = sum(subscription.plan.price for subscription in active_subscriptions)
        return float(total_revenue)
    
    def get_recent_subscriptions(self, obj):
        """Get recent subscriptions for this plan."""
        recent_subscriptions = obj.subscriptions.order_by('-created_at')[:5]
        return SubscriptionListSerializer(recent_subscriptions, many=True).data


class SubscriptionListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for subscription list views.
    """
    plan = serializers.SerializerMethodField()
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'status', 'auto_renew', 'created_by', 'created_at'
        ]
    
    def get_plan(self, obj):
        """Get plan information."""
        return {
            'id': obj.plan.id,
            'plan_name': obj.plan.plan_name,
            'plan_duration': obj.plan.plan_duration,
            'price': float(obj.plan.price)
        }


class SubscriptionPlanCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating subscription plans.
    Allows creating a plan with same name and duration if existing plan is inactive.
    """
    created_by_id = serializers.IntegerField(required=False)
    discount = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    custom_design_hour = serializers.IntegerField(required=False, allow_null=True)
    mock_pdf_count = serializers.IntegerField(required=False, allow_null=True)
    no_of_free_downloads = serializers.IntegerField(required=False, allow_null=True)
    
    class Meta:
        model = Plan
        fields = [
            'plan_name', 'description', 'price', 'plan_duration', 
            'discount', 'custom_design_hour', 'mock_pdf_count', 'no_of_free_downloads',
            'is_most_popular',
            'created_by_id'
        ]
    
    def validate_price(self, value):
        """Validate price is positive."""
        if value <= 0:
            raise serializers.ValidationError("Price must be positive.")
        return value
    
    def validate_description(self, value):
        """Validate description is not empty."""
        if not value:
            raise serializers.ValidationError("Description cannot be empty.")
        return value
    
    def validate_discount(self, value):
        """Validate discount is between 0 and 100."""
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Discount must be between 0 and 100.")
        return value if value is not None else 0
    
    def validate_custom_design_hour(self, value):
        """Validate custom design hour is positive."""
        if value is not None and value <= 0:
            raise serializers.ValidationError("Custom design hour must be positive.")
        return value
    
    def validate_mock_pdf_count(self, value):
        """Validate mock PDF count is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Mock PDF count cannot be negative.")
        return value if value is not None else 0
    
    def validate_no_of_free_downloads(self, value):
        """Validate free downloads count is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Number of free downloads cannot be negative.")
        return value if value is not None else 0
    
    def update(self, instance, validated_data):
        """
        Update plan and handle is_most_popular logic.
        If marking as popular, unmark other plans of the same duration.
        """
        is_most_popular = validated_data.get('is_most_popular')
        plan_duration = instance.plan_duration
        
        # If marking as popular, unmark other plans of the same duration
        if is_most_popular is True and plan_duration:
            Plan.objects.filter(
                plan_duration=plan_duration,
                is_most_popular=True
            ).exclude(id=instance.id).update(is_most_popular=False)
        
        return super().update(instance, validated_data)
    
    def validate(self, attrs):
        """
        Validate that plan_name and plan_duration combination is unique for active plans.
        Allow creation if existing plan with same name and duration is inactive.
        """
        plan_name = attrs.get('plan_name')
        plan_duration = attrs.get('plan_duration')
        
        if plan_name and plan_duration:
            # Check if a plan with same name and duration exists
            existing_plan = Plan.objects.filter(
                plan_name=plan_name,
                plan_duration=plan_duration
            ).first()
            
            if existing_plan:
                # If existing plan is active, prevent creation
                if existing_plan.status == 'active':
                    raise serializers.ValidationError({
                        'non_field_errors': [
                            f'A plan with name "{existing_plan.get_plan_name_display()}" and duration "{existing_plan.get_plan_duration_display()}" already exists and is active. Please deactivate the existing plan first or choose a different combination.'
                        ]
                    })
                # If existing plan is inactive, we'll update it instead of creating new one
                # This will be handled in the view
        
        return attrs
    
    def create(self, validated_data):
        """
        Create plan and handle is_most_popular logic.
        If marking as popular, unmark other plans of the same duration.
        """
        is_most_popular = validated_data.get('is_most_popular', False)
        plan_duration = validated_data.get('plan_duration')
        
        # If marking as popular, unmark other plans of the same duration
        if is_most_popular and plan_duration:
            Plan.objects.filter(
                plan_duration=plan_duration,
                is_most_popular=True
            ).exclude(
                plan_name=validated_data.get('plan_name'),
                plan_duration=plan_duration
            ).update(is_most_popular=False)
        
        return super().create(validated_data)


class SubscriptionPlanUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating subscription plans.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Plan
        fields = [
            'description', 'price', 'status',
            'discount', 'custom_design_hour', 'mock_pdf_count', 'no_of_free_downloads',
            'is_most_popular',
            'updated_by_id'
        ]
    
    def validate_price(self, value):
        """Validate price is positive."""
        if value is not None and value <= 0:
            raise serializers.ValidationError("Price must be positive.")
        return value
    
    def validate_status(self, value):
        """Validate status change."""
        if self.instance and self.instance.status == 'inactive' and value == 'active':
            # Check if there are any active subscriptions
            active_subscriptions = self.instance.subscriptions.filter(status='active').count()
            if active_subscriptions > 0:
                raise serializers.ValidationError("Cannot activate plan with active subscriptions. Please contact support.")
        return value
    
    def validate_discount(self, value):
        """Validate discount is between 0 and 100."""
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Discount must be between 0 and 100.")
        return value
    
    def validate_custom_design_hour(self, value):
        """Validate custom design hour is positive."""
        if value is not None and value <= 0:
            raise serializers.ValidationError("Custom design hour must be positive.")
        return value
    
    def validate_mock_pdf_count(self, value):
        """Validate mock PDF count is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Mock PDF count cannot be negative.")
        return value
    
    def validate_no_of_free_downloads(self, value):
        """Validate free downloads count is non-negative."""
        if value is not None and value < 0:
            raise serializers.ValidationError("Number of free downloads cannot be negative.")
        return value
    
    def update(self, instance, validated_data):
        """
        Update plan and handle is_most_popular logic.
        If marking as popular, unmark other plans of the same duration.
        """
        is_most_popular = validated_data.get('is_most_popular')
        plan_duration = instance.plan_duration
        
        # If marking as popular, unmark other plans of the same duration
        if is_most_popular is True and plan_duration:
            Plan.objects.filter(
                plan_duration=plan_duration,
                is_most_popular=True
            ).exclude(id=instance.id).update(is_most_popular=False)
        
        return super().update(instance, validated_data)


class SubscriptionPlanDeactivateSerializer(serializers.Serializer):
    """
    Serializer for deactivating subscription plans.
    All fields are optional - plan can be deactivated without any additional data.
    """
    deactivation_reason = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    notify_customers = serializers.BooleanField(required=False, default=True)
    admin_notes = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)
    
    def validate_deactivation_reason(self, value):
        """Validate deactivation reason."""
        # If value is provided, it must not be empty
        if value and isinstance(value, str) and value.strip():
            return value.strip()
        # If value is None or empty, return empty string (field is optional)
        return ''
    
    def validate(self, attrs):
        """Ensure defaults are set if fields are not provided."""
        # Set defaults if not provided
        if 'notify_customers' not in attrs:
            attrs['notify_customers'] = True
        if 'deactivation_reason' not in attrs or not attrs.get('deactivation_reason'):
            attrs['deactivation_reason'] = ''
        if 'admin_notes' not in attrs or not attrs.get('admin_notes'):
            attrs['admin_notes'] = ''
        return attrs


class SubscriptionPlanFilterSerializer(serializers.Serializer):
    """
    Serializer for filtering subscription plans.
    """
    plan_name = serializers.ChoiceField(
        choices=Plan.PLAN_NAME_CHOICES,
        required=False
    )
    plan_duration = serializers.ChoiceField(
        choices=Plan.DURATION_CHOICES,
        required=False
    )
    status = serializers.ChoiceField(
        choices=Plan.STATUS_CHOICES,
        required=False
    )
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    has_subscriptions = serializers.BooleanField(required=False)
    search = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, attrs):
        """Validate filter parameters."""
        min_price = attrs.get('min_price')
        max_price = attrs.get('max_price')
        
        if min_price is not None and max_price is not None:
            if min_price > max_price:
                raise serializers.ValidationError("Min price cannot be greater than max price.")
        
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        return attrs


class SubscriptionPlanAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for subscription plan analytics.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['plan_name', 'plan_duration', 'status', 'month', 'year'],
        required=False
    )
    
    def validate(self, attrs):
        """Validate analytics parameters."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class PromotionalOfferSerializer(serializers.Serializer):
    """
    Serializer for promotional offers and discounts.
    """
    plan_id = serializers.IntegerField()
    offer_name = serializers.CharField(max_length=200)
    discount_type = serializers.ChoiceField(
        choices=[('percentage', 'Percentage'), ('fixed', 'Fixed Amount')]
    )
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    start_date = serializers.DateTimeField()
    end_date = serializers.DateTimeField()
    max_uses = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_discount_value(self, value):
        """Validate discount value."""
        if value <= 0:
            raise serializers.ValidationError("Discount value must be positive.")
        return value
    
    def validate(self, attrs):
        """Validate promotional offer data."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        discount_type = attrs.get('discount_type')
        discount_value = attrs.get('discount_value')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        if discount_type == 'percentage' and discount_value > 100:
            raise serializers.ValidationError("Percentage discount cannot exceed 100%.")
        
        return attrs


class BulkPlanUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk plan updates.
    """
    plan_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    admin_notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_plan_ids(self, value):
        """Validate that all plans exist."""
        existing_plans = Plan.objects.filter(id__in=value).count()
        if existing_plans != len(value):
            raise serializers.ValidationError("One or more plans do not exist.")
        return value
    
    def validate_updates(self, value):
        """Validate update fields."""
        allowed_fields = ['status', 'price', 'description']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        
        if 'price' in value and value['price'] <= 0:
            raise serializers.ValidationError("Price must be positive.")
        
        return value


class PlanComparisonSerializer(serializers.Serializer):
    """
    Serializer for comparing multiple plans.
    """
    plan_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    
    def validate_plan_ids(self, value):
        """Validate that all plans exist."""
        existing_plans = Plan.objects.filter(id__in=value).count()
        if existing_plans != len(value):
            raise serializers.ValidationError("One or more plans do not exist.")
        return value


class SubscriptionPlanStatsSerializer(serializers.Serializer):
    """
    Serializer for subscription plan statistics.
    """
    total_plans = serializers.IntegerField()
    active_plans = serializers.IntegerField()
    inactive_plans = serializers.IntegerField()
    total_subscriptions = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    average_plan_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    most_popular_plan = serializers.DictField()
    revenue_by_plan = serializers.DictField()


class PlanRecommendationSerializer(serializers.Serializer):
    """
    Serializer for plan recommendations.
    """
    user_id = serializers.IntegerField(required=False)
    budget = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    duration_preference = serializers.ChoiceField(
        choices=Plan.DURATION_CHOICES,
        required=False
    )
    features_required = serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False
    )
    
    def validate_budget(self, value):
        """Validate budget is positive."""
        if value is not None and value <= 0:
            raise serializers.ValidationError("Budget must be positive.")
        return value


class SubscriptionPlanExportSerializer(serializers.Serializer):
    """
    Serializer for exporting subscription plans data.
    """
    format = serializers.ChoiceField(choices=[('csv', 'CSV'), ('excel', 'Excel'), ('pdf', 'PDF')])
    include_subscriptions = serializers.BooleanField(default=True)
    include_analytics = serializers.BooleanField(default=False)
    date_range = serializers.DictField(required=False)
    
    def validate_date_range(self, value):
        """Validate date range."""
        if value:
            if 'start_date' not in value or 'end_date' not in value:
                raise serializers.ValidationError("Date range must have 'start_date' and 'end_date' keys.")
            
            from datetime import datetime
            try:
                start_date = datetime.fromisoformat(value['start_date'].replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(value['end_date'].replace('Z', '+00:00'))
                
                if start_date >= end_date:
                    raise serializers.ValidationError("Start date must be before end date.")
            except ValueError:
                raise serializers.ValidationError("Invalid date format.")
        
        return value
