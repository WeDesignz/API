from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Cart, Order, OrderTransaction, OrderComment, Invoice
from Accounts.serializers import UserSerializer
from Catalog.serializers import ProductSerializer
from MediaFiles.serializers import MediaSerializer


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer for Cart model with full CRUD operations.
    Handles cart item creation, updates, and management.
    """
    product = ProductSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = Cart
        fields = [
            'id', 'product', 'product_id', 'cart_type',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_product_id(self, value):
        """
        Validate that product exists.
        """
        try:
            from Catalog.models import Product
            Product.objects.get(id=value)
        except:
            raise serializers.ValidationError("Product does not exist.")
        return value
    
    def validate(self, attrs):
        """
        Validate business logic for cart items.
        """
        product_id = attrs.get('product_id')
        cart_type = attrs.get('cart_type', 'cart')
        created_by_id = attrs.get('created_by_id')
        
        # Check for duplicate cart items
        if created_by_id and product_id:
            existing_cart = Cart.objects.filter(
                product_id=product_id,
                cart_type=cart_type,
                created_by_id=created_by_id
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_cart.exists():
                raise serializers.ValidationError("Product already exists in cart.")
        
        return attrs


class CartListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Cart model used in list views.
    """
    product = ProductSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = Cart
        fields = ['id', 'product', 'cart_type', 'created_by', 'created_at']


class CartCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating cart items with minimal required fields.
    """
    product_id = serializers.IntegerField()
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Cart
        fields = ['product_id', 'cart_type', 'created_by_id']
    
    def validate_product_id(self, value):
        """
        Validate that product exists and is active.
        """
        try:
            from Catalog.models import Product
            product = Product.objects.get(id=value)
            if product.status != 'active':
                raise serializers.ValidationError("Product is not active.")
        except:
            raise serializers.ValidationError("Product does not exist.")
        return value


class CartUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating cart items with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Cart
        fields = ['cart_type', 'updated_by_id']


class OrderSerializer(serializers.ModelSerializer):
    """
    Serializer for Order model with full CRUD operations.
    Handles order creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    products = serializers.SerializerMethodField()
    order_transaction_number = serializers.CharField(read_only=True, allow_null=True)
    order_transaction_type = serializers.CharField(read_only=True, allow_null=True)
    custom_order_details = serializers.SerializerMethodField()
    subscription_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_type', 'product_ids', 'total_amount', 'status',
            'order_transaction_number', 'order_transaction_type',
            'custom_order_request', 'subscription',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'products',
            'custom_order_details', 'subscription_details'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_custom_order_details(self, obj):
        """Get custom order request details if order_type is 'custom'"""
        if obj.order_type == 'custom' and obj.custom_order_request:
            from CustomRequests.serializers import CustomOrderRequestSerializer
            return CustomOrderRequestSerializer(obj.custom_order_request).data
        return None
    
    def get_subscription_details(self, obj):
        """Get subscription details if order_type is 'subscription'"""
        if obj.order_type == 'subscription' and obj.subscription:
            from Plans.serializers import SubscriptionSerializer
            return SubscriptionSerializer(obj.subscription).data
        return None
    
    def get_products(self, obj):
        """
        Get related products for the order.
        """
        if obj.product_ids:
            try:
                product_ids = [int(id) for id in obj.product_ids.split(',') if id.strip()]
                products = Product.objects.filter(id__in=product_ids)
                return ProductSerializer(products, many=True).data
            except (ValueError, TypeError):
                return []
        return []
    
    
    def validate_product_ids(self, value):
        """
        Validate product IDs format and existence.
        """
        if value:
            try:
                product_ids = [int(id) for id in value.split(',') if id.strip()]
                existing_products = Product.objects.filter(id__in=product_ids).count()
                if existing_products != len(product_ids):
                    raise serializers.ValidationError("One or more products do not exist.")
            except (ValueError, TypeError):
                raise serializers.ValidationError("Invalid product IDs format.")
        return value


class OrderListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Order model used in list views.
    """
    created_by = UserSerializer(read_only=True)
    products_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_type', 'total_amount', 'status', 'created_by', 'created_at',
            'products_count', 'order_transaction_number', 'order_transaction_type'
        ]
    
    def get_products_count(self, obj):
        """
        Get count of products in the order.
        """
        if obj.product_ids:
            try:
                product_ids = [int(id) for id in obj.product_ids.split(',') if id.strip()]
                return len(product_ids)
            except (ValueError, TypeError):
                return 0
        return 0


class OrderCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating orders with minimal required fields.
    """
    product_ids = serializers.CharField(required=False, allow_blank=True)
    created_by_id = serializers.IntegerField(required=False)
    order_type = serializers.ChoiceField(choices=Order.ORDER_TYPE_CHOICES, default='cart')
    custom_order_request_id = serializers.IntegerField(required=False, write_only=True)
    subscription_id = serializers.IntegerField(required=False, write_only=True)
    
    class Meta:
        model = Order
        fields = [
            'order_type', 'product_ids', 'total_amount', 'created_by_id',
            'order_transaction_number', 'order_transaction_type',
            'custom_order_request_id', 'subscription_id'
        ]
    
    def validate_product_ids(self, value):
        """
        Validate product IDs format and existence.
        Allow empty for custom orders.
        """
        if not value:
            return value
        
        try:
            product_ids = [int(id) for id in value.split(',') if id.strip()]
            existing_products = Product.objects.filter(id__in=product_ids).count()
            if existing_products != len(product_ids):
                raise serializers.ValidationError("One or more products do not exist.")
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid product IDs format.")
        return value
    
    def validate(self, attrs):
        """
        Cross-field validation for order creation.
        """
        order_type = attrs.get('order_type', 'cart')
        product_ids = attrs.get('product_ids', '')
        custom_order_request_id = attrs.get('custom_order_request_id')
        subscription_id = attrs.get('subscription_id')
        total_amount = attrs.get('total_amount', 0)
        
        # Validate product_ids required for cart/subscription orders
        if order_type in ['cart', 'subscription']:
            if not product_ids:
                raise serializers.ValidationError({
                    'product_ids': 'Product IDs are required for cart and subscription orders.'
                })
        
        # Validate custom_order_request_id required for custom orders
        if order_type == 'custom':
            if not custom_order_request_id:
                raise serializers.ValidationError({
                    'custom_order_request_id': 'Custom order request ID is required for custom orders.'
                })
            # Verify custom order request exists
            try:
                from CustomRequests.models import CustomOrderRequest
                CustomOrderRequest.objects.get(id=custom_order_request_id)
            except CustomOrderRequest.DoesNotExist:
                raise serializers.ValidationError({
                    'custom_order_request_id': 'Custom order request does not exist.'
                })
            # For custom orders, product_ids should be empty
            attrs['product_ids'] = ''
        
        # Validate subscription_id for subscription orders
        if order_type == 'subscription':
            if subscription_id:
                try:
                    from Plans.models import Subscription
                    subscription = Subscription.objects.get(id=subscription_id)
                    if subscription.status != 'active':
                        raise serializers.ValidationError({
                            'subscription_id': 'Subscription must be active.'
                        })
                except Subscription.DoesNotExist:
                    raise serializers.ValidationError({
                        'subscription_id': 'Subscription does not exist.'
                    })
        
        # Validate total_amount - allow 0 for subscription orders
        if total_amount < 0:
            raise serializers.ValidationError({
                'total_amount': 'Total amount cannot be negative.'
            })
        
        return attrs
    
    def create(self, validated_data):
        """
        Create order with proper relationships.
        """
        custom_order_request_id = validated_data.pop('custom_order_request_id', None)
        subscription_id = validated_data.pop('subscription_id', None)
        
        # Handle custom_order_request relationship
        if validated_data.get('order_type') == 'custom' and custom_order_request_id:
            from CustomRequests.models import CustomOrderRequest
            validated_data['custom_order_request'] = CustomOrderRequest.objects.get(id=custom_order_request_id)
        
        # Handle subscription relationship
        if validated_data.get('order_type') == 'subscription' and subscription_id:
            from Plans.models import Subscription
            validated_data['subscription'] = Subscription.objects.get(id=subscription_id)
        
        return super().create(validated_data)


class OrderUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating orders with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Order
        fields = ['status', 'updated_by_id']


class OrderTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for OrderTransaction model with full CRUD operations.
    Handles order transaction creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    media = serializers.SerializerMethodField()
    wallet_transactions = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderTransaction
        fields = [
            'id', 'order_transaction_number', 'order_transaction_type',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'media', 'wallet_transactions'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_media(self, obj):
        """
        Get related media for the order transaction.
        """
        if obj:
            media = obj.get_media()
            return MediaSerializer(media, many=True).data
        return []
    
    def get_wallet_transactions(self, obj):
        """
        Get related wallet transactions for the order transaction.
        """
        if obj:
            wallet_transactions = obj.get_wallet_transactions()
            # Import here to avoid circular imports
            from Wallet.serializers import WalletTransactionListSerializer
            return WalletTransactionListSerializer(wallet_transactions, many=True).data
        return []
    
    def validate_order_transaction_number(self, value):
        """
        Validate order transaction number uniqueness.
        """
        if OrderTransaction.objects.filter(order_transaction_number=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Order transaction number already exists.")
        return value


class OrderTransactionListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for OrderTransaction model used in list views.
    """
    media_count = serializers.SerializerMethodField()
    wallet_transactions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderTransaction
        fields = [
            'id', 'order_transaction_number', 'order_transaction_type',
            'created_at', 'media_count', 'wallet_transactions_count'
        ]
    
    def get_media_count(self, obj):
        """
        Get count of related media.
        """
        return len(obj.get_media())
    
    def get_wallet_transactions_count(self, obj):
        """
        Get count of related wallet transactions.
        """
        return len(obj.get_wallet_transactions())


class OrderTransactionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating order transactions with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = OrderTransaction
        fields = ['order_transaction_number', 'order_transaction_type', 'created_by_id']
    
    def validate_order_transaction_number(self, value):
        """
        Validate order transaction number uniqueness.
        """
        if OrderTransaction.objects.filter(order_transaction_number=value).exists():
            raise serializers.ValidationError("Order transaction number already exists.")
        return value


class OrderTransactionUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating order transactions with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = OrderTransaction
        fields = ['order_transaction_type', 'updated_by_id']


class OrderSearchSerializer(serializers.Serializer):
    """
    Serializer for order search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    status = serializers.ChoiceField(
        choices=Order.STATUS_CHOICES,
        required=False
    )
    min_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    user_id = serializers.IntegerField(required=False)
    
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


class CartSearchSerializer(serializers.Serializer):
    """
    Serializer for cart search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    cart_type = serializers.ChoiceField(
        choices=Cart.TYPE_CHOICES,
        required=False
    )
    product_id = serializers.IntegerField(required=False)
    user_id = serializers.IntegerField(required=False)
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


class OrderFilterSerializer(serializers.Serializer):
    """
    Serializer for order filtering functionality.
    """
    statuses = serializers.ListField(
        child=serializers.ChoiceField(choices=Order.STATUS_CHOICES),
        required=False
    )
    amount_range = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    user_ids = serializers.ListField(
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


class CartFilterSerializer(serializers.Serializer):
    """
    Serializer for cart filtering functionality.
    """
    cart_types = serializers.ListField(
        child=serializers.ChoiceField(choices=Cart.TYPE_CHOICES),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    product_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )


class OrderAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for order analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['status', 'created_by', 'amount_range'],
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


class CartAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for cart analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['cart_type', 'created_by', 'product'],
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


class BulkOrderUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk order updates.
    """
    order_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_order_ids(self, value):
        """
        Validate that all orders exist.
        """
        existing_orders = Order.objects.filter(id__in=value).count()
        if existing_orders != len(value):
            raise serializers.ValidationError("One or more orders do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['status']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class BulkCartUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk cart updates.
    """
    cart_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_cart_ids(self, value):
        """
        Validate that all cart items exist.
        """
        existing_carts = Cart.objects.filter(id__in=value).count()
        if existing_carts != len(value):
            raise serializers.ValidationError("One or more cart items do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['cart_type']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class OrderStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating order status.
    """
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
    updated_by_id = serializers.IntegerField(required=False)
    
    def validate_status(self, value):
        """
        Validate status transition is allowed.
        """
        # Add business logic for status transitions here
        # For example, prevent moving from 'success' to 'pending'
        return value


class CartToOrderSerializer(serializers.Serializer):
    """
    Serializer for converting cart items to an order.
    """
    cart_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    user_id = serializers.IntegerField()
    
    def validate_cart_ids(self, value):
        """
        Validate that all cart items exist and belong to the user.
        """
        existing_carts = Cart.objects.filter(
            id__in=value,
            created_by_id=self.initial_data.get('user_id')
        ).count()
        if existing_carts != len(value):
            raise serializers.ValidationError("One or more cart items do not exist or do not belong to the user.")
        return value
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from .models import Order, OrderTransaction
from Razorpay.models import RazorpayPayment, RazorpayWebhookEvent
from Plans.models import Plan, Subscription
from Wallet.models import WalletTransaction, WalletWithdrawalRequest
from CustomRequests.models import CustomOrderRequest
from Catalog.models import Product, CollectionBundle
from common.relations import get_related


class TransactionListSerializer(serializers.ModelSerializer):
    """
    Serializer for transaction list view with comprehensive information.
    """
    transaction_type = serializers.SerializerMethodField()
    user_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    user_email = serializers.CharField(source='created_by.email', read_only=True)
    razorpay_payment_id = serializers.SerializerMethodField()
    razorpay_order_id = serializers.SerializerMethodField()
    razorpay_status = serializers.SerializerMethodField()
    razorpay_payment = serializers.SerializerMethodField()
    order_details = serializers.SerializerMethodField()
    subscription_details = serializers.SerializerMethodField()
    custom_order_details = serializers.SerializerMethodField()
    withdrawal_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'order_type', 'product_ids', 'total_amount', 'status', 'created_by', 'user_name', 'user_email',
            'created_at', 'updated_at', 'transaction_type', 'razorpay_payment_id', 'razorpay_order_id',
            'razorpay_status', 'razorpay_payment', 'order_details', 'subscription_details', 'custom_order_details',
            'withdrawal_details', 'order_transaction_number', 'order_transaction_type'
        ]
        read_only_fields = [
            'id', 'order_number', 'order_type', 'product_ids', 'total_amount', 'status', 'created_by', 'user_name', 'user_email',
            'created_at', 'updated_at', 'transaction_type', 'razorpay_payment_id', 'razorpay_order_id',
            'razorpay_status', 'razorpay_payment', 'order_details', 'subscription_details', 'custom_order_details',
            'withdrawal_details', 'order_transaction_number', 'order_transaction_type'
        ]
    
    def get_transaction_type(self, obj):
        """Determine transaction type based on order content"""
        # TODO: Implement logic to determine transaction type
        # This would require analyzing product_ids and related data
        return 'order'  # Placeholder
    
    def get_razorpay_payment_id(self, obj):
        """Get Razorpay payment ID if exists"""
        # Use prefetched razorpay_payments if available
        if hasattr(obj, 'razorpay_payments'):
            payment = obj.razorpay_payments.first()
            if payment:
                return payment.razorpay_payment_id
        # Fallback to get_related if prefetch not available
        payments = get_related(obj, 'Order:RazorpayPayment', RazorpayPayment)
        if payments.exists():
            return payments.first().razorpay_payment_id
        return None
    
    def get_razorpay_order_id(self, obj):
        """Get Razorpay order ID if exists"""
        if hasattr(obj, 'razorpay_payments'):
            payment = obj.razorpay_payments.first()
            if payment:
                return payment.razorpay_order_id
        payments = get_related(obj, 'Order:RazorpayPayment', RazorpayPayment)
        if payments.exists():
            return payments.first().razorpay_order_id
        return None
    
    def get_razorpay_status(self, obj):
        """Get Razorpay payment status if exists"""
        if hasattr(obj, 'razorpay_payments'):
            payment = obj.razorpay_payments.first()
            if payment:
                return payment.status
        payments = get_related(obj, 'Order:RazorpayPayment', RazorpayPayment)
        if payments.exists():
            return payments.first().status
        return None
    
    def get_razorpay_payment(self, obj):
        """Get full Razorpay payment data if exists"""
        if hasattr(obj, 'razorpay_payments'):
            payment = obj.razorpay_payments.first()
            if payment:
                return {
                    'id': payment.id,
                    'razorpay_payment_id': payment.razorpay_payment_id,
                    'razorpay_order_id': payment.razorpay_order_id,
                    'amount': float(payment.amount),
                    'currency': payment.currency,
                    'status': payment.status,
                    'method': payment.method,
                    'created_at': payment.created_at,
                    'updated_at': payment.updated_at,
                }
        payments = get_related(obj, 'Order:RazorpayPayment', RazorpayPayment)
        if payments.exists():
            payment = payments.first()
            return {
                'id': payment.id,
                'razorpay_payment_id': payment.razorpay_payment_id,
                'razorpay_order_id': payment.razorpay_order_id,
                'amount': float(payment.amount),
                'currency': payment.currency,
                'status': payment.status,
                'method': payment.method,
                'created_at': payment.created_at,
                'updated_at': payment.updated_at,
            }
        return None
    
    def get_order_details(self, obj):
        """Get order transaction details - OrderTransaction has been merged into Order"""
        # OrderTransaction model has been merged into Order
        # Return simplified order details based on Order model
        product_ids = []
        if obj.product_ids:
            try:
                product_ids = [int(id.strip()) for id in obj.product_ids.split(',') if id.strip()]
            except (ValueError, TypeError):
                product_ids = []
        
        return {
            'transaction_count': 1 if obj.order_transaction_number else 0,
            'total_items': len(product_ids),
            'items': [
                {
                    'product_id': pid,
                    'total': float(obj.total_amount) / len(product_ids) if product_ids else float(obj.total_amount)
                }
                for pid in product_ids
            ] if product_ids else []
        }
    
    def get_subscription_details(self, obj):
        """Get subscription details if this is a subscription order"""
        # TODO: Implement subscription details logic
        return None
    
    def get_custom_order_details(self, obj):
        """Get custom order details if this is a custom order"""
        # TODO: Implement custom order details logic
        return None
    
    def get_withdrawal_details(self, obj):
        """Get withdrawal details if this is a withdrawal transaction"""
        # TODO: Implement withdrawal details logic
        return None


class TransactionDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed transaction information.
    """
    user = serializers.SerializerMethodField()
    razorpay_payments = serializers.SerializerMethodField()
    order_transactions = serializers.SerializerMethodField()
    refunds = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'product_ids', 'total_amount', 'status', 'created_by', 'created_at', 'updated_at',
            'user', 'razorpay_payments', 'order_transactions', 'refunds',
            'order_transaction_number', 'order_transaction_type'
        ]
        read_only_fields = [
            'id', 'product_ids', 'total_amount', 'status', 'created_by', 'created_at', 'updated_at',
            'user', 'razorpay_payments', 'order_transactions', 'refunds',
            'order_transaction_number', 'order_transaction_type'
        ]
    
    def get_user(self, obj):
        """Get user information"""
        return {
            'id': obj.created_by.id,
            'username': obj.created_by.username,
            'email': obj.created_by.email,
            'first_name': obj.created_by.first_name,
            'last_name': obj.created_by.last_name,
            'full_name': obj.created_by.get_full_name()
        }
    
    def get_razorpay_payments(self, obj):
        """Get Razorpay payment information"""
        payments = get_related(obj, 'Order:RazorpayPayment', RazorpayPayment)
        return [
            {
                'id': payment.id,
                'razorpay_payment_id': payment.razorpay_payment_id,
                'amount': float(payment.amount),
                'status': payment.status,
                'created_at': payment.created_at
            }
            for payment in payments
        ]
    
    def get_order_transactions(self, obj):
        """Get order transaction details - OrderTransaction has been merged into Order"""
        # OrderTransaction model has been merged into Order
        # Return simplified transaction details based on Order model
        product_ids = []
        if obj.product_ids:
            try:
                product_ids = [int(id.strip()) for id in obj.product_ids.split(',') if id.strip()]
            except (ValueError, TypeError):
                product_ids = []
        
        if not product_ids:
            return []
        
        # Return one transaction entry per product
        item_total = float(obj.total_amount) / len(product_ids) if product_ids else 0
        return [
            {
                'product_id': pid,
                'total': item_total,
                'created_at': obj.created_at.isoformat() if obj.created_at else None
            }
            for pid in product_ids
        ]
    
    def get_refunds(self, obj):
        """Get refund information"""
        # TODO: Implement refund details
        return []


class RefundRequestSerializer(serializers.Serializer):
    """
    Serializer for refund requests.
    """
    order_id = serializers.IntegerField()
    refund_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    refund_reason = serializers.CharField(max_length=500)
    admin_notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_order_id(self, value):
        """Validate that order exists and is eligible for refund"""
        try:
            order = Order.objects.get(id=value)
            if order.status not in ['completed', 'success']:
                raise serializers.ValidationError("Order is not eligible for refund.")
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order does not exist.")
        return value
    
    def validate_refund_amount(self, value):
        """Validate refund amount"""
        if value <= 0:
            raise serializers.ValidationError("Refund amount must be positive.")
        return value


class RefundListSerializer(serializers.ModelSerializer):
    """
    Serializer for refund list view.
    """
    order = TransactionListSerializer(read_only=True)
    processed_by = serializers.SerializerMethodField()
    
    class Meta:
        model = Order  # TODO: Create Refund model
        fields = [
            'id', 'order', 'refund_amount', 'refund_reason', 'status',
            'processed_by', 'processed_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'order', 'refund_amount', 'refund_reason', 'status',
            'processed_by', 'processed_at', 'created_at'
        ]
    
    def get_processed_by(self, obj):
        """Get admin user who processed the refund"""
        # TODO: Implement processed_by logic
        return None


class OrderListSerializer(serializers.ModelSerializer):
    """
    Serializer for order list view.
    """
    user_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    user_email = serializers.CharField(source='created_by.email', read_only=True)
    transaction_count = serializers.SerializerMethodField()
    razorpay_payment_id = serializers.SerializerMethodField()
    razorpay_order_id = serializers.SerializerMethodField()
    razorpay_status = serializers.SerializerMethodField()
    razorpay_payment = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'order_type', 'product_ids', 'total_amount', 'status', 'created_by', 'user_name', 'user_email',
            'created_at', 'updated_at', 'transaction_count', 'razorpay_payment_id', 'razorpay_order_id',
            'razorpay_status', 'razorpay_payment', 'order_transaction_number', 'order_transaction_type'
        ]
        read_only_fields = [
            'id', 'order_number', 'order_type', 'product_ids', 'total_amount', 'status', 'created_by', 'user_name', 'user_email',
            'created_at', 'updated_at', 'transaction_count', 'razorpay_payment_id', 'razorpay_order_id',
            'razorpay_status', 'razorpay_payment', 'order_transaction_number', 'order_transaction_type'
        ]
    
    def get_transaction_count(self, obj):
        """Get count of order transactions - each Order is now one transaction"""
        # OrderTransaction has been merged into Order model
        # Each Order represents one transaction
        return 1 if obj.order_transaction_number else 0
    
    def get_razorpay_payment_id(self, obj):
        """Get Razorpay payment ID if exists"""
        # Use prefetched razorpay_payments if available
        if hasattr(obj, 'razorpay_payments'):
            payment = obj.razorpay_payments.first()
            if payment:
                return payment.razorpay_payment_id
        # Fallback to get_related if prefetch not available
        payments = get_related(obj, 'Order:RazorpayPayment', RazorpayPayment)
        if payments.exists():
            return payments.first().razorpay_payment_id
        return None
    
    def get_razorpay_order_id(self, obj):
        """Get Razorpay order ID if exists"""
        if hasattr(obj, 'razorpay_payments'):
            payment = obj.razorpay_payments.first()
            if payment:
                return payment.razorpay_order_id
        payments = get_related(obj, 'Order:RazorpayPayment', RazorpayPayment)
        if payments.exists():
            return payments.first().razorpay_order_id
        return None
    
    def get_razorpay_status(self, obj):
        """Get Razorpay payment status if exists"""
        if hasattr(obj, 'razorpay_payments'):
            payment = obj.razorpay_payments.first()
            if payment:
                return payment.status
        payments = get_related(obj, 'Order:RazorpayPayment', RazorpayPayment)
        if payments.exists():
            return payments.first().status
        return None
    
    def get_razorpay_payment(self, obj):
        """Get full Razorpay payment data if exists"""
        if hasattr(obj, 'razorpay_payments'):
            payment = obj.razorpay_payments.first()
            if payment:
                return {
                    'id': payment.id,
                    'razorpay_payment_id': payment.razorpay_payment_id,
                    'razorpay_order_id': payment.razorpay_order_id,
                    'amount': float(payment.amount),
                    'currency': payment.currency,
                    'status': payment.status,
                    'method': payment.method,
                    'created_at': payment.created_at,
                    'updated_at': payment.updated_at,
                }
        payments = get_related(obj, 'Order:RazorpayPayment', RazorpayPayment)
        if payments.exists():
            payment = payments.first()
            return {
                'id': payment.id,
                'razorpay_payment_id': payment.razorpay_payment_id,
                'razorpay_order_id': payment.razorpay_order_id,
                'amount': float(payment.amount),
                'currency': payment.currency,
                'status': payment.status,
                'method': payment.method,
                'created_at': payment.created_at,
                'updated_at': payment.updated_at,
            }
        return None


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for detailed order information.
    """
    user = serializers.SerializerMethodField()
    order_transactions = serializers.SerializerMethodField()
    razorpay_payments = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'product_ids', 'total_amount', 'status', 'created_by', 'created_at', 'updated_at',
            'user', 'order_transactions', 'razorpay_payments',
            'order_transaction_number', 'order_transaction_type'
        ]
        read_only_fields = [
            'id', 'product_ids', 'total_amount', 'status', 'created_by', 'created_at', 'updated_at',
            'user', 'order_transactions', 'razorpay_payments',
            'order_transaction_number', 'order_transaction_type'
        ]
    
    def get_user(self, obj):
        """Get user information"""
        return {
            'id': obj.created_by.id,
            'username': obj.created_by.username,
            'email': obj.created_by.email,
            'first_name': obj.created_by.first_name,
            'last_name': obj.created_by.last_name,
            'full_name': obj.created_by.get_full_name()
        }
    
    def get_order_transactions(self, obj):
        """Get order transaction details - OrderTransaction has been merged into Order"""
        # OrderTransaction model has been merged into Order
        # Return simplified transaction details based on Order model
        product_ids = []
        if obj.product_ids:
            try:
                product_ids = [int(id.strip()) for id in obj.product_ids.split(',') if id.strip()]
            except (ValueError, TypeError):
                product_ids = []
        
        if not product_ids:
            return []
        
        # Return one transaction entry per product
        item_total = float(obj.total_amount) / len(product_ids) if product_ids else 0
        return [
            {
                'product_id': pid,
                'total': item_total,
                'created_at': obj.created_at.isoformat() if obj.created_at else None
            }
            for pid in product_ids
        ]
    
    def get_razorpay_payments(self, obj):
        """Get Razorpay payment information"""
        payments = get_related(obj, 'Order:RazorpayPayment', RazorpayPayment)
        return [
            {
                'id': payment.id,
                'razorpay_payment_id': payment.razorpay_payment_id,
                'amount': float(payment.amount),
                'status': payment.status,
                'created_at': payment.created_at
            }
            for payment in payments
        ]


class OrderStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating order status.
    """
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES)
    admin_notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_status(self, value):
        """Validate status transition"""
        # TODO: Implement status transition validation
        return value


class FinancialReportSerializer(serializers.Serializer):
    """
    Serializer for financial reports.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    report_type = serializers.ChoiceField(
        choices=[('daily', 'Daily'), ('monthly', 'Monthly'), ('yearly', 'Yearly'), ('custom', 'Custom')],
        required=False
    )
    include_refunds = serializers.BooleanField(default=True)
    group_by = serializers.ChoiceField(
        choices=[('day', 'Day'), ('week', 'Week'), ('month', 'Month'), ('year', 'Year')],
        required=False
    )
    
    def validate(self, attrs):
        """Validate report parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class FinancialReportDataSerializer(serializers.Serializer):
    """
    Serializer for financial report data.
    """
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_transactions = serializers.IntegerField()
    successful_transactions = serializers.IntegerField()
    failed_transactions = serializers.IntegerField()
    total_refunds = serializers.DecimalField(max_digits=15, decimal_places=2)
    net_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    revenue_by_type = serializers.DictField()
    daily_breakdown = serializers.ListField(child=serializers.DictField())
    growth_rate = serializers.DecimalField(max_digits=5, decimal_places=2)


class TransactionFilterSerializer(serializers.Serializer):
    """
    Serializer for transaction filtering.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES, required=False)
    user_id = serializers.IntegerField(required=False)
    min_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    transaction_type = serializers.ChoiceField(
        choices=[('order', 'Order'), ('subscription', 'Subscription'), ('custom', 'Custom Order')],
        required=False
    )
    
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


