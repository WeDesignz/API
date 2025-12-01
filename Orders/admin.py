from django.contrib import admin
from .models import Cart, Order, OrderComment, OrderCommentReadReceipt, Invoice


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """
    Admin interface for Cart model.
    Manages shopping cart and wishlist items for users.
    """
    list_display = ['product', 'cart_type', 'created_by', 'created_at']
    list_filter = ['cart_type', 'created_at', 'updated_at']
    search_fields = ['product__title', 'product__product_number', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['cart_type']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Cart Information', {
            'fields': ('product', 'cart_type')
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'created_by', 'updated_by')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Admin interface for Order model.
    Manages customer orders and purchase transactions.
    Supports three order types: cart, subscription, and custom orders.
    """
    list_display = ['id', 'order_number', 'order_type', 'total_amount', 'status', 'free_downloads_used', 'subscription', 'pdf_download', 'created_by', 'created_at']
    list_display_links = ['order_number', 'id']  # Use order_number as primary link, fallback to id
    list_filter = ['order_type', 'status', 'created_at', 'updated_at']
    search_fields = ['id', 'order_number', 'created_by__username', 'created_by__email', 'product_ids', 'pdf_download__id']
    readonly_fields = ['id', 'order_number', 'free_downloads_used', 'created_at', 'updated_at']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Order Identification', {
            'fields': ('order_number', 'id'),
            'description': 'Professional order number and internal ID'
        }),
        ('Order Type & Basic Information', {
            'fields': ('order_type', 'product_ids', 'total_amount', 'status')
        }),
        ('Order Relationships', {
            'fields': ('custom_order_request', 'subscription', 'pdf_download'),
            'description': 'Custom order request (for custom orders), subscription (for subscription orders), or PDF download (for mock_pdf orders)'
        }),
        ('Subscription Information', {
            'fields': ('free_downloads_used',),
            'description': 'Number of free downloads used from subscription for this order (decremented on payment success)',
            'classes': ('collapse',)
        }),
        ('Transaction Information', {
            'fields': ('order_transaction_number', 'order_transaction_type'),
            'classes': ('collapse',)
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'created_by', 
            'updated_by',
            'custom_order_request',
            'subscription',
            'subscription__plan',
            'pdf_download'
        )
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make order_type readonly after creation to prevent type changes.
        """
        readonly = list(self.readonly_fields)
        if obj:  # Editing an existing order
            readonly.append('order_type')
            readonly.append('custom_order_request')
        return readonly
    


@admin.register(OrderCommentReadReceipt)
class OrderCommentReadReceiptAdmin(admin.ModelAdmin):
    """
    Admin interface for OrderCommentReadReceipt model.
    """
    list_display = ['id', 'comment', 'user', 'read_at']
    list_filter = ['read_at']
    search_fields = ['comment__message', 'user__username', 'user__email']
    readonly_fields = ['read_at']
    ordering = ['-read_at']
    list_per_page = 25


@admin.register(OrderComment)
class OrderCommentAdmin(admin.ModelAdmin):
    """
    Admin interface for OrderComment model.
    Manages comments/messages for all order types (cart, subscription, custom).
    """
    list_display = ['id', 'order', 'comment_type', 'created_by', 'is_admin_response', 'is_internal', 'created_at']
    list_filter = ['comment_type', 'is_admin_response', 'is_internal', 'created_at']
    search_fields = ['message', 'order__id', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_internal']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Comment Information', {
            'fields': ('order', 'comment_type', 'message', 'is_internal')
        }),
        ('User Information', {
            'fields': ('created_by', 'admin_user', 'is_admin_response')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order', 
            'created_by', 
            'admin_user'
        )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """
    Admin interface for Invoice model.
    Manages invoices for both customers and designers.
    """
    list_display = ['invoice_number', 'invoice_type', 'order', 'user', 'total_amount', 'invoice_date', 'created_at']
    list_display_links = ['invoice_number']
    list_filter = ['invoice_type', 'invoice_date', 'created_at', 'updated_at']
    search_fields = ['invoice_number', 'order__order_number', 'user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['invoice_number', 'invoice_date', 'invoice_data', 'created_at', 'updated_at']
    list_editable = []
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Invoice Identification', {
            'fields': ('invoice_number', 'invoice_type', 'invoice_date', 'payment_due_date'),
            'description': 'Invoice number, type (customer/designer), and dates'
        }),
        ('Order & User Information', {
            'fields': ('order', 'user'),
            'description': 'Order this invoice is for and user (customer or designer)'
        }),
        ('Financial Details', {
            'fields': ('subtotal', 'gst_amount', 'commission_amount', 'total_amount'),
            'description': 'Breakdown of invoice amounts'
        }),
        ('PDF & Metadata', {
            'fields': ('pdf_file_path', 'invoice_data'),
            'description': 'PDF file path and invoice data used for generation',
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'order',
            'user'
        )
    
    def get_readonly_fields(self, request, obj=None):
        """
        Make invoice fields readonly after creation to prevent changes.
        """
        readonly = list(self.readonly_fields)
        if obj:  # Editing an existing invoice
            readonly.extend(['invoice_type', 'order', 'user', 'subtotal', 'gst_amount', 'commission_amount', 'total_amount', 'payment_due_date', 'pdf_file_path'])
        return readonly

