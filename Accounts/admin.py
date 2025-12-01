from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import Role, Permission, PermissionHasRole


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """
    Admin interface for Role model.
    Manages user roles and permissions.
    """
    list_display = ['role', 'created_by', 'created_at']
    search_fields = ['role', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['role']
    
    fieldsets = (
        ('Role Information', {
            'fields': ('role',)
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """
    Admin interface for Permission model.
    Manages system permissions and access controls.
    """
    list_display = ['permission', 'created_by', 'created_at']
    search_fields = ['permission', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['permission']
    
    fieldsets = (
        ('Permission Information', {
            'fields': ('permission',)
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PermissionHasRole)
class PermissionHasRoleAdmin(admin.ModelAdmin):
    """
    Admin interface for PermissionHasRole model.
    Manages role-permission assignments and access control mappings.
    """
    list_display = ['role', 'permission', 'created_by', 'created_at']
    list_filter = ['role', 'permission', 'created_at']
    search_fields = ['role__role', 'permission__permission', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['role__role', 'permission__permission']
    
    fieldsets = (
        ('Role-Permission Assignment', {
            'fields': ('role', 'permission')
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