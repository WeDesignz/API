from django.contrib import admin
from django.http import HttpRequest
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule, SolarSchedule, ClockedSchedule
from django_celery_beat.admin import PeriodicTaskAdmin
from django_celery_results.models import TaskResult
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

# Unregister the default admin and register our custom one
admin.site.unregister(PeriodicTask)
admin.site.unregister(IntervalSchedule)
admin.site.unregister(CrontabSchedule)
admin.site.unregister(TaskResult)


class PaginatedAdminMixin:
    """
    Mixin to add pagination dropdown functionality to admin classes.
    Allows users to select how many rows to display per page.
    """
    list_max_show_all = 500  # Maximum number of items to show when "Show all" is clicked
    
    def get_list_per_page(self, request: HttpRequest) -> int:
        """
        Allow users to change the number of items per page via URL parameter.
        Usage: Add ?per_page=50 to the URL to show 50 items per page.
        Valid options: 10, 25, 50, 100, 200, 500
        """
        per_page = request.GET.get('per_page', None)
        if per_page:
            try:
                per_page_int = int(per_page)
                # Allow common pagination sizes
                if per_page_int in [10, 25, 50, 100, 200, 500]:
                    return per_page_int
            except (ValueError, TypeError):
                pass
        return self.list_per_page


# Custom Periodic Task Admin
@admin.register(PeriodicTask)
class CustomPeriodicTaskAdmin(PaginatedAdminMixin, PeriodicTaskAdmin):
    list_display = [
        'name', 'task', 'enabled', 'last_run_at', 
        'total_run_count', 'status_display'
    ]
    list_filter = ['enabled', 'task', 'last_run_at']
    search_fields = ['name', 'task', 'args', 'kwargs']
    readonly_fields = ['last_run_at', 'total_run_count']
    list_per_page = 25
    
    def status_display(self, obj):
        if obj.enabled:
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">✗ Disabled</span>')
    status_display.short_description = 'Status'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'task', 'enabled')
        }),
        ('Schedule', {
            'fields': ('interval', 'crontab', 'solar', 'clocked', 'start_time', 'last_run_at')
        }),
        ('Task Configuration', {
            'fields': ('args', 'kwargs', 'queue', 'exchange', 'routing_key', 'priority')
        }),
        ('Statistics', {
            'fields': ('total_run_count',),
            'classes': ('collapse',)
        }),
    )


# Custom Interval Schedule Admin
@admin.register(IntervalSchedule)
class CustomIntervalScheduleAdmin(PaginatedAdminMixin, admin.ModelAdmin):
    list_display = ['every', 'period']
    list_filter = ['period']
    search_fields = ['every']
    list_per_page = 25


# Custom Crontab Schedule Admin
@admin.register(CrontabSchedule)
class CustomCrontabScheduleAdmin(PaginatedAdminMixin, admin.ModelAdmin):
    list_display = ['minute', 'hour', 'day_of_week', 'day_of_month', 'month_of_year', 'timezone']
    list_filter = ['day_of_week', 'month_of_year', 'timezone']
    search_fields = ['minute', 'hour', 'day_of_week', 'day_of_month', 'month_of_year']
    list_per_page = 25


# Task Result Admin
@admin.register(TaskResult)
class TaskResultAdmin(PaginatedAdminMixin, admin.ModelAdmin):
    list_display = [
        'task_id', 'task_name', 'status', 'date_created', 'date_done', 
        'worker', 'result_display'
    ]
    list_filter = ['status', 'date_created', 'date_done', 'worker']
    search_fields = ['task_id', 'task_name', 'worker']
    readonly_fields = ['task_id', 'task_name', 'status', 'date_created', 'date_done', 'worker', 'result']
    ordering = ['-date_created']
    list_per_page = 25
    
    def result_display(self, obj):
        if obj.result:
            result_str = str(obj.result)[:100]
            if len(str(obj.result)) > 100:
                result_str += '...'
            return format_html('<code>{}</code>', result_str)
        return '-'
    result_display.short_description = 'Result'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return True


# WeDesignz Custom Tasks Admin
# Note: Custom admin site functionality has been simplified to avoid compatibility issues


# Pinterest Integration Admin
from .models import PinterestIntegration, PinterestPost, InstagramIntegration, InstagramPost


