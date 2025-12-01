from django.contrib import admin
from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    """
    Admin interface for Plan model.
    Manages subscription plans with pricing and duration options.
    """
    list_display = ['plan_name', 'plan_duration', 'price', 'is_most_popular', 'discount', 'status', 'created_by', 'created_at']
    list_filter = ['plan_name', 'plan_duration', 'status', 'is_most_popular', 'created_at', 'updated_at']
    search_fields = ['plan_name', 'description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['price', 'status', 'discount', 'is_most_popular']
    ordering = ['plan_name', 'plan_duration']
    list_per_page = 25
    
    fieldsets = (
        ('Plan Information', {
            'fields': ('plan_name', 'description', 'price', 'plan_duration', 'status')
        }),
        ('Plan Features', {
            'fields': ('discount', 'custom_design_hour', 'mock_pdf_count', 'no_of_free_downloads'),
            'description': 'Configure plan-specific features and limits'
        }),
        ('Marketing', {
            'fields': ('is_most_popular',),
            'description': 'Mark this plan as "Most Popular" for its duration. Only one plan per duration should be marked.'
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


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """
    Admin interface for Subscription model.
    Manages user subscriptions to various plans.
    """
    list_display = [
        'plan', 'status', 'auto_renew', 'free_downloads_used', 
        'mock_pdf_downloads_used', 'settlement_processed', 
        'current_period_downloads_used', 'created_by', 'created_at'
    ]
    list_filter = [
        'status', 'auto_renew', 'plan', 'settlement_processed', 
        'plan__plan_duration', 'created_at', 'updated_at'
    ]
    search_fields = ['plan__plan_name', 'created_by__username', 'created_by__email']
    readonly_fields = [
        'created_at', 'updated_at', 
        'get_remaining_free_downloads', 'get_remaining_mock_pdf_downloads',
        'get_current_period_info', 'get_settlement_info'
    ]
    list_editable = ['status', 'auto_renew']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Subscription Information', {
            'fields': ('plan', 'status', 'auto_renew')
        }),
        ('Usage Tracking', {
            'fields': (
                'free_downloads_used', 'mock_pdf_downloads_used', 
                'get_remaining_free_downloads', 'get_remaining_mock_pdf_downloads'
            ),
            'description': 'Track usage of plan benefits'
        }),
        ('Settlement Tracking', {
            'fields': (
                'settlement_processed', 'last_settled_month',
                'get_settlement_info'
            ),
            'description': 'Track subscription settlement status (for annual plans with monthly settlements)'
        }),
        ('Monthly Period Tracking (Annual Plans Only)', {
            'fields': (
                'current_period_downloads_used', 'current_period_start',
                'get_current_period_info'
            ),
            'description': 'Track monthly download usage for annual subscriptions (only applicable for annual plans)',
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
    
    def get_remaining_free_downloads(self, obj):
        """Display remaining free downloads."""
        if obj.pk:
            remaining = obj.get_remaining_free_downloads()
            total = obj.plan.no_of_free_downloads if hasattr(obj.plan, 'no_of_free_downloads') else 0
            return f"{remaining} / {total}"
        return "N/A"
    get_remaining_free_downloads.short_description = 'Remaining Free Downloads'
    
    def get_remaining_mock_pdf_downloads(self, obj):
        """Display remaining mock PDF downloads."""
        if obj.pk:
            remaining = obj.get_remaining_mock_pdf_downloads()
            total = obj.plan.mock_pdf_count if hasattr(obj.plan, 'mock_pdf_count') else 0
            return f"{remaining} / {total}"
        return "N/A"
    get_remaining_mock_pdf_downloads.short_description = 'Remaining Mock PDF Downloads'
    
    def get_current_period_info(self, obj):
        """Display current period information for annual plans."""
        if not obj.pk:
            return "N/A"
        
        if obj.plan.plan_duration != 'annually':
            return "N/A (Monthly plan - no monthly tracking)"
        
        period_start, period_end = obj.get_current_settlement_period()
        monthly_limit = obj.get_monthly_download_limit()
        current_used = obj.get_current_period_downloads_used()
        remaining = obj.get_remaining_monthly_downloads()
        
        info = []
        if period_start:
            info.append(f"Period: {period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}")
        if monthly_limit is not None:
            info.append(f"Monthly Limit: {monthly_limit} downloads")
        if current_used is not None:
            info.append(f"Used This Period: {current_used}")
        if remaining is not None:
            info.append(f"Remaining This Period: {remaining}")
        
        return " | ".join(info) if info else "N/A"
    get_current_period_info.short_description = 'Current Period Info'
    
    def get_settlement_info(self, obj):
        """Display settlement information."""
        if not obj.pk:
            return "N/A"
        
        info = []
        info.append(f"Settlement Processed: {'Yes' if obj.settlement_processed else 'No'}")
        
        if obj.last_settled_month:
            info.append(f"Last Settled: {obj.last_settled_month.strftime('%Y-%m-%d')}")
        else:
            info.append("Last Settled: Never")
        
        return " | ".join(info)
    get_settlement_info.short_description = 'Settlement Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('plan', 'created_by', 'updated_by')