from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    RevenueReport, TopDesignsReport, TopDesignersReport, 
    ActiveUsersReport, GrowthChart, ReportExport, AnalyticsCache
)
from Accounts.serializers import UserSerializer


class RevenueReportSerializer(serializers.ModelSerializer):
    """
    Serializer for revenue reports.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    net_revenue = serializers.SerializerMethodField()
    
    class Meta:
        model = RevenueReport
        fields = [
            'id', 'report_name', 'report_type', 'start_date', 'end_date',
            'total_revenue', 'plan_purchases_revenue', 'bundle_sales_revenue',
            'design_sales_revenue', 'custom_orders_revenue', 'total_refunds',
            'net_revenue', 'total_transactions', 'successful_transactions',
            'failed_transactions', 'refund_count', 'description', 'is_generated',
            'generated_at', 'created_by', 'created_at', 'updated_by', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'net_revenue']
    
    def get_net_revenue(self, obj):
        """Calculate net revenue after refunds."""
        return float(obj.calculate_net_revenue())


class RevenueReportCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating revenue reports.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = RevenueReport
        fields = [
            'report_name', 'report_type', 'start_date', 'end_date',
            'description', 'created_by_id'
        ]
    
    def validate(self, attrs):
        """Validate report parameters."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class TopDesignsReportSerializer(serializers.ModelSerializer):
    """
    Serializer for top designs reports.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    design_info = serializers.SerializerMethodField()
    
    class Meta:
        model = TopDesignsReport
        fields = [
            'id', 'design_id', 'design_title', 'total_sales', 'total_downloads',
            'total_views', 'average_rating', 'total_revenue', 'conversion_rate',
            'engagement_score', 'sales_rank', 'downloads_rank', 'rating_rank',
            'overall_rank', 'report_start_date', 'report_end_date',
            'created_by', 'created_at', 'updated_by', 'updated_at', 'design_info'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_design_info(self, obj):
        """Get design information via relations."""
        if obj.design:
            return {
                'id': obj.design.id,
                'title': obj.design.title,
                'description': obj.design.description,
                'price': float(obj.design.price),
                'status': obj.design.status
            }
        return None


class TopDesignersReportSerializer(serializers.ModelSerializer):
    """
    Serializer for top designers reports.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    designer_info = serializers.SerializerMethodField()
    
    class Meta:
        model = TopDesignersReport
        fields = [
            'id', 'designer_id', 'designer_name', 'total_revenue', 'approved_designs',
            'total_designs', 'total_sales', 'total_downloads', 'total_views',
            'engagement_ratio', 'conversion_rate', 'average_rating', 'revenue_rank',
            'designs_rank', 'engagement_rank', 'overall_rank', 'report_start_date',
            'report_end_date', 'created_by', 'created_at', 'updated_by', 'updated_at',
            'designer_info'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_designer_info(self, obj):
        """Get designer information via relations."""
        if obj.designer:
            return {
                'id': obj.designer.id,
                'username': obj.designer.username,
                'email': obj.designer.email,
                'first_name': obj.designer.first_name,
                'last_name': obj.designer.last_name
            }
        return None


class ActiveUsersReportSerializer(serializers.ModelSerializer):
    """
    Serializer for active users reports.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    
    class Meta:
        model = ActiveUsersReport
        fields = [
            'id', 'report_name', 'report_type', 'start_date', 'end_date',
            'total_active_users', 'new_signups', 'returning_users', 'customer_count',
            'designer_count', 'active_subscriptions', 'subscription_renewals',
            'expired_subscriptions', 'churn_rate', 'total_logins',
            'average_session_duration', 'page_views', 'created_by', 'created_at',
            'updated_by', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ActiveUsersReportCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating active users reports.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = ActiveUsersReport
        fields = [
            'report_name', 'report_type', 'start_date', 'end_date', 'created_by_id'
        ]
    
    def validate(self, attrs):
        """Validate report parameters."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class GrowthChartSerializer(serializers.ModelSerializer):
    """
    Serializer for growth chart data.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    
    class Meta:
        model = GrowthChart
        fields = [
            'id', 'chart_type', 'date', 'value', 'secondary_value', 'metadata',
            'created_by', 'created_at', 'updated_by', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ReportExportSerializer(serializers.ModelSerializer):
    """
    Serializer for report exports.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    processing_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportExport
        fields = [
            'id', 'export_type', 'export_format', 'status', 'file_path', 'file_size',
            'download_url', 'start_date', 'end_date', 'filters', 'celery_task_id',
            'error_message', 'processing_started_at', 'processing_completed_at',
            'processing_duration', 'created_by', 'created_at', 'updated_by', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'processing_duration']
    
    def get_processing_duration(self, obj):
        """Calculate processing duration."""
        if obj.processing_started_at and obj.processing_completed_at:
            duration = obj.processing_completed_at - obj.processing_started_at
            return duration.total_seconds()
        return None


class ReportExportCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating report exports.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = ReportExport
        fields = [
            'export_type', 'export_format', 'start_date', 'end_date', 'filters', 'created_by_id'
        ]
    
    def validate(self, attrs):
        """Validate export parameters."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class AnalyticsCacheSerializer(serializers.ModelSerializer):
    """
    Serializer for analytics cache.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    is_expired = serializers.SerializerMethodField()
    
    class Meta:
        model = AnalyticsCache
        fields = [
            'id', 'cache_key', 'cache_type', 'cached_data', 'expires_at',
            'is_valid', 'is_expired', 'created_by', 'created_at', 'updated_by', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_expired']
    
    def get_is_expired(self, obj):
        """Check if cache is expired."""
        return obj.is_expired()


class RevenueAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for revenue analytics requests.
    """
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    report_type = serializers.ChoiceField(
        choices=RevenueReport.REPORT_TYPE_CHOICES,
        required=False,
        allow_null=True,
        allow_blank=True
    )
    include_refunds = serializers.BooleanField(default=True, required=False, allow_null=True)
    group_by = serializers.ChoiceField(
        choices=[('day', 'Day'), ('week', 'Week'), ('month', 'Month'), ('year', 'Year')],
        required=False,
        allow_null=True,
        allow_blank=True
    )
    
    def to_internal_value(self, data):
        """Handle string boolean values from query parameters."""
        if 'include_refunds' in data:
            value = data['include_refunds']
            if isinstance(value, str):
                data = data.copy()
                data['include_refunds'] = value.lower() in ('true', '1', 'yes')
        return super().to_internal_value(data)
    
    def validate(self, attrs):
        """Validate analytics parameters."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class TopPerformersSerializer(serializers.Serializer):
    """
    Serializer for top performers analytics requests.
    """
    start_date = serializers.DateField(required=False, allow_null=True)
    end_date = serializers.DateField(required=False, allow_null=True)
    limit = serializers.IntegerField(default=10, min_value=1, max_value=100, required=False)
    sort_by = serializers.ChoiceField(
        choices=[('revenue', 'Revenue'), ('sales', 'Sales'), ('downloads', 'Downloads'), ('rating', 'Rating')],
        required=False,
        allow_null=True
    )
    report_type = serializers.ChoiceField(
        choices=[('designs', 'Designs'), ('designers', 'Designers')],
        required=False,
        allow_null=True
    )


class UserStatsSerializer(serializers.Serializer):
    """
    Serializer for user statistics requests.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    report_type = serializers.ChoiceField(
        choices=ActiveUsersReport.REPORT_TYPE_CHOICES,
        required=False
    )
    include_churn = serializers.BooleanField(default=True)
    include_engagement = serializers.BooleanField(default=True)


class GrowthChartSerializer(serializers.Serializer):
    """
    Serializer for growth chart requests.
    """
    chart_type = serializers.ChoiceField(
        choices=GrowthChart.CHART_TYPE_CHOICES,
        required=False
    )
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=[('day', 'Day'), ('week', 'Week'), ('month', 'Month')],
        required=False
    )
    include_secondary = serializers.BooleanField(default=False)


class DashboardSummarySerializer(serializers.Serializer):
    """
    Serializer for dashboard summary data.
    """
    total_revenue = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_users = serializers.IntegerField()
    total_designs = serializers.IntegerField()
    total_downloads = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    growth_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    top_design = serializers.DictField()
    top_designer = serializers.DictField()
    recent_activity = serializers.ListField(child=serializers.DictField())


class ExportRequestSerializer(serializers.Serializer):
    """
    Serializer for export requests.
    """
    export_type = serializers.ChoiceField(choices=ReportExport.EXPORT_TYPE_CHOICES)
    export_format = serializers.ChoiceField(choices=ReportExport.EXPORT_FORMAT_CHOICES)
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    filters = serializers.DictField(required=False, default=dict)
    include_charts = serializers.BooleanField(default=False)
    
    def validate(self, attrs):
        """Validate export request."""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs
