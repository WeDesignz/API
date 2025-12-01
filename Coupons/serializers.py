from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from .models import Coupon, CouponUsage
from Accounts.serializers import UserSerializer
from Orders.serializers import OrderSerializer


class CouponSerializer(serializers.ModelSerializer):
    """
    Serializer for Coupon model with full CRUD operations.
    Handles coupon creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    usage_count = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = Coupon
        fields = [
            'id', 'name', 'code', 'applied_to_base', 'applied_to_prime', 'applied_to_premium',
            'description', 'coupon_discount_type', 'discount_value', 'max_usage',
            'max_usage_per_user', 'min_order_value', 'start_date_time', 'end_date_time',
            'status', 'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'usage_count', 'is_valid'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_usage_count(self, obj):
        """
        Get current usage count for the coupon.
        """
        return obj.usages.count()
    
    def get_is_valid(self, obj):
        """
        Check if coupon is currently valid.
        """
        now = timezone.now()
        return (
            obj.status == 'active' and
            obj.start_date_time <= now <= obj.end_date_time
        )
    
    def validate_code(self, value):
        """
        Validate coupon code uniqueness.
        """
        if Coupon.objects.filter(code=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Coupon code already exists.")
        return value
    
    def validate_discount_value(self, value):
        """
        Validate discount value is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Discount value must be positive.")
        return value
    
    def validate_max_usage(self, value):
        """
        Validate max usage is non-negative.
        """
        if value < 0:
            raise serializers.ValidationError("Max usage cannot be negative.")
        return value
    
    def validate_max_usage_per_user(self, value):
        """
        Validate max usage per user is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Max usage per user must be positive.")
        return value
    
    def validate_min_order_value(self, value):
        """
        Validate minimum order value is non-negative.
        """
        if value < 0:
            raise serializers.ValidationError("Minimum order value cannot be negative.")
        return value
    
    def validate(self, attrs):
        """
        Validate date range and business logic.
        """
        start_date = attrs.get('start_date_time')
        end_date = attrs.get('end_date_time')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        # Validate that at least one plan type is selected
        applied_to_base = attrs.get('applied_to_base', False)
        applied_to_prime = attrs.get('applied_to_prime', False)
        applied_to_premium = attrs.get('applied_to_premium', False)
        
        if not any([applied_to_base, applied_to_prime, applied_to_premium]):
            raise serializers.ValidationError("Coupon must be applied to at least one plan type.")
        
        return attrs


class CouponListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Coupon model used in list views.
    """
    usage_count = serializers.SerializerMethodField()
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = Coupon
        fields = [
            'id', 'name', 'code', 'coupon_discount_type', 'discount_value',
            'start_date_time', 'end_date_time', 'status', 'usage_count', 'is_valid'
        ]
    
    def get_usage_count(self, obj):
        """
        Get current usage count for the coupon.
        """
        return obj.usages.count()
    
    def get_is_valid(self, obj):
        """
        Check if coupon is currently valid.
        """
        now = timezone.now()
        return (
            obj.status == 'active' and
            obj.start_date_time <= now <= obj.end_date_time
        )


