from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError
from .models import (
    AdminUserProfile, AdminActivityLog, AdminSession,
    DesignerNotification, CustomerNotification, AdminNotification,
    SystemConfig
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
        'id', 'commission_rate', 'gst_percentage', 'minimum_required_designs',
        'maintenance_mode', 'updated_at'
    ]
    list_filter = ['maintenance_mode', 'updated_at', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Business Settings', {
            'fields': (
                'commission_rate',
                'gst_percentage',
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
