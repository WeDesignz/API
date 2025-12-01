from rest_framework import serializers
from django.contrib.auth.models import User
from .models import RazorpayPayment, RazorpayWebhookEvent
from Accounts.serializers import UserSerializer
from Orders.serializers import OrderSerializer


class RazorpayPaymentSerializer(serializers.ModelSerializer):
    """
    Serializer for RazorpayPayment model with full CRUD operations.
    Handles Razorpay payment creation, updates, and management.
    """
    order = OrderSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    order_id = serializers.IntegerField(write_only=True, required=False)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = RazorpayPayment
        fields = [
            'id', 'order', 'order_id', 'razorpay_payment_id', 'razorpay_order_id',
            'amount', 'currency', 'status', 'method', 'description', 'notes',
            'fee', 'tax', 'error_code', 'error_description', 'created_by',
            'created_at', 'updated_by', 'updated_at', 'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_razorpay_payment_id(self, value):
        """
        Validate Razorpay payment ID uniqueness.
        """
        if RazorpayPayment.objects.filter(razorpay_payment_id=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Razorpay payment ID already exists.")
        return value
    
    def validate_amount(self, value):
        """
        Validate amount is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value
    
    def validate_currency(self, value):
        """
        Validate currency code format.
        """
        if len(value) != 3:
            raise serializers.ValidationError("Currency code must be 3 characters.")
        return value.upper()
    
    def validate_fee(self, value):
        """
        Validate fee is non-negative.
        """
        if value is not None and value < 0:
            raise serializers.ValidationError("Fee cannot be negative.")
        return value
    
    def validate_tax(self, value):
        """
        Validate tax is non-negative.
        """
        if value is not None and value < 0:
            raise serializers.ValidationError("Tax cannot be negative.")
        return value
    
    def validate_order_id(self, value):
        """
        Validate that order exists.
        """
        if value:
            try:
                from Orders.models import Order
                Order.objects.get(id=value)
            except:
                raise serializers.ValidationError("Order does not exist.")
        return value


class RazorpayPaymentListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for RazorpayPayment model used in list views.
    """
    order = OrderSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = RazorpayPayment
        fields = [
            'id', 'order', 'razorpay_payment_id', 'amount', 'currency',
            'status', 'method', 'created_by', 'created_at'
        ]


class RazorpayPaymentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating Razorpay payments with minimal required fields.
    """
    order_id = serializers.IntegerField(required=False)
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = RazorpayPayment
        fields = [
            'order_id', 'razorpay_payment_id', 'razorpay_order_id', 'amount',
            'currency', 'method', 'description', 'notes', 'created_by_id'
        ]
    
    def validate_razorpay_payment_id(self, value):
        """
        Validate Razorpay payment ID uniqueness.
        """
        if RazorpayPayment.objects.filter(razorpay_payment_id=value).exists():
            raise serializers.ValidationError("Razorpay payment ID already exists.")
        return value


class RazorpayPaymentUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating Razorpay payments with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = RazorpayPayment
        fields = [
            'status', 'method', 'description', 'notes', 'fee', 'tax',
            'error_code', 'error_description', 'updated_by_id'
        ]


class RazorpayPaymentStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating Razorpay payment status.
    """
    status = serializers.ChoiceField(choices=RazorpayPayment.STATUS_CHOICES)
    updated_by_id = serializers.IntegerField(required=False)
    
    def validate_status(self, value):
        """
        Validate status transition is allowed.
        """
        # Add business logic for status transitions here
        # For example, prevent moving from 'captured' to 'created'
        return value


class RazorpayWebhookEventSerializer(serializers.ModelSerializer):
    """
    Serializer for RazorpayWebhookEvent model with full CRUD operations.
    Handles webhook event creation, updates, and management.
    """
    payment = RazorpayPaymentSerializer(read_only=True)
    payment_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = RazorpayWebhookEvent
        fields = [
            'id', 'event_id', 'event_type', 'payment', 'payment_id',
            'payload', 'processed', 'processed_at', 'error_message',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_event_id(self, value):
        """
        Validate event ID uniqueness.
        """
        if RazorpayWebhookEvent.objects.filter(event_id=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Event ID already exists.")
        return value
    
    def validate_payment_id(self, value):
        """
        Validate that payment exists.
        """
        if value:
            try:
                RazorpayPayment.objects.get(id=value)
            except RazorpayPayment.DoesNotExist:
                raise serializers.ValidationError("Payment does not exist.")
        return value


class RazorpayWebhookEventListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for RazorpayWebhookEvent model used in list views.
    """
    payment = RazorpayPaymentListSerializer(read_only=True)
    
    class Meta:
        model = RazorpayWebhookEvent
        fields = [
            'id', 'event_id', 'event_type', 'payment', 'processed',
            'processed_at', 'created_at'
        ]


class RazorpayWebhookEventCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating webhook events with minimal required fields.
    """
    payment_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = RazorpayWebhookEvent
        fields = [
            'event_id', 'event_type', 'payment_id', 'payload'
        ]
    
    def validate_event_id(self, value):
        """
        Validate event ID uniqueness.
        """
        if RazorpayWebhookEvent.objects.filter(event_id=value).exists():
            raise serializers.ValidationError("Event ID already exists.")
        return value


class RazorpayWebhookEventUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating webhook events with selective field updates.
    """
    class Meta:
        model = RazorpayWebhookEvent
        fields = ['processed', 'processed_at', 'error_message']


class RazorpayPaymentSearchSerializer(serializers.Serializer):
    """
    Serializer for Razorpay payment search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    status = serializers.ChoiceField(
        choices=RazorpayPayment.STATUS_CHOICES,
        required=False
    )
    method = serializers.CharField(max_length=50, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    min_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    order_id = serializers.IntegerField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        min_amount = attrs.get('min_amount')
        max_amount = attrs.get('max_amount')
        
        if min_amount is not None and max_amount is not None:
            if min_amount > max_amount:
                raise serializers.ValidationError("Min amount cannot be greater than max amount.")
        
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        return attrs


class RazorpayWebhookEventSearchSerializer(serializers.Serializer):
    """
    Serializer for webhook event search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    event_type = serializers.ChoiceField(
        choices=RazorpayWebhookEvent.EVENT_TYPES,
        required=False
    )
    processed = serializers.BooleanField(required=False)
    payment_id = serializers.IntegerField(required=False)
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


class RazorpayPaymentFilterSerializer(serializers.Serializer):
    """
    Serializer for Razorpay payment filtering functionality.
    """
    statuses = serializers.ListField(
        child=serializers.ChoiceField(choices=RazorpayPayment.STATUS_CHOICES),
        required=False
    )
    methods = serializers.ListField(
        child=serializers.CharField(max_length=50),
        required=False
    )
    currencies = serializers.ListField(
        child=serializers.CharField(max_length=3),
        required=False
    )
    amount_range = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    order_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    
    def validate_amount_range(self, value):
        """
        Validate amount range format.
        """
        if value:
            if 'min' not in value or 'max' not in value:
                raise serializers.ValidationError("Amount range must have 'min' and 'max' keys.")
            if value['min'] > value['max']:
                raise serializers.ValidationError("Min amount cannot be greater than max amount.")
        return value


class RazorpayWebhookEventFilterSerializer(serializers.Serializer):
    """
    Serializer for webhook event filtering functionality.
    """
    event_types = serializers.ListField(
        child=serializers.ChoiceField(choices=RazorpayWebhookEvent.EVENT_TYPES),
        required=False
    )
    processed = serializers.BooleanField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    payment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )


class RazorpayPaymentAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for Razorpay payment analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['status', 'method', 'currency', 'created_by'],
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


class RazorpayWebhookEventAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for webhook event analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['event_type', 'processed', 'payment'],
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


class BulkRazorpayPaymentUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk Razorpay payment updates.
    """
    payment_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_payment_ids(self, value):
        """
        Validate that all payments exist.
        """
        existing_payments = RazorpayPayment.objects.filter(id__in=value).count()
        if existing_payments != len(value):
            raise serializers.ValidationError("One or more payments do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['status', 'method', 'description', 'notes']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class BulkRazorpayWebhookEventUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk webhook event updates.
    """
    event_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_event_ids(self, value):
        """
        Validate that all webhook events exist.
        """
        existing_events = RazorpayWebhookEvent.objects.filter(id__in=value).count()
        if existing_events != len(value):
            raise serializers.ValidationError("One or more webhook events do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['processed', 'error_message']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class RazorpayPaymentRefundSerializer(serializers.Serializer):
    """
    Serializer for Razorpay payment refund process.
    """
    payment_id = serializers.IntegerField()
    refund_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    refund_reason = serializers.CharField(max_length=200, required=False)
    refund_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate_payment_id(self, value):
        """
        Validate that payment exists and is captured.
        """
        try:
            payment = RazorpayPayment.objects.get(id=value)
            if payment.status != 'captured':
                raise serializers.ValidationError("Payment must be captured to process refund.")
        except RazorpayPayment.DoesNotExist:
            raise serializers.ValidationError("Payment does not exist.")
        return value
    
    def validate_refund_amount(self, value):
        """
        Validate refund amount is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be positive.")
        return value


class RazorpayPaymentCaptureSerializer(serializers.Serializer):
    """
    Serializer for Razorpay payment capture process.
    """
    payment_id = serializers.IntegerField()
    capture_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    def validate_payment_id(self, value):
        """
        Validate that payment exists and is authorized.
        """
        try:
            payment = RazorpayPayment.objects.get(id=value)
            if payment.status != 'authorized':
                raise serializers.ValidationError("Payment must be authorized to capture.")
        except RazorpayPayment.DoesNotExist:
            raise serializers.ValidationError("Payment does not exist.")
        return value
    
    def validate_capture_amount(self, value):
        """
        Validate capture amount is positive.
        """
        if value is not None and value <= 0:
            raise serializers.ValidationError("Capture amount must be positive.")
        return value


class RazorpayWebhookEventProcessSerializer(serializers.Serializer):
    """
    Serializer for processing webhook events.
    """
    event_id = serializers.IntegerField()
    processed_by_id = serializers.IntegerField(required=False)
    
    def validate_event_id(self, value):
        """
        Validate that webhook event exists and is not processed.
        """
        try:
            event = RazorpayWebhookEvent.objects.get(id=value)
            if event.processed:
                raise serializers.ValidationError("Webhook event is already processed.")
        except RazorpayWebhookEvent.DoesNotExist:
            raise serializers.ValidationError("Webhook event does not exist.")
        return value


class RazorpayPaymentStatsSerializer(serializers.Serializer):
    """
    Serializer for Razorpay payment statistics.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['status', 'method', 'currency'],
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
from django.contrib.auth.models import User
from .models import RazorpayPayment, RazorpayWebhookEvent
from Orders.models import Order
from common.relations import get_related


class RazorpayPaymentAdminSerializer(serializers.ModelSerializer):
    """
    Serializer for Razorpay payment information in admin panel.
    """
    order = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    
    class Meta:
        model = RazorpayPayment
        fields = [
            'id', 'razorpay_payment_id', 'amount', 'currency', 'status',
            'method', 'created_at', 'updated_at', 'order', 'user'
        ]
        read_only_fields = ['id', 'razorpay_payment_id', 'amount', 'currency', 'status',
                           'method', 'created_at', 'updated_at', 'order', 'user']
    
    def get_order(self, obj):
        """Get related order information"""
        orders = get_related(obj, 'RazorpayPayment:Order', Order)
        if orders.exists():
            order = orders.first()
            return {
                'id': order.id,
                'total_amount': float(order.total_amount),
                'status': order.status,
                'created_at': order.created_at
            }
        return None
    
    def get_user(self, obj):
        """Get user information"""
        orders = get_related(obj, 'RazorpayPayment:Order', Order)
        if orders.exists():
            user = orders.first().created_by
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        return None


class RazorpayWebhookEventAdminSerializer(serializers.ModelSerializer):
    """
    Serializer for Razorpay webhook events in admin panel.
    """
    class Meta:
        model = RazorpayWebhookEvent
        fields = [
            'id', 'event_type', 'event_id', 'payment', 'payload', 'processed', 
            'processed_at', 'error_message', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'event_id', 'event_type', 'payment', 'payload', 
                           'processed', 'processed_at', 'error_message', 'created_at', 'updated_at']


class PaymentAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for payment analytics.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=[('day', 'Day'), ('week', 'Week'), ('month', 'Month')],
        required=False
    )
    
    def validate(self, attrs):
        """Validate analytics parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class PaymentFilterSerializer(serializers.Serializer):
    """
    Serializer for payment filtering.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(
        choices=[('captured', 'Captured'), ('authorized', 'Authorized'), ('failed', 'Failed')],
        required=False
    )
    payment_method = serializers.ChoiceField(
        choices=[('card', 'Card'), ('netbanking', 'Net Banking'), ('upi', 'UPI'), ('wallet', 'Wallet')],
        required=False
    )
    min_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    
    def validate(self, attrs):
        """Validate filter parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        min_amount = attrs.get('min_amount')
        max_amount = attrs.get('max_amount')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        if min_amount is not None and max_amount is not None:
            if min_amount > max_amount:
                raise serializers.ValidationError("Min amount cannot be greater than max amount.")
        
        return attrs
