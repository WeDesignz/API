from django.contrib import admin
from .models import Coupon, CouponUsage


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    """
    Admin interface for Coupon model.
    Manages discount coupons with various application settings and validity periods.
    """
    list_display = ['name', 'code', 'coupon_discount_type', 'discount_value', 'status', 'start_date_time', 'end_date_time', 'created_by', 'created_at']
    list_filter = ['coupon_discount_type', 'status', 'applied_to_base', 'applied_to_prime', 'applied_to_premium', 'created_at', 'updated_at']
    search_fields = ['name', 'code', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status', 'discount_value']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Coupon Information', {
            'fields': ('name', 'code', 'description', 'coupon_discount_type', 'discount_value')
        }),
        ('Application Settings', {
            'fields': ('applied_to_base', 'applied_to_prime', 'applied_to_premium')
        }),
        ('Usage Limits', {
            'fields': ('max_usage', 'max_usage_per_user', 'min_order_value'),
            'classes': ('collapse',)
        }),
        ('Validity Period', {
            'fields': ('start_date_time', 'end_date_time', 'status'),
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


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    """
    Admin interface for CouponUsage model.
    Manages coupon usage records and applied discounts.
    """
    list_display = ['coupon', 'order', 'discount_applied', 'order_amount', 'created_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['coupon__name', 'coupon__code', 'order__created_by__username', 'order__created_by__email', 'created_by__username']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Usage Information', {
            'fields': ('coupon', 'order', 'discount_applied', 'order_amount')
        }),
        ('User Information', {
            'fields': ('created_by',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('coupon', 'order', 'created_by')