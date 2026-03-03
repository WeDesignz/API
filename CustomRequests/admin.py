from django.contrib import admin
from .models import CustomOrderRequest


@admin.register(CustomOrderRequest)
class CustomOrderRequestAdmin(admin.ModelAdmin):
    """
    Admin interface for CustomOrderRequest model.
    Manages custom design requests from customers.
    """
    list_display = ['title', 'status', 'payment_status', 'budget', 'sla_deadline', 'created_by', 'created_at']
    list_filter = ['status', 'payment_status', 'created_at', 'updated_at']
    search_fields = ['title', 'description', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at', 'started_at', 'completed_at', 'delivered_at', 'assigned_at']
    list_editable = ['status', 'payment_status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Request Information', {
            'fields': ('title', 'description', 'status', 'payment_status', 'budget')
        }),
        ('SLA & Delivery', {
            'fields': ('sla_deadline', 'started_at', 'completed_at', 'delivered_at', 'assigned_to_id', 'assigned_at')
        }),
        ('Cancellation & Refund', {
            'fields': ('cancellation_reason', 'cancellation_type', 'refund_amount', 'refund_reason'),
            'classes': ('collapse',)
        }),
        ('Delivery', {
            'fields': ('delivery_files_uploaded', 'delivery_message'),
            'classes': ('collapse',)
        }),
        ('Notifications', {
            'fields': ('admin_notified', 'customer_notified'),
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
        return super().get_queryset(request).select_related('created_by', 'updated_by')