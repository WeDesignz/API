from django.contrib import admin
from django.utils.html import format_html
from .models import Addresses, DesignerProfile, Studio, StudioBusinessDetails, StudioMember, Ratings, DesignProcessingTask


@admin.register(Addresses)
class AddressesAdmin(admin.ModelAdmin):
    """
    Admin interface for Addresses model.
    Manages user addresses with different types and settings.
    """
    list_display = ['id', 'city', 'state', 'country', 'address_type', 'is_postal', 'created_by', 'created_at']
    list_filter = ['address_type', 'is_postal', 'is_permanent', 'state', 'country', 'created_at']
    search_fields = ['city', 'state', 'country', 'postal_code', 'address_line_1', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['address_type', 'is_postal']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Address Information', {
            'fields': ('address_line_1', 'address_line_2', 'landmark', 'city', 'state', 'country', 'postal_code')
        }),
        ('Address Settings', {
            'fields': ('address_type', 'is_postal', 'is_permanent')
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


@admin.register(DesignerProfile)
class DesignerProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for DesignerProfile model.
    Manages designer profiles with skills and verification status.
    """
    list_display = ['profile_type_display', 'status', 'is_individual', 'onboarding_completed', 'studio_info', 'created_by', 'created_at']
    list_filter = ['status', 'is_individual', 'onboarding_completed', 'created_at', 'updated_at']
    search_fields = ['bio', 'created_by__username', 'created_by__email', 'created_by__first_name', 'created_by__last_name']
    readonly_fields = ['created_at', 'updated_at', 'profile_type_display', 'studio_info', 'owned_studio_info', 'membership_info', 'access_info']
    list_editable = ['status', 'is_individual']
    list_display_links = ['created_by']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Designer Information', {
            'fields': ('bio', 'date_of_birth', 'skill_tags', 'status', 'is_individual', 'onboarding_completed')
        }),
        ('Profile Type & Studio Relationship', {
            'fields': ('profile_type_display', 'studio_info', 'owned_studio_info', 'membership_info', 'access_info'),
            'description': 'Information about whether this profile belongs to a studio owner, member, or is an individual designer.'
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
    
    def profile_type_display(self, obj):
        """Display profile type with color coding."""
        profile_type = obj.profile_type
        colors = {
            'owner': 'green',
            'member': 'blue',
            'individual': 'gray'
        }
        labels = {
            'owner': 'Studio Owner',
            'member': 'Studio Member',
            'individual': 'Individual Designer'
        }
        color = colors.get(profile_type, 'gray')
        label = labels.get(profile_type, profile_type.title())
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            label
        )
    profile_type_display.short_description = 'Profile Type'
    
    def studio_info(self, obj):
        """Display studio information (owned or member of)."""
        owned_studio = obj.get_owned_studio()
        membership = obj.get_studio_membership()
        
        if owned_studio:
            return format_html(
                '<span style="color: green;">Owner of: {}</span>',
                owned_studio.name
            )
        elif membership:
            return format_html(
                '<span style="color: blue;">Member of: {} ({})</span>',
                membership.studio.name,
                membership.get_role_display()
            )
        else:
            return format_html('<span style="color: gray;">No studio</span>')
    studio_info.short_description = 'Studio Relationship'
    
    def owned_studio_info(self, obj):
        """Display detailed owned studio information."""
        owned_studio = obj.get_owned_studio()
        if owned_studio:
            return f'Studio: {owned_studio.name} (ID: {owned_studio.id}, Status: {owned_studio.get_status_display()})'
        return 'No owned studio'
    owned_studio_info.short_description = 'Owned Studio Details'
    
    def membership_info(self, obj):
        """Display detailed membership information."""
        membership = obj.get_studio_membership()
        if membership:
            return f'Studio: {membership.studio.name} (ID: {membership.studio.id}), Role: {membership.get_role_display()}, Status: {membership.get_status_display()}'
        return 'No studio membership'
    membership_info.short_description = 'Membership Details'
    
    def access_info(self, obj):
        """Display access level information."""
        has_full_access = obj.has_full_console_access
        can_upload = obj.can_upload_designs
        
        access_parts = []
        if has_full_access:
            access_parts.append('<span style="color: green;">Full Console Access</span>')
        else:
            access_parts.append('<span style="color: orange;">Limited Access</span>')
        
        if can_upload:
            access_parts.append('<span style="color: blue;">Can Upload Designs</span>')
        else:
            access_parts.append('<span style="color: red;">Cannot Upload Designs</span>')
        
        return format_html(' | '.join(access_parts))
    access_info.short_description = 'Access Level'


@admin.register(Studio)
class StudioAdmin(admin.ModelAdmin):
    """
    Admin interface for Studio model.
    Manages design studios with industry types and capacity settings.
    """
    list_display = ['name', 'wedesignz_auto_name', 'studio_industry_type', 'status', 'daily_design_generation_capacity', 'created_by', 'created_at']
    list_filter = ['studio_industry_type', 'status', 'created_at', 'updated_at']
    search_fields = ['name', 'wedesignz_auto_name', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status', 'daily_design_generation_capacity']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Studio Information', {
            'fields': ('name', 'wedesignz_auto_name', 'studio_industry_type', 'status', 'daily_design_generation_capacity', 'remarks')
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


@admin.register(StudioBusinessDetails)
class StudioBusinessDetailsAdmin(admin.ModelAdmin):
    """
    Admin interface for StudioBusinessDetails model.
    Manages business details and legal information for studios.
    """
    list_display = ['studio', 'legal_business_name', 'business_type', 'business_category', 'created_by', 'created_at']
    list_filter = ['business_type', 'business_category', 'created_at', 'updated_at']
    search_fields = ['studio__name', 'legal_business_name', 'studio_email', 'studio_mobile_number', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Business Information', {
            'fields': ('studio', 'legal_business_name', 'studio_email', 'studio_mobile_number', 'business_type', 'business_category', 'business_sub_category', 'business_model')
        }),
        ('MSME Information', {
            'fields': ('msme_udyam_number', 'msme_certificate_annexure'),
            'classes': ('collapse',)
        }),
        ('Tax Information', {
            'fields': ('pan_number', 'pan_card', 'gst_number'),
            'classes': ('collapse',)
        }),
        ('Bank Details', {
            'fields': ('bank_account_number', 'bank_ifsc_code', 'bank_account_holder_name', 'account_type'),
            'classes': ('collapse',)
        }),
        ('Address Information', {
            'fields': ('registered_addresses_json',),
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
        return super().get_queryset(request).select_related('studio', 'created_by', 'updated_by')


@admin.register(StudioMember)
class StudioMemberAdmin(admin.ModelAdmin):
    """
    Admin interface for StudioMember model.
    Manages studio members with roles and status.
    """
    list_display = ['studio', 'member', 'role', 'status', 'created_by', 'created_at']
    list_filter = ['role', 'status', 'created_at', 'updated_at']
    search_fields = ['studio__name', 'member__username', 'member__email', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['role', 'status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Member Information', {
            'fields': ('studio', 'member', 'role', 'status')
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
        return super().get_queryset(request).select_related('studio', 'member', 'created_by', 'updated_by')


@admin.register(Ratings)
class RatingsAdmin(admin.ModelAdmin):
    """
    Admin interface for Ratings model.
    Manages ratings for studios, members, and products.
    """
    list_display = ['studio', 'studio_member', 'product', 'rating_type', 'rating_value', 'rating_title', 'status', 'created_by', 'created_at']
    list_filter = ['rating_type', 'rating_value', 'status', 'created_at', 'updated_at']
    search_fields = ['studio__name', 'studio_member__created_by__username', 'product__title', 'rating_title', 'rating_description', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['rating_value', 'status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Rating Information', {
            'fields': ('studio', 'studio_member', 'product', 'rating_type', 'rating_value', 'rating_title', 'rating_description', 'tags', 'status')
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
        return super().get_queryset(request).select_related('studio', 'studio_member', 'product', 'created_by', 'updated_by')


@admin.register(DesignProcessingTask)
class DesignProcessingTaskAdmin(admin.ModelAdmin):
    """
    Admin interface for DesignProcessingTask model.
    Manages design processing tasks and their progress.
    """
    list_display = ['id', 'user', 'status', 'progress_display', 'total_designs', 'processed_designs', 'failed_designs', 'created_at']
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = ['user__username', 'user__email', 'zip_file_path']
    readonly_fields = ['created_at', 'updated_at', 'progress_percentage']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Task Information', {
            'fields': ('user', 'zip_file_path', 'status')
        }),
        ('Progress Information', {
            'fields': ('total_designs', 'processed_designs', 'failed_designs', 'progress_percentage')
        }),
        ('Error Information', {
            'fields': ('error_message',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
    
    def progress_display(self, obj):
        """Display progress as a percentage."""
        percentage = obj.progress_percentage
        color = 'green' if obj.status == 'completed' else 'blue' if obj.status == 'processing' else 'gray'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color,
            percentage
        )
    progress_display.short_description = 'Progress'