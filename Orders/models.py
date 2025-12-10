from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from django.dispatch import receiver
from common.relations import attach_relation, get_related_ids, get_related, detach_relation
from MediaFiles.models import Media
from Wallet.models import WalletTransaction


class Cart(models.Model):
    TYPE_CHOICES = [
        ('cart', 'Cart'),
        ('wishlist', 'Wishlist'),
    ]
    
    product = models.ForeignKey('Catalog.Product', on_delete=models.CASCADE, related_name='cart_items')
    cart_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='cart')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_cart_items')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_cart_items', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'cart'
        verbose_name = 'Cart'
        verbose_name_plural = 'Cart'
    
    def __str__(self):
        return f"Cart {self.pk} - {self.product.title} ({self.cart_type})"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    
    TRANSACTION_TYPE_CHOICES = [
        ('invoice', 'Invoice'),
        ('bill', 'Bill'),
        ('receipt', 'Receipt'),
    ]
    
    ORDER_TYPE_CHOICES = [
        ('cart', 'Cart Order'),           # Regular cart checkout with payment
        ('subscription', 'Subscription'),  # Free checkout using active subscription
        ('custom', 'Custom Order'),        # Custom order request
        ('mock_pdf', 'Mock PDF Download'), # Mock PDF download order
    ]
    
    # Order type to distinguish between cart, subscription, and custom orders
    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPE_CHOICES,
        default='cart',
        help_text="Type of order: cart (regular cart checkout), subscription (free with subscription), or custom (custom order request)"
    )
    
    # Product IDs (merged from cart_ids) - nullable for custom orders
    product_ids = models.TextField(blank=True, null=True, help_text="Product IDs for cart/subscription orders (comma-separated)")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Link to CustomOrderRequest if order_type is 'custom'
    custom_order_request = models.OneToOneField('CustomRequests.CustomOrderRequest', on_delete=models.CASCADE, related_name='order', null=True, blank=True, help_text="Linked custom order request if order_type is 'custom'")
    
    # Link to subscription if order_type is 'subscription'
    subscription = models.ForeignKey('Plans.Subscription', on_delete=models.SET_NULL, related_name='orders', null=True, blank=True, help_text="Subscription used for free checkout (order_type='subscription')")
    
    # Link to PDFDownload if order_type is 'mock_pdf'
    pdf_download = models.ForeignKey('Catalog.PDFDownload', on_delete=models.CASCADE, related_name='orders', null=True, blank=True, help_text="Linked PDF download if order_type is 'mock_pdf'")
    
    # Track free downloads used for this order (decremented from subscription on payment success)
    free_downloads_used = models.IntegerField(
        default=0,
        help_text="Number of free downloads used from subscription for this order (decremented on payment success)"
    )
    
    # Transaction fields (merged from OrderTransaction)
    order_transaction_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    order_transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, null=True, blank=True)
    
    # Professional Order Number (e.g., ORD-20241120-0001)
    order_number = models.CharField(max_length=50, unique=True, null=True, blank=True, db_index=True)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_orders', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'order'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
    
    def __str__(self):
        return f"Order {self.order_number or self.pk} - {self.get_order_type_display()} - {self.status}"
    
    def generate_order_number(self):
        """
        Generate a professional order number in format: ORD-YYYYMMDD-XXXXX
        Example: ORD-20241120-00001
        """
        from django.utils import timezone
        from django.core.cache import cache
        from django.db import transaction
        
        # Get current date in YYYYMMDD format
        date_str = timezone.now().strftime('%Y%m%d')
        
        # Use cache to track daily counter for thread-safety
        cache_key = f'order_counter_{date_str}'
        
        # Try to get counter from cache, if not exists, get from database
        counter = cache.get(cache_key)
        
        if counter is None:
            # Get the highest counter for today from database
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_orders = Order.objects.filter(
                order_number__startswith=f'ORD-{date_str}-',
                created_at__gte=today_start
            ).order_by('-order_number').first()
            
            if today_orders and today_orders.order_number:
                # Extract counter from existing order number
                try:
                    counter = int(today_orders.order_number.split('-')[-1])
                except (ValueError, IndexError):
                    counter = 0
            else:
                counter = 0
            
            # Set cache with 24 hour expiry (until end of day)
            cache.set(cache_key, counter, 86400)  # 24 hours
        
        # Increment counter atomically
        with transaction.atomic():
            # Double-check in database to ensure uniqueness
            new_counter = counter + 1
            order_number = f'ORD-{date_str}-{new_counter:05d}'
            
            # Check if this order number already exists (race condition protection)
            while Order.objects.filter(order_number=order_number).exists():
                new_counter += 1
                order_number = f'ORD-{date_str}-{new_counter:05d}'
            
            # Update cache
            cache.set(cache_key, new_counter, 86400)
            
            return order_number
    
    def get_media(self):
        return get_related(self, 'Order:Media', Media)
    
    def attach_media(self, media_obj, meta=None, created_by=None):
        return attach_relation('Order:Media', self, media_obj, meta=meta, created_by=created_by)
    
    def detach_media(self, media_obj):
        return detach_relation('Order:Media', self, media_obj)
    
    def get_wallet_transactions(self):
        return get_related(self, 'Order:WalletTransaction', WalletTransaction)
    
    def attach_wallet_transaction(self, wallet_transaction_obj, meta=None, created_by=None):
        return attach_relation('Order:WalletTransaction', self, wallet_transaction_obj, meta=meta, created_by=created_by)
    
    def detach_wallet_transaction(self, wallet_transaction_obj):
        return detach_relation('Order:WalletTransaction', self, wallet_transaction_obj)


