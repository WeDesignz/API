from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Email, MobileNumber, OTP


@admin.register(Email)
class EmailAdmin(admin.ModelAdmin):
    """
    Admin interface for Email model.
    Manages email addresses with verification and primary status.
    """
    list_display = ['email', 'is_verified', 'is_primary', 'created_by', 'created_at']
    list_filter = ['is_verified', 'is_primary', 'created_at']
    search_fields = ['email', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_verified', 'is_primary']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Email Information', {
            'fields': ('email', 'is_verified', 'is_primary')
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MobileNumber)
class MobileNumberAdmin(admin.ModelAdmin):
    """
    Admin interface for MobileNumber model.
    Manages mobile numbers with verification and primary status.
    """
    list_display = ['mobile_number', 'is_verified', 'is_primary', 'created_by', 'created_at']
    list_filter = ['is_verified', 'is_primary', 'created_at']
    search_fields = ['mobile_number', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_verified', 'is_primary']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Mobile Information', {
            'fields': ('mobile_number', 'is_verified', 'is_primary')
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    """
    Admin interface for OTP model.
    Manages one-time passwords for authentication and verification.
    """
    list_display = ['otp', 'otp_type', 'otp_for', 'is_verified', 'expires_at', 'created_by', 'created_at']
    list_filter = ['otp_type', 'otp_for', 'is_verified', 'created_at', 'expires_at']
    search_fields = ['otp', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_verified']
    ordering = ['-created_at']
    
    fieldsets = (
        ('OTP Information', {
            'fields': ('otp', 'otp_type', 'otp_for', 'is_verified', 'expires_at')
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Custom User admin interface.
    Enhanced user management with additional fields and improved display.
    """
    list_display = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_active', 'is_superuser', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
