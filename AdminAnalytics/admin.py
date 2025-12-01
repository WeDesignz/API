from django.contrib import admin
from .models import (
    RevenueReport, TopDesignsReport, TopDesignersReport, 
    ActiveUsersReport, GrowthChart, ReportExport, AnalyticsCache
)


@admin.register(RevenueReport)
class RevenueReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'report_name', 'start_date', 'end_date', 'total_revenue', 'created_at']
    list_filter = ['report_type', 'created_at']
    search_fields = ['report_name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TopDesignsReport)
class TopDesignsReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'design_id', 'total_sales', 'total_downloads', 'average_rating', 'created_at']
    list_filter = ['created_at']
    search_fields = ['design_id']


@admin.register(TopDesignersReport)
class TopDesignersReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'designer_id', 'total_revenue', 'approved_designs', 'engagement_ratio', 'created_at']
    list_filter = ['created_at']
    search_fields = ['designer_id']


@admin.register(ActiveUsersReport)
class ActiveUsersReportAdmin(admin.ModelAdmin):
    list_display = ['id', 'report_name', 'start_date', 'end_date', 'total_active_users', 'created_at']
    list_filter = ['report_type', 'created_at']
    search_fields = ['report_name']


@admin.register(GrowthChart)
class GrowthChartAdmin(admin.ModelAdmin):
    list_display = ['id', 'chart_type', 'date', 'value', 'created_at']
    list_filter = ['chart_type', 'created_at']
    search_fields = ['chart_type']


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ['id', 'export_type', 'status', 'file_path', 'created_at']
    list_filter = ['export_type', 'status', 'created_at']
    search_fields = ['export_type']


@admin.register(AnalyticsCache)
class AnalyticsCacheAdmin(admin.ModelAdmin):
    list_display = ['id', 'cache_key', 'cache_type', 'expires_at', 'created_at']
    list_filter = ['cache_type', 'created_at']
    search_fields = ['cache_key']
