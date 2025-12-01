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