class CouponUsageSerializer(serializers.ModelSerializer):
    """
    Serializer for CouponUsage model with full CRUD operations.
    Handles coupon usage tracking and management.
    """
    coupon = CouponSerializer(read_only=True)
    order = OrderSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    coupon_id = serializers.IntegerField(write_only=True)
    order_id = serializers.IntegerField(write_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = CouponUsage
        fields = [
            'id', 'coupon', 'coupon_id', 'order', 'order_id', 'discount_applied',
            'order_amount', 'created_by', 'created_at', 'created_by_id'
        ]
        read_only_fields = ['id', 'created_at']
    
    def validate_coupon_id(self, value):
        """
        Validate that coupon exists.
        """
        try:
            Coupon.objects.get(id=value)
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Coupon does not exist.")
        return value
    
    def validate_order_id(self, value):
        """
        Validate that order exists.
        """
        try:
            from Orders.models import Order
            Order.objects.get(id=value)
        except:
            raise serializers.ValidationError("Order does not exist.")
        return value
    
    def validate_discount_applied(self, value):
        """
        Validate discount applied is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Discount applied must be positive.")
        return value
    
    def validate_order_amount(self, value):
        """
        Validate order amount is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Order amount must be positive.")
        return value
    
    def validate(self, attrs):
        """
        Validate business logic for coupon usage.
        """
        discount_applied = attrs.get('discount_applied', 0)
        order_amount = attrs.get('order_amount', 0)
        
        if discount_applied > order_amount:
            raise serializers.ValidationError("Discount applied cannot be greater than order amount.")
        
        return attrs


class CouponUsageListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for CouponUsage model used in list views.
    """
    coupon = CouponListSerializer(read_only=True)
    order = OrderSerializer(read_only=True)
    
    class Meta:
        model = CouponUsage
        fields = [
            'id', 'coupon', 'order', 'discount_applied', 'order_amount', 'created_at'
        ]


class CouponValidationSerializer(serializers.Serializer):
    """
    Serializer for coupon validation process.
    """
    coupon_code = serializers.CharField(max_length=50)
    order_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    user_id = serializers.IntegerField(required=False)
    
    def validate_coupon_code(self, value):
        """
        Validate coupon code exists and is active.
        """
        try:
            coupon = Coupon.objects.get(code__iexact=value)
            if coupon.status != 'active':
                raise serializers.ValidationError("Coupon is not active.")
            
            # Check if coupon is within valid date range
            now = timezone.now()
            if not (coupon.start_date_time <= now <= coupon.end_date_time):
                raise serializers.ValidationError("Coupon is not currently valid.")
            
            return value
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Invalid coupon code.")
    
    def validate(self, attrs):
        """
        Validate coupon usage eligibility.
        """
        coupon_code = attrs.get('coupon_code')
        order_amount = attrs.get('order_amount')
        user_id = attrs.get('user_id')
        
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code)
            
            # Check minimum order value
            if order_amount < coupon.min_order_value:
                raise serializers.ValidationError(
                    f"Order amount must be at least {coupon.min_order_value} to use this coupon."
                )
            
            # Check max usage limit
            if coupon.max_usage > 0 and coupon.usages.count() >= coupon.max_usage:
                raise serializers.ValidationError("Coupon usage limit exceeded.")
            
            # Check per-user usage limit
            if user_id and coupon.max_usage_per_user > 0:
                user_usage_count = coupon.usages.filter(created_by_id=user_id).count()
                if user_usage_count >= coupon.max_usage_per_user:
                    raise serializers.ValidationError("You have already used this coupon maximum times.")
            
            attrs['coupon'] = coupon
            return attrs
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Invalid coupon code.")


class CouponApplySerializer(serializers.Serializer):
    """
    Serializer for applying coupon to an order.
    """
    coupon_code = serializers.CharField(max_length=50)
    order_id = serializers.IntegerField()
    user_id = serializers.IntegerField(required=False)
    
    def validate_coupon_code(self, value):
        """
        Validate coupon code exists and is active.
        """
        try:
            coupon = Coupon.objects.get(code__iexact=value)
            if coupon.status != 'active':
                raise serializers.ValidationError("Coupon is not active.")
            return value
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Invalid coupon code.")
    
    def validate_order_id(self, value):
        """
        Validate that order exists.
        """
        try:
            from Orders.models import Order
            Order.objects.get(id=value)
        except:
            raise serializers.ValidationError("Order does not exist.")
        return value


class CouponSearchSerializer(serializers.Serializer):
    """
    Serializer for coupon search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    status = serializers.ChoiceField(
        choices=Coupon.STATUS_CHOICES,
        required=False
    )
    discount_type = serializers.ChoiceField(
        choices=Coupon.DISCOUNT_TYPE_CHOICES,
        required=False
    )
    applied_to_base = serializers.BooleanField(required=False)
    applied_to_prime = serializers.BooleanField(required=False)
    applied_to_premium = serializers.BooleanField(required=False)
    min_discount_value = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_discount_value = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    valid_only = serializers.BooleanField(required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        min_discount = attrs.get('min_discount_value')
        max_discount = attrs.get('max_discount_value')
        
        if min_discount is not None and max_discount is not None:
            if min_discount > max_discount:
                raise serializers.ValidationError("Min discount value cannot be greater than max discount value.")
        
        return attrs


class CouponStatsSerializer(serializers.Serializer):
    """
    Serializer for coupon statistics.
    """
    coupon_id = serializers.IntegerField()
    
    def validate_coupon_id(self, value):
        """
        Validate that coupon exists.
        """
        try:
            Coupon.objects.get(id=value)
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Coupon does not exist.")
        return value


class BulkCouponUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk coupon updates.
    """
    coupon_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_coupon_ids(self, value):
        """
        Validate that all coupons exist.
        """
        existing_coupons = Coupon.objects.filter(id__in=value).count()
        if existing_coupons != len(value):
            raise serializers.ValidationError("One or more coupons do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = [
            'status', 'applied_to_base', 'applied_to_prime', 'applied_to_premium',
            'max_usage', 'max_usage_per_user', 'min_order_value'
        ]
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class CouponAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for coupon analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    coupon_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    
    def validate(self, attrs):
        """
        Validate date range.
        """
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs