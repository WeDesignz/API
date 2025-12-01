from django.contrib import admin
from .models import RazorpayPayment, RazorpayWebhookEvent


@admin.register(RazorpayPayment)
class RazorpayPaymentAdmin(admin.ModelAdmin):
    """
    Admin interface for RazorpayPayment model.
    Manages payment transactions through Razorpay gateway.
    """
    list_display = ['razorpay_payment_id', 'order', 'amount', 'currency', 'status', 'method', 'created_by', 'created_at']
    list_filter = ['status', 'currency', 'method', 'created_at', 'updated_at']
    search_fields = ['razorpay_payment_id', 'razorpay_order_id', 'description', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('order', 'razorpay_payment_id', 'razorpay_order_id', 'amount', 'currency', 'status', 'method')
        }),
        ('Payment Details', {
            'fields': ('description', 'notes', 'fee', 'tax'),
            'classes': ('collapse',)
        }),
        ('Error Information', {
            'fields': ('error_code', 'error_description'),
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
        return super().get_queryset(request).select_related('order', 'created_by', 'updated_by')


@admin.register(RazorpayWebhookEvent)
class RazorpayWebhookEventAdmin(admin.ModelAdmin):
    """
    Admin interface for RazorpayWebhookEvent model.
    Manages webhook events from Razorpay payment gateway.
    """
    list_display = ['event_id', 'event_type', 'payment', 'processed', 'processed_at', 'created_at']
    list_filter = ['event_type', 'processed', 'created_at', 'updated_at', 'processed_at']
    search_fields = ['event_id', 'event_type', 'payment__razorpay_payment_id']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['processed']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Event Information', {
            'fields': ('event_id', 'event_type', 'payment', 'payload')
        }),
        ('Processing Status', {
            'fields': ('processed', 'processed_at', 'error_message'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('payment')