class OrderFilterSerializer(serializers.Serializer):
    """
    Serializer for order filtering.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(choices=Order.STATUS_CHOICES, required=False)
    user_id = serializers.IntegerField(required=False)
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


class RefundFilterSerializer(serializers.Serializer):
    """
    Serializer for refund filtering.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(choices=[('pending', 'Pending'), ('processed', 'Processed'), ('failed', 'Failed')], required=False)
    order_id = serializers.IntegerField(required=False)
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


# ==================== ORDER COMMENT SERIALIZERS ====================

class OrderCommentSerializer(serializers.ModelSerializer):
    """
    Serializer for OrderComment with full details.
    Works for all order types: cart, subscription, and custom.
    """
    created_by = UserSerializer(read_only=True)
    admin_user = UserSerializer(read_only=True)
    media = serializers.SerializerMethodField()
    is_customer_comment = serializers.ReadOnlyField()
    is_admin_comment = serializers.ReadOnlyField()
    is_system_comment = serializers.ReadOnlyField()
    is_read = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderComment
        fields = [
            'id', 'order', 'comment_type', 'message', 
            'is_internal', 'created_by', 'created_at', 'updated_at',
            'is_admin_response', 'admin_user', 'media',
            'is_customer_comment', 'is_admin_comment', 'is_system_comment',
            'is_read'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_read']
    
    def get_is_read(self, obj):
        """
        Check if the current user has read this comment.
        Returns True if a read receipt exists for the current user, False otherwise.
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.read_receipts.filter(user=request.user).exists()
        return False
    
    def get_media(self, obj):
        """
        Get related media files for the comment.
        """
        if obj:
            media = obj.get_media()
            return MediaSerializer(media, many=True).data
        return []
    
    def validate_message(self, value):
        """
        Validate message is not empty.
        """
        if not value.strip():
            raise serializers.ValidationError("Message cannot be empty.")
        return value.strip()


class OrderCommentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating order comments.
    Note: 'order' is not included in fields as it's set from URL parameter in the view.
    """
    created_by_id = serializers.IntegerField(required=False, write_only=True)
    message = serializers.CharField(required=True)
    
    class Meta:
        model = OrderComment
        fields = ['comment_type', 'message', 'is_internal', 'created_by_id']
    
    def validate_message(self, value):
        """
        Validate message is not empty.
        """
        if not value or not value.strip():
            raise serializers.ValidationError("Message cannot be empty.")
        return value.strip()


class OrderCommentListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing comments.
    """
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = OrderComment
        fields = [
            'id', 'comment_type', 'message', 'is_internal',
            'created_by', 'created_at', 'is_admin_response'
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    """
    Serializer for Invoice model.
    """
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_number', 'invoice_type', 'invoice_date',
            'payment_due_date', 'order', 'order_number', 'user', 'user_name', 'user_username',
            'subtotal', 'gst_amount', 'commission_amount', 'total_amount',
            'pdf_file_path', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
