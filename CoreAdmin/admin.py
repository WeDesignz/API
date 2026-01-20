from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from .models import (
    AdminPermissionGroup, AdminUserProfile, AdminActivityLog, AdminSession,
    DesignApproval, DesignAnalytics, CopyrightReport, Refund, RefundLog,
    FinancialReport,
    DesignerAccountSuspension, DesignerNotification, CustomerAccountStatus,
    CustomerViewHistory, CustomerDownloadHistory, CustomerNotification,
    AdminNotification, AdminNotificationCampaign, SystemConfig
)


@admin.register(AdminUserProfile)
class AdminUserProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'admin_group', 'is_2fa_enabled', 'is_active', 
        'last_2fa_verification', 'created_at'
    ]
    list_filter = [
        'is_2fa_enabled', 'is_active', 'admin_group', 
        'last_2fa_verification', 'created_at'
    ]
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created_at', 'updated_at', 'two_factor_secret', 'backup_codes']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'admin_group', 'is_active')
        }),
        ('Two-Factor Authentication', {
            'fields': ('is_2fa_enabled', 'last_2fa_verification', 'two_factor_secret', 'backup_codes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(AdminActivityLog)
class AdminActivityLogAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'activity_type', 'description', 'ip_address', 
        'timestamp'
    ]
    list_filter = [
        'activity_type', 'timestamp'
    ]
    search_fields = [
        'user__username', 'user__email', 'description', 
        'ip_address', 'user_agent'
    ]
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    fieldsets = (
        ('Activity Information', {
            'fields': ('user', 'activity_type', 'description')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent', 'metadata'),
            'classes': ('collapse',)
        }),
        ('Timestamp', {
            'fields': ('timestamp',)
        })
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_add_permission(self, request):
        return False  # Activity logs are created programmatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Activity logs should not be modified
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete logs


@admin.register(AdminSession)
class AdminSessionAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'session_key_short', 'ip_address', 'is_active', 
        'last_activity', 'created_at'
    ]
    list_filter = ['is_active', 'last_activity', 'created_at']
    search_fields = ['user__username', 'user__email', 'ip_address', 'user_agent', 'session_key']
    readonly_fields = ['created_at', 'session_key', 'user_agent', 'ip_address']
    
    fieldsets = (
        ('Session Information', {
            'fields': ('user', 'session_key', 'is_active')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Activity', {
            'fields': ('last_activity',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        })
    )
    
    def session_key_short(self, obj):
        return f"{obj.session_key[:8]}..." if obj.session_key else "N/A"
    session_key_short.short_description = 'Session Key'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def has_add_permission(self, request):
        return False  # Sessions are created programmatically


@admin.register(DesignerNotification)
class DesignerNotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'designer_name', 'notification_type', 'title', 'priority',
        'is_read', 'email_sent', 'push_sent', 'created_at'
    ]
    list_filter = [
        'notification_type', 'priority', 'is_read', 
        'email_sent', 'push_sent', 'created_at', 'is_scheduled'
    ]
    search_fields = [
        'title', 'message', 'designer_id'
    ]
    readonly_fields = [
        'created_at', 'read_at', 'email_sent_at', 'push_sent_at',
        'scheduled_at', 'is_scheduled'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('designer_id', 'notification_type', 'title', 'message', 'priority')
        }),
        ('Delivery Status', {
            'fields': ('email_sent', 'email_sent_at', 'push_sent', 'push_sent_at'),
            'classes': ('collapse',)
        }),
        ('Read Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Scheduling', {
            'fields': ('is_scheduled', 'scheduled_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def designer_name(self, obj):
        """Get designer name directly from designer_id"""
        try:
            from django.contrib.auth.models import User
            if hasattr(obj, 'designer_id') and obj.designer_id:
                try:
                    designer = User.objects.get(id=obj.designer_id)
                    full_name = designer.get_full_name()
                    if full_name:
                        return full_name
                    return designer.username or designer.email or 'Unknown'
                except User.DoesNotExist:
                    return f'User ID {obj.designer_id} (Not Found)'
            return 'Unknown'
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error getting designer name in admin: {e}')
            return f'Error: {str(e)}'
    designer_name.short_description = 'Designer'
    
    def get_queryset(self, request):
        return super().get_queryset(request)


@admin.register(CustomerNotification)
class CustomerNotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'customer_name', 'notification_type', 'title', 'priority',
        'is_read', 'email_sent', 'push_sent', 'created_at'
    ]
    list_filter = [
        'notification_type', 'priority', 'is_read',
        'email_sent', 'push_sent', 'created_at', 'is_scheduled'
    ]
    search_fields = [
        'title', 'message', 'customer_id'
    ]
    readonly_fields = [
        'created_at', 'read_at', 'email_sent_at', 'push_sent_at',
        'scheduled_at', 'is_scheduled'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('customer_id', 'notification_type', 'title', 'message', 'priority')
        }),
        ('Delivery Status', {
            'fields': ('email_sent', 'email_sent_at', 'push_sent', 'push_sent_at'),
            'classes': ('collapse',)
        }),
        ('Read Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Scheduling', {
            'fields': ('is_scheduled', 'scheduled_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def customer_name(self, obj):
        """Get customer name directly from customer_id"""
        try:
            from django.contrib.auth.models import User
            if hasattr(obj, 'customer_id') and obj.customer_id:
                try:
                    customer = User.objects.get(id=obj.customer_id)
                    full_name = customer.get_full_name()
                    if full_name:
                        return full_name
                    return customer.username or customer.email or 'Unknown'
                except User.DoesNotExist:
                    return f'User ID {obj.customer_id} (Not Found)'
            return 'Unknown'
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error getting customer name in admin: {e}')
            return f'Error: {str(e)}'
    customer_name.short_description = 'Customer'
    
    def get_queryset(self, request):
        return super().get_queryset(request)


@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'admin_name', 'notification_type', 'title',
        'is_read', 'email_sent', 'push_sent', 'created_at'
    ]
    list_filter = [
        'notification_type', 'is_read',
        'email_sent', 'push_sent', 'created_at'
    ]
    search_fields = [
        'title', 'message', 'admin_id'
    ]
    readonly_fields = [
        'created_at', 'read_at', 'email_sent_at', 'push_sent_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('admin_id', 'notification_type', 'title', 'message')
        }),
        ('Related Objects', {
            'fields': ('related_thread_id', 'related_order_id'),
            'classes': ('collapse',)
        }),
        ('Delivery Status', {
            'fields': ('email_sent', 'email_sent_at', 'push_sent', 'push_sent_at'),
            'classes': ('collapse',)
        }),
        ('Read Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    def admin_name(self, obj):
        """Get admin name directly from admin_id"""
        try:
            from django.contrib.auth.models import User
            if hasattr(obj, 'admin_id') and obj.admin_id:
                try:
                    admin_user = User.objects.get(id=obj.admin_id)
                    full_name = admin_user.get_full_name()
                    if full_name:
                        return full_name
                    return admin_user.username or admin_user.email or 'Unknown'
                except User.DoesNotExist:
                    return f'User ID {obj.admin_id} (Not Found)'
            return 'Unknown'
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error getting admin name in admin: {e}')
            return f'Error: {str(e)}'
    admin_name.short_description = 'Admin'
    
    def get_queryset(self, request):
        return super().get_queryset(request)


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    """
    Admin interface for System Configuration (Singleton model).
    Only one instance should exist.
    """
    list_display = [
        'id', 'commission_rate', 'gst_percentage', 'design_price', 'custom_order_price', 'minimum_required_designs',
        'maintenance_mode', 'updated_at'
    ]
    list_filter = ['maintenance_mode', 'updated_at', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Business Settings', {
            'fields': (
                'commission_rate',
                'gst_percentage',
                'design_price',
                'custom_order_price',
                'custom_order_time_slot_hours',
                'minimum_required_designs',
            )
        }),
        ('System Status', {
            'fields': ('maintenance_mode',)
        }),
        ('Landing Page - Hero Section', {
            'fields': ('hero_section_designs',),
            'description': 'Array of product IDs to display in hero section CardSwap (3-5 recommended)',
            'classes': ('collapse',)
        }),
        ('Landing Page - Featured Designs', {
            'fields': ('featured_designs',),
            'description': 'Array of product IDs for Featured Designs slider',
            'classes': ('collapse',)
        }),
        ('Landing Page - Dome Gallery', {
            'fields': ('dome_gallery_designs',),
            'description': 'Array of product IDs for 3D dome gallery (50+ recommended)',
            'classes': ('collapse',)
        }),
        ('Landing Page Statistics', {
            'fields': ('landing_page_stats',),
            'description': 'Statistics displayed on landing page (totalClients, totalDesigners, totalDesignAssets)',
            'classes': ('collapse',)
        }),
        ('Client Names', {
            'fields': ('client_names',),
            'description': 'Array of client names for client names slider',
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def has_add_permission(self, request):
        """Only allow adding if no instance exists"""
        return SystemConfig.objects.count() == 0
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of the singleton instance"""
        return False
    
    def get_queryset(self, request):
        """Only show the singleton instance"""
        qs = super().get_queryset(request)
        # Ensure singleton exists
        SystemConfig.get_config()
        return qs
    
    def save_model(self, request, obj, form, change):
        """Ensure only one instance exists"""
        if not change:  # Creating new instance
            if SystemConfig.objects.exists():
                raise ValidationError(
                    "System Configuration already exists. Only one instance is allowed. "
                    "Please edit the existing instance instead."
                )
        super().save_model(request, obj, form, change)
    
    def changelist_view(self, request, extra_context=None):
        """Redirect to the singleton instance if it exists"""
        config = SystemConfig.get_config()
        if config:
            from django.shortcuts import redirect
            return redirect(f'/admin/CoreAdmin/systemconfig/{config.pk}/change/')
        return super().changelist_view(request, extra_context)


@admin.register(AdminPermissionGroup)
class AdminPermissionGroupAdmin(admin.ModelAdmin):
    """
    Admin interface for AdminPermissionGroup model.
    Manages permission groups for admin users.
    """
    list_display = ['name', 'is_active', 'permission_count', 'created_at', 'updated_at']
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_active']
    ordering = ['name']
    
    fieldsets = (
        ('Group Information', {
            'fields': ('name', 'description', 'is_active')
        }),
        ('Permissions', {
            'fields': ('permissions',),
            'description': 'List of permission strings in this group'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def permission_count(self, obj):
        """Display number of permissions in this group"""
        return obj.get_permission_count()
    permission_count.short_description = 'Permission Count'


@admin.register(DesignApproval)
class DesignApprovalAdmin(admin.ModelAdmin):
    """
    Admin interface for DesignApproval model.
    Manages design approval history and status changes.
    """
    list_display = ['id', 'product_id', 'action', 'approved_by_display', 'approved_at', 'created_at']
    list_filter = ['action', 'created_at', 'approved_at']
    search_fields = ['product_id', 'admin_notes', 'rejection_reason', 'ip_address']
    readonly_fields = ['created_at', 'approved_at']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Approval Information', {
            'fields': ('product_id', 'action', 'admin_notes', 'rejection_reason')
        }),
        ('Approval Details', {
            'fields': ('approved_by_id', 'approved_at'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def approved_by_display(self, obj):
        """Display approved by user"""
        if obj.approved_by_id:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(pk=obj.approved_by_id)
                return user.username or user.email
            except User.DoesNotExist:
                return f'User ID {obj.approved_by_id} (Not Found)'
        return '-'
    approved_by_display.short_description = 'Approved By'


@admin.register(DesignAnalytics)
class DesignAnalyticsAdmin(admin.ModelAdmin):
    """
    Admin interface for DesignAnalytics model.
    Manages design analytics and performance metrics.
    """
    list_display = ['id', 'product_id', 'total_views', 'total_downloads', 'total_purchases', 'total_revenue', 'trending_score', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['product_id']
    readonly_fields = ['created_at', 'updated_at', 'last_viewed_at', 'last_downloaded_at', 'last_purchased_at']
    ordering = ['-trending_score', '-total_views']
    list_per_page = 25
    
    fieldsets = (
        ('Product Information', {
            'fields': ('product_id',)
        }),
        ('Analytics Metrics', {
            'fields': ('total_views', 'total_downloads', 'total_purchases', 'total_revenue', 'average_rating', 'trending_score')
        }),
        ('Last Activity', {
            'fields': ('last_viewed_at', 'last_downloaded_at', 'last_purchased_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CopyrightReport)
class CopyrightReportAdmin(admin.ModelAdmin):
    """
    Admin interface for CopyrightReport model.
    Manages copyright violation reports for designs.
    """
    list_display = ['id', 'product_id', 'reporter_display', 'title', 'priority', 'status', 'resolved_by_display', 'created_at']
    list_filter = ['status', 'priority', 'created_at', 'resolved_at']
    search_fields = ['title', 'description', 'product_id', 'reporter_id', 'resolution', 'admin_notes']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']
    list_editable = ['status', 'priority']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Report Information', {
            'fields': ('product_id', 'reporter_id', 'title', 'description', 'priority', 'status')
        }),
        ('Resolution Details', {
            'fields': ('resolution', 'admin_notes', 'resolved_by_id', 'resolved_at'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def reporter_display(self, obj):
        """Display reporter user"""
        if obj.reporter_id:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(pk=obj.reporter_id)
                return user.username or user.email
            except User.DoesNotExist:
                return f'User ID {obj.reporter_id} (Not Found)'
        return '-'
    reporter_display.short_description = 'Reporter'
    
    def resolved_by_display(self, obj):
        """Display resolved by user"""
        if obj.resolved_by_id:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(pk=obj.resolved_by_id)
                return user.username or user.email
            except User.DoesNotExist:
                return f'User ID {obj.resolved_by_id} (Not Found)'
        return '-'
    resolved_by_display.short_description = 'Resolved By'


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    """
    Admin interface for Refund model.
    Manages refunds for transactions.
    """
    list_display = ['id', 'order_id', 'refund_amount', 'status', 'razorpay_refund_id', 'processed_by_display', 'created_at']
    list_filter = ['status', 'created_at', 'processed_at']
    search_fields = ['order_id', 'refund_reason', 'razorpay_refund_id', 'razorpay_payment_id', 'admin_notes']
    readonly_fields = ['created_at', 'updated_at', 'processed_at']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Refund Information', {
            'fields': ('order_id', 'refund_amount', 'refund_reason', 'status')
        }),
        ('Razorpay Details', {
            'fields': ('razorpay_refund_id', 'razorpay_payment_id'),
            'classes': ('collapse',)
        }),
        ('Processing Details', {
            'fields': ('processed_by_id', 'processed_at', 'admin_notes'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def processed_by_display(self, obj):
        """Display processed by user"""
        if obj.processed_by_id:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(pk=obj.processed_by_id)
                return user.username or user.email
            except User.DoesNotExist:
                return f'User ID {obj.processed_by_id} (Not Found)'
        return '-'
    processed_by_display.short_description = 'Processed By'


@admin.register(RefundLog)
class RefundLogAdmin(admin.ModelAdmin):
    """
    Admin interface for RefundLog model.
    Manages refund activity logs.
    """
    list_display = ['id', 'refund_id', 'action', 'admin_user_display', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['refund_id', 'description', 'admin_user_id']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Log Information', {
            'fields': ('refund_id', 'action', 'description', 'admin_user_id')
        }),
        ('Audit Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def admin_user_display(self, obj):
        """Display admin user"""
        if obj.admin_user_id:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(pk=obj.admin_user_id)
                return user.username or user.email
            except User.DoesNotExist:
                return f'User ID {obj.admin_user_id} (Not Found)'
        return '-'
    admin_user_display.short_description = 'Admin User'


@admin.register(FinancialReport)
class FinancialReportAdmin(admin.ModelAdmin):
    """
    Admin interface for FinancialReport model.
    Manages generated financial reports.
    """
    list_display = ['id', 'report_type', 'period_start', 'period_end', 'total_transactions', 'total_amount', 'net_revenue', 'generated_at']
    list_filter = ['report_type', 'generated_at']
    search_fields = ['report_type', 'csv_file_path', 'pdf_file_path']
    readonly_fields = ['generated_at', 'report_data']
    ordering = ['-generated_at']
    list_per_page = 25
    
    fieldsets = (
        ('Report Information', {
            'fields': ('report_type', 'period_start', 'period_end', 'generated_by_id')
        }),
        ('Financial Metrics', {
            'fields': ('total_transactions', 'total_amount', 'total_refunds', 'net_revenue')
        }),
        ('Transaction Breakdown', {
            'fields': ('plan_sales', 'bundle_sales', 'design_sales', 'custom_order_sales', 'designer_payouts'),
            'classes': ('collapse',)
        }),
        ('Additional Metrics', {
            'fields': ('pending_settlements', 'platform_commission'),
            'classes': ('collapse',)
        }),
        ('File Storage', {
            'fields': ('csv_file_path', 'pdf_file_path'),
            'classes': ('collapse',)
        }),
        ('Report Data', {
            'fields': ('report_data',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('generated_at',),
            'classes': ('collapse',)
        }),
    )


# DesignerOnboardingStatus model is deprecated - using DesignerProfile.status instead
# @admin.register(DesignerOnboardingStatus)
# class DesignerOnboardingStatusAdmin(admin.ModelAdmin):
#     """
#     Admin interface for DesignerOnboardingStatus model.
#     DEPRECATED: This model is no longer used. Use DesignerProfile.status instead.
#     """
#     pass


@admin.register(DesignerAccountSuspension)
class DesignerAccountSuspensionAdmin(admin.ModelAdmin):
    """
    Admin interface for DesignerAccountSuspension model.
    Manages designer account suspensions and deletions.
    """
    list_display = ['id', 'designer_id', 'is_suspended', 'is_deleted', 'suspension_reason', 'suspended_by_display', 'suspended_at', 'created_at']
    list_filter = ['is_suspended', 'is_deleted', 'suspension_reason', 'created_at', 'suspended_at', 'deleted_at']
    search_fields = ['designer_id', 'suspension_notes', 'deletion_notes', 'suspended_by_id', 'deleted_by_id']
    readonly_fields = ['created_at', 'updated_at', 'suspended_at', 'deleted_at']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Designer Information', {
            'fields': ('designer_id', 'is_suspended', 'is_deleted')
        }),
        ('Suspension Details', {
            'fields': ('suspension_reason', 'suspension_notes', 'suspended_by_id', 'suspended_at'),
            'classes': ('collapse',)
        }),
        ('Deletion Details', {
            'fields': ('deletion_reason', 'deletion_notes', 'deleted_by_id', 'deleted_at'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def suspended_by_display(self, obj):
        """Display suspended by user"""
        if obj.suspended_by_id:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(pk=obj.suspended_by_id)
                return user.username or user.email
            except User.DoesNotExist:
                return f'User ID {obj.suspended_by_id} (Not Found)'
        return '-'
    suspended_by_display.short_description = 'Suspended By'


@admin.register(CustomerAccountStatus)
class CustomerAccountStatusAdmin(admin.ModelAdmin):
    """
    Admin interface for CustomerAccountStatus model.
    Manages customer account status and management.
    """
    list_display = ['id', 'customer_id', 'status', 'deactivation_reason', 'deactivated_by_display', 'deactivated_at', 'created_at']
    list_filter = ['status', 'deactivation_reason', 'created_at', 'deactivated_at', 'reactivated_at']
    search_fields = ['customer_id', 'deactivation_notes', 'deactivated_by_id', 'reactivated_by_id']
    readonly_fields = ['created_at', 'updated_at', 'deactivated_at', 'reactivated_at']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Customer Information', {
            'fields': ('customer_id', 'status')
        }),
        ('Deactivation Details', {
            'fields': ('deactivation_reason', 'deactivation_notes', 'deactivated_by_id', 'deactivated_at'),
            'classes': ('collapse',)
        }),
        ('Reactivation Details', {
            'fields': ('reactivated_by_id', 'reactivated_at'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def deactivated_by_display(self, obj):
        """Display deactivated by user"""
        if obj.deactivated_by_id:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(pk=obj.deactivated_by_id)
                return user.username or user.email
            except User.DoesNotExist:
                return f'User ID {obj.deactivated_by_id} (Not Found)'
        return '-'
    deactivated_by_display.short_description = 'Deactivated By'


@admin.register(CustomerViewHistory)
class CustomerViewHistoryAdmin(admin.ModelAdmin):
    """
    Admin interface for CustomerViewHistory model.
    Manages customer view history.
    """
    list_display = ['id', 'customer_id', 'view_type', 'item_id', 'item_title', 'viewed_at']
    list_filter = ['view_type', 'viewed_at']
    search_fields = ['customer_id', 'item_title', 'item_category', 'session_id', 'ip_address']
    readonly_fields = ['viewed_at']
    ordering = ['-viewed_at']
    list_per_page = 25
    
    fieldsets = (
        ('View Information', {
            'fields': ('customer_id', 'view_type', 'item_id', 'item_title', 'item_category', 'session_id')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('viewed_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(CustomerDownloadHistory)
class CustomerDownloadHistoryAdmin(admin.ModelAdmin):
    """
    Admin interface for CustomerDownloadHistory model.
    Manages customer download history.
    """
    list_display = ['id', 'customer_id', 'download_type', 'item_id', 'item_title', 'file_name', 'file_size', 'downloaded_at']
    list_filter = ['download_type', 'downloaded_at']
    search_fields = ['customer_id', 'item_title', 'file_name', 'download_source', 'ip_address']
    readonly_fields = ['downloaded_at']
    ordering = ['-downloaded_at']
    list_per_page = 25
    
    fieldsets = (
        ('Download Information', {
            'fields': ('customer_id', 'download_type', 'item_id', 'item_title', 'file_name', 'file_size', 'download_source')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('downloaded_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(AdminNotificationCampaign)
class AdminNotificationCampaignAdmin(admin.ModelAdmin):
    """
    Admin interface for AdminNotificationCampaign model.
    Manages admin-created notification campaigns.
    """
    list_display = ['id', 'title', 'priority', 'send_to_designers', 'send_to_customers', 'delivery_method', 'status', 'scheduled_at', 'sent_at', 'created_at']
    list_filter = ['status', 'priority', 'delivery_method', 'send_to_designers', 'send_to_customers', 'created_at', 'sent_at']
    search_fields = ['title', 'message', 'admin_id']
    readonly_fields = ['created_at', 'updated_at', 'sent_at', 'total_recipients', 'designers_count', 'customers_count']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Campaign Information', {
            'fields': ('admin_id', 'title', 'message', 'priority')
        }),
        ('Recipients', {
            'fields': ('send_to_designers', 'send_to_customers')
        }),
        ('Delivery Settings', {
            'fields': ('delivery_method',)
        }),
        ('Status & Scheduling', {
            'fields': ('status', 'scheduled_at', 'sent_at')
        }),
        ('Statistics', {
            'fields': ('total_recipients', 'designers_count', 'customers_count'),
            'classes': ('collapse',)
        }),
        ('Celery Task Tracking', {
            'fields': ('celery_task_id',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