@admin.register(PinterestIntegration)
class PinterestIntegrationAdmin(admin.ModelAdmin):
    list_display = [
        'is_enabled', 'is_configured', 'is_token_valid', 'board_name', 
        'last_successful_post', 'last_error_at'
    ]
    list_filter = ['is_enabled', 'last_successful_post', 'last_error_at']
    readonly_fields = [
        'access_token', 'refresh_token', 'token_expires_at',
        'last_successful_post', 'last_error', 'last_error_at',
        'created_at', 'updated_at', 'created_by'
    ]
    
    fieldsets = (
        ('Configuration', {
            'fields': ('is_enabled', 'board_id', 'board_name')
        }),
        ('OAuth Tokens', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at'),
            'classes': ('collapse',)
        }),
        ('Status Tracking', {
            'fields': ('last_successful_post', 'last_error', 'last_error_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def is_configured(self, obj):
        return bool(obj.access_token and obj.board_id)
    is_configured.boolean = True
    is_configured.short_description = 'Configured'
    
    def is_token_valid(self, obj):
        return obj.is_token_valid()
    is_token_valid.boolean = True
    is_token_valid.short_description = 'Token Valid'
    
    def has_add_permission(self, request):
        # Only allow one instance (singleton)
        return not PinterestIntegration.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Allow deletion for re-authorization
        return True


@admin.register(PinterestPost)
class PinterestPostAdmin(PaginatedAdminMixin, admin.ModelAdmin):
    list_display = [
        'product', 'status', 'pin_id', 'retry_count', 
        'created_at', 'posted_at', 'last_retry_at', 'action_buttons'
    ]
    list_filter = ['status', 'created_at', 'posted_at']
    search_fields = ['product__title', 'product__product_number', 'pin_id', 'error_message']
    readonly_fields = [
        'product', 'pin_id', 'pin_url', 'error_message', 'retry_count',
        'created_at', 'posted_at', 'last_retry_at'
    ]
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Product Information', {
            'fields': ('product',)
        }),
        ('Pinterest Status', {
            'fields': ('status', 'pin_id', 'pin_url')
        }),
        ('Error Tracking', {
            'fields': ('error_message', 'retry_count', 'last_retry_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'posted_at'),
            'classes': ('collapse',)
        }),
    )
    
    def action_buttons(self, obj):
        if obj.status == 'failed':
            return format_html(
                '<a href="/admin/common/pinterestpost/{}/retry/" class="button">Retry</a>',
                obj.id
            )
        return '-'
    action_buttons.short_description = 'Actions'
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:post_id>/retry/',
                self.admin_site.admin_view(self.retry_post),
                name='common_pinterestpost_retry',
            ),
        ]
        return custom_urls + urls
    
    def retry_post(self, request, post_id):
        """Retry a failed Pinterest post."""
        from django.shortcuts import redirect
        from django.contrib import messages
        from .models import PinterestPost
        from .tasks import post_design_to_pinterest
        from django.conf import settings
        
        try:
            post = PinterestPost.objects.get(id=post_id)
            if post.status != 'failed':
                messages.warning(request, f'Post is not in failed status. Current status: {post.get_status_display()}')
            else:
                base_url = getattr(settings, 'SITE_DOMAIN', 'https://wedesignz.com')
                if not base_url.startswith('http'):
                    base_url = f"https://{base_url}"
                post_design_to_pinterest.delay(post.id, base_url)
                messages.success(request, f'Retry queued for Pinterest post: {post.product.title}')
        except PinterestPost.DoesNotExist:
            messages.error(request, 'Pinterest post not found')
        
        return redirect('admin:common_pinterestpost_changelist')


# Instagram Integration Admin

@admin.register(InstagramIntegration)
class InstagramIntegrationAdmin(admin.ModelAdmin):
    list_display = [
        'is_enabled', 'is_configured', 'is_token_valid', 'username', 
        'last_successful_post', 'last_error_at'
    ]
    list_filter = ['is_enabled', 'last_successful_post', 'last_error_at']
    readonly_fields = [
        'access_token', 'refresh_token', 'token_expires_at', 'user_id', 'username',
        'last_successful_post', 'last_error', 'last_error_at',
        'created_at', 'updated_at', 'created_by'
    ]
    
    fieldsets = (
        ('Configuration', {
            'fields': ('is_enabled',)
        }),
        ('OAuth Tokens', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at', 'user_id', 'username'),
            'classes': ('collapse',)
        }),
        ('Status Tracking', {
            'fields': ('last_successful_post', 'last_error', 'last_error_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def is_configured(self, obj):
        return bool(obj.access_token)
    is_configured.boolean = True
    is_configured.short_description = 'Configured'
    
    def is_token_valid(self, obj):
        return obj.is_token_valid()
    is_token_valid.boolean = True
    is_token_valid.short_description = 'Token Valid'
    
    def has_add_permission(self, request):
        # Only allow one instance (singleton)
        return not InstagramIntegration.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Allow deletion for re-authorization
        return True


@admin.register(InstagramPost)
class InstagramPostAdmin(PaginatedAdminMixin, admin.ModelAdmin):
    list_display = [
        'product', 'post_type', 'media_type', 'status', 'post_id', 'retry_count', 
        'created_at', 'posted_at', 'last_retry_at', 'action_buttons'
    ]
    list_filter = ['status', 'post_type', 'media_type', 'created_at', 'posted_at']
    search_fields = ['product__title', 'product__product_number', 'post_id', 'caption', 'error_message']
    readonly_fields = [
        'product', 'media_type', 'caption', 'post_type', 'post_id', 'media_id', 'post_url', 
        'error_message', 'retry_count',
        'created_at', 'posted_at', 'last_retry_at'
    ]
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Product Information', {
            'fields': ('product',)
        }),
        ('Post Configuration', {
            'fields': ('post_type', 'media_type', 'caption')
        }),
        ('Instagram Status', {
            'fields': ('status', 'post_id', 'media_id', 'post_url')
        }),
        ('Error Tracking', {
            'fields': ('error_message', 'retry_count', 'last_retry_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'posted_at'),
            'classes': ('collapse',)
        }),
    )
    
    def action_buttons(self, obj):
        if obj.status == 'failed':
            return format_html(
                '<a href="/admin/common/instagrampost/{}/retry/" class="button">Retry</a>',
                obj.id
            )
        return '-'
    action_buttons.short_description = 'Actions'
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:post_id>/retry/',
                self.admin_site.admin_view(self.retry_post),
                name='common_instagrampost_retry',
            ),
        ]
        return custom_urls + urls
    
    def retry_post(self, request, post_id):
        """Retry a failed Instagram post."""
        from django.shortcuts import redirect
        from django.contrib import messages
        from .models import InstagramPost
        from .tasks import post_to_instagram
        
        try:
            post = InstagramPost.objects.get(id=post_id)
            if post.status != 'failed':
                messages.warning(request, f'Post is not in failed status. Current status: {post.get_status_display()}')
            else:
                post_to_instagram.delay(post.id)
                messages.success(request, f'Retry queued for Instagram post: {post.product.title}')
        except InstagramPost.DoesNotExist:
            messages.error(request, 'Instagram post not found')
        
        return redirect('admin:common_instagrampost_changelist')