@receiver(pre_save, sender=Order)
def generate_order_number_signal(sender, instance, **kwargs):
    """
    Automatically generate professional order number when order is created.
    """
    # Only generate if order_number is not already set
    if not instance.order_number:
        instance.order_number = instance.generate_order_number()


class OrderComment(models.Model):
    """
    Unified comment/chat model for all order types.
    Works for Cart Orders, Subscription Orders, and Custom Orders.
    """
    COMMENT_TYPE_CHOICES = [
        ('customer', 'Customer'),
        ('admin', 'Admin'),
        ('system', 'System'),
    ]
    
    # Link to Order (works for all order types: cart, subscription, custom)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='comments')
    comment_type = models.CharField(max_length=20, choices=COMMENT_TYPE_CHOICES, default='customer')
    message = models.TextField()
    is_internal = models.BooleanField(default=False, help_text="Internal comments only visible to admin team")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='order_comments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For admin responses
    is_admin_response = models.BooleanField(default=False)
    admin_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,related_name='admin_order_comments')
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'order_comment'
        verbose_name = 'Order Comment'
        verbose_name_plural = 'Order Comments'
        ordering = ['created_at']  # Chronological order for chat
    
    def __str__(self):
        return f"Comment on Order #{self.order.id} by {self.created_by.username}"
    
    def get_media(self):
        """Get related media files for this comment."""
        return get_related(self, 'OrderComment:Media', Media)
    
    def attach_media(self, media_obj, meta=None, created_by=None):
        """Attach media file to this comment."""
        return attach_relation('OrderComment:Media', self, media_obj, meta=meta, created_by=created_by)
    
    def detach_media(self, media_obj):
        """Detach media file from this comment."""
        return detach_relation('OrderComment:Media', self, media_obj)
    
    @property
    def is_customer_comment(self):
        """Check if this is a customer comment."""
        return self.comment_type == 'customer'
    
    @property
    def is_admin_comment(self):
        """Check if this is an admin comment."""
        return self.comment_type == 'admin'
    
    @property
    def is_system_comment(self):
        """Check if this is a system comment."""
        return self.comment_type == 'system'


class OrderCommentReadReceipt(models.Model):
    """
    Tracks which users have read which comments.
    Used to determine unread message counts for both customers and admins.
    """
    comment = models.ForeignKey(
        OrderComment,
        on_delete=models.CASCADE,
        related_name='read_receipts'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='order_comment_read_receipts'
    )
    read_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_comment_read_receipt'
        verbose_name = 'Order Comment Read Receipt'
        verbose_name_plural = 'Order Comment Read Receipts'
        unique_together = ['comment', 'user']  # One read receipt per user per comment
        indexes = [
            models.Index(fields=['comment', 'user']),
        ]
    
    def __str__(self):
        return f"{self.user.username} read comment #{self.comment.id}"


class Invoice(models.Model):
    """
    Model to store invoice information for both customers and designers.
    """
    INVOICE_TYPE_CHOICES = [
        ('customer', 'Customer Invoice'),  # Invoice to customer for purchase
        ('designer', 'Designer Invoice'),  # Invoice to designer for GST + Commission
    ]
    
    invoice_number = models.CharField(max_length=100, unique=True, db_index=True)
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPE_CHOICES)
    invoice_date = models.DateField(auto_now_add=True)
    payment_due_date = models.DateField(null=True, blank=True)
    
    # Link to order (nullable for subscription settlements)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='invoices', null=True, blank=True)
    
    # Link to subscription (for subscription settlement invoices)
    subscription = models.ForeignKey('Plans.Subscription', on_delete=models.CASCADE, related_name='settlement_invoices', null=True, blank=True, help_text="Subscription this invoice is for (for subscription settlements)")
    
    # User this invoice is for (customer or designer)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    
    # Financial details
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # PDF file path
    pdf_file_path = models.CharField(max_length=500, blank=True, null=True)
    
    # Metadata
    invoice_data = models.JSONField(default=dict, help_text="Stores invoice data used for PDF generation")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'invoice'
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.invoice_number} - {self.get_invoice_type_display()} - {self.user.username}"
    
    def generate_invoice_number(self):
        """
        Generate invoice number in format: INV-YYYYMMDD-XXXXX
        """
        from django.utils import timezone
        from django.core.cache import cache
        from django.db import transaction
        
        date_str = timezone.now().strftime('%Y%m%d')
        cache_key = f'invoice_counter_{date_str}'
        
        counter = cache.get(cache_key)
        if counter is None:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_invoices = Invoice.objects.filter(
                invoice_number__startswith=f'INV-{date_str}-',
                created_at__gte=today_start
            ).order_by('-invoice_number').first()
            
            if today_invoices:
                try:
                    counter = int(today_invoices.invoice_number.split('-')[-1])
                except (ValueError, IndexError):
                    counter = 0
            else:
                counter = 0
            
            cache.set(cache_key, counter, 86400)
        
        with transaction.atomic():
            new_counter = counter + 1
            invoice_number = f'INV-{date_str}-{new_counter:05d}'
            
            while Invoice.objects.filter(invoice_number=invoice_number).exists():
                new_counter += 1
                invoice_number = f'INV-{date_str}-{new_counter:05d}'
            
            cache.set(cache_key, new_counter, 86400)
            return invoice_number
    
    def generate_bill_number(self):
        """
        Generate bill number in format: BILL-YYYYMMDD-XXXXX
        For designer invoices (bills).
        """
        from django.utils import timezone
        from django.core.cache import cache
        from django.db import transaction
        
        date_str = timezone.now().strftime('%Y%m%d')
        cache_key = f'bill_counter_{date_str}'
        
        counter = cache.get(cache_key)
        if counter is None:
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_bills = Invoice.objects.filter(
                invoice_number__startswith=f'BILL-{date_str}-',
                created_at__gte=today_start
            ).order_by('-invoice_number').first()
            
            if today_bills:
                try:
                    counter = int(today_bills.invoice_number.split('-')[-1])
                except (ValueError, IndexError):
                    counter = 0
            else:
                counter = 0
            
            cache.set(cache_key, counter, 86400)
        
        with transaction.atomic():
            new_counter = counter + 1
            bill_number = f'BILL-{date_str}-{new_counter:05d}'
            
            while Invoice.objects.filter(invoice_number=bill_number).exists():
                new_counter += 1
                bill_number = f'BILL-{date_str}-{new_counter:05d}'
            
            cache.set(cache_key, new_counter, 86400)
            return bill_number


# OrderTransaction model has been merged into Order model
# This class is kept for backward compatibility during migration
# TODO: Remove after migration is complete and all references are updated
class OrderTransaction(models.Model):
    TYPE_CHOICES = [
        ('invoice', 'Invoice'),
        ('bill', 'Bill'),
        ('receipt', 'Receipt'),
    ]

    order_transaction_number = models.CharField(max_length=100, unique=True, null=True, blank=True)
    order_transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_order_transactions', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_order_transactions', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'order_transaction'
        verbose_name = 'Order Transaction (Deprecated)'
        verbose_name_plural = 'Order Transactions (Deprecated)'
    
    def __str__(self):
        return f"Transaction {self.order_transaction_number} - {self.order_transaction_type}"