from django.contrib import admin
from .models import (
    RevenueReport, TopDesignsReport, TopDesignersReport, 
    ActiveUsersReport, GrowthChart, ReportExport, AnalyticsCache
)


@admin.register(RevenueReport)
class RevenueReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'report_name', 'report_type', 'start_date', 'end_date', 'total_revenue', 'net_revenue', 'is_generated', 'created_at']
    list_filter = ['report_type', 'is_generated', 'created_at']
    search_fields = ['report_name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'generated_at']

    fieldsets = (
        ('Report Information', {
            'fields': ('report_name', 'report_type', 'start_date', 'end_date', 'description', 'is_generated', 'generated_at')
        }),
        ('Revenue Metrics', {
            'fields': ('total_revenue', 'plan_purchases_revenue', 'bundle_sales_revenue', 'design_sales_revenue', 'custom_orders_revenue', 'total_refunds', 'net_revenue')
        }),
        ('Transaction Metrics', {
            'fields': ('total_transactions', 'successful_transactions', 'failed_transactions', 'refund_count'),
            'classes': ('collapse',)
        }),
        ('User & Timestamps', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TopDesignsReport)
class TopDesignsReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'design_id', 'design_title', 'total_sales', 'total_downloads', 'total_revenue', 'overall_rank', 'created_at']
    list_filter = ['created_at']
    search_fields = ['design_id', 'design_title']

    fieldsets = (
        ('Design', {
            'fields': ('design_id', 'design_title')
        }),
        ('Metrics', {
            'fields': ('total_sales', 'total_downloads', 'total_views', 'average_rating', 'total_revenue', 'conversion_rate', 'engagement_score')
        }),
        ('Ranking', {
            'fields': ('sales_rank', 'downloads_rank', 'rating_rank', 'overall_rank')
        }),
        ('Date Range', {
            'fields': ('report_start_date', 'report_end_date')
        }),
        ('User & Timestamps', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TopDesignersReport)
class TopDesignersReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'designer_id', 'designer_name', 'total_revenue', 'approved_designs', 'engagement_ratio', 'overall_rank', 'created_at']
    list_filter = ['created_at']
    search_fields = ['designer_id', 'designer_name']

    fieldsets = (
        ('Designer', {
            'fields': ('designer_id', 'designer_name')
        }),
        ('Metrics', {
            'fields': ('total_revenue', 'approved_designs', 'total_designs', 'total_sales', 'total_downloads', 'total_views', 'engagement_ratio', 'conversion_rate', 'average_rating')
        }),
        ('Ranking', {
            'fields': ('revenue_rank', 'designs_rank', 'engagement_rank', 'overall_rank')
        }),
        ('Date Range', {
            'fields': ('report_start_date', 'report_end_date')
        }),
        ('User & Timestamps', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ActiveUsersReport)
class ActiveUsersReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'report_name', 'report_type', 'start_date', 'end_date', 'total_active_users', 'created_at']
    list_filter = ['report_type', 'created_at']
    search_fields = ['report_name']

    fieldsets = (
        ('Report Information', {
            'fields': ('report_name', 'report_type', 'start_date', 'end_date')
        }),
        ('User Metrics', {
            'fields': ('total_active_users', 'new_signups', 'returning_users', 'customer_count', 'designer_count')
        }),
        ('Subscription Metrics', {
            'fields': ('active_subscriptions', 'subscription_renewals', 'expired_subscriptions', 'churn_rate'),
            'classes': ('collapse',)
        }),
        ('Activity', {
            'fields': ('total_logins', 'average_session_duration', 'page_views'),
            'classes': ('collapse',)
        }),
        ('User & Timestamps', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(GrowthChart)
class GrowthChartAdmin(admin.ModelAdmin):
    list_display = ['id', 'chart_type', 'date', 'value', 'secondary_value', 'created_at']
    list_filter = ['chart_type', 'created_at']
    search_fields = ['chart_type']

    fieldsets = (
        ('Chart Data', {
            'fields': ('chart_type', 'date', 'value', 'secondary_value', 'metadata')
        }),
        ('User & Timestamps', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ['id', 'export_type', 'export_format', 'status', 'file_path', 'created_by', 'created_at']
    list_filter = ['export_type', 'export_format', 'status', 'created_at']
    search_fields = ['export_type', 'file_path']

    fieldsets = (
        ('Export Information', {
            'fields': ('export_type', 'export_format', 'status')
        }),
        ('File', {
            'fields': ('file_path', 'file_size', 'download_url')
        }),
        ('Parameters', {
            'fields': ('start_date', 'end_date', 'filters'),
            'classes': ('collapse',)
        }),
        ('Processing', {
            'fields': ('celery_task_id', 'error_message', 'processing_started_at', 'processing_completed_at'),
            'classes': ('collapse',)
        }),
        ('User & Timestamps', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AnalyticsCache)
class AnalyticsCacheAdmin(admin.ModelAdmin):
    list_display = ['id', 'cache_key', 'cache_type', 'expires_at', 'is_valid', 'created_at']
    list_filter = ['cache_type', 'is_valid', 'created_at']
    search_fields = ['cache_key']

    fieldsets = (
        ('Cache Information', {
            'fields': ('cache_key', 'cache_type', 'cached_data', 'expires_at', 'is_valid')
        }),
        ('User & Timestamps', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
