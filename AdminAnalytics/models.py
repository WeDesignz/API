from django.db import models
from django.contrib.auth.models import User
from common.relations import attach_relation, get_related_ids, get_related, detach_relation


class RevenueReport(models.Model):
    """
    Model for storing revenue and financial insights reports.
    """
    REPORT_TYPE_CHOICES = [
        ('daily', 'Daily'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Range'),
    ]
    
    report_name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Revenue metrics
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    plan_purchases_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    bundle_sales_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    design_sales_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    custom_orders_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_refunds = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    net_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    # Additional metrics
    total_transactions = models.IntegerField(default=0)
    successful_transactions = models.IntegerField(default=0)
    failed_transactions = models.IntegerField(default=0)
    refund_count = models.IntegerField(default=0)
    
    # Metadata
    description = models.TextField(blank=True, null=True)
    is_generated = models.BooleanField(default=False)
    generated_at = models.DateTimeField(null=True, blank=True)
    
    # Standard fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_revenue_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_revenue_reports', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'revenue_report'
        verbose_name = 'Revenue Report'
        verbose_name_plural = 'Revenue Reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.report_name} ({self.report_type}) - {self.start_date.date()} to {self.end_date.date()}"
    
    def calculate_net_revenue(self):
        """Calculate net revenue after refunds."""
        self.net_revenue = self.total_revenue - self.total_refunds
        return self.net_revenue


class TopDesignsReport(models.Model):
    """
    Model for storing top performing designs analytics.
    """
    design_id = models.IntegerField(help_text="ID of the design/product")
    design_title = models.CharField(max_length=200, blank=True, null=True)
    
    # Performance metrics
    total_sales = models.IntegerField(default=0)
    total_downloads = models.IntegerField(default=0)
    total_views = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    # Engagement metrics
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    engagement_score = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Ranking
    sales_rank = models.IntegerField(default=0)
    downloads_rank = models.IntegerField(default=0)
    rating_rank = models.IntegerField(default=0)
    overall_rank = models.IntegerField(default=0)
    
    # Date range for this report
    report_start_date = models.DateTimeField()
    report_end_date = models.DateTimeField()
    
    # Standard fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_top_designs_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_top_designs_reports', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'top_designs_report'
        verbose_name = 'Top Designs Report'
        verbose_name_plural = 'Top Designs Reports'
        ordering = ['overall_rank', '-total_revenue']
    
    def __str__(self):
        return f"Design {self.design_id} - Rank {self.overall_rank} (Revenue: {self.total_revenue})"
    
    @property
    def design(self):
        """Get the related design via relations."""
        if self.design_id:
            from common.relations import get_related
            from Catalog.models import Product
            designs = get_related(self, 'TopDesignsReport:Product', Product)
            return designs.first() if designs.exists() else None
        return None
    
    def set_design(self, design_obj):
        """Set the related design via relations."""
        if design_obj:
            self.design_id = design_obj.pk
            attach_relation('TopDesignsReport:Product', self, design_obj)
        else:
            self.design_id = None


class TopDesignersReport(models.Model):
    """
    Model for storing top performing designers analytics.
    """
    designer_id = models.IntegerField(help_text="ID of the designer/user")
    designer_name = models.CharField(max_length=200, blank=True, null=True)
    
    # Performance metrics
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    approved_designs = models.IntegerField(default=0)
    total_designs = models.IntegerField(default=0)
    total_sales = models.IntegerField(default=0)
    total_downloads = models.IntegerField(default=0)
    total_views = models.IntegerField(default=0)
    
    # Engagement metrics
    engagement_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    conversion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    # Ranking
    revenue_rank = models.IntegerField(default=0)
    designs_rank = models.IntegerField(default=0)
    engagement_rank = models.IntegerField(default=0)
    overall_rank = models.IntegerField(default=0)
    
    # Date range for this report
    report_start_date = models.DateTimeField()
    report_end_date = models.DateTimeField()
    
    # Standard fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_top_designers_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_top_designers_reports', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'top_designers_report'
        verbose_name = 'Top Designers Report'
        verbose_name_plural = 'Top Designers Reports'
        ordering = ['overall_rank', '-total_revenue']
    
    def __str__(self):
        return f"Designer {self.designer_id} - Rank {self.overall_rank} (Revenue: {self.total_revenue})"
    
    @property
    def designer(self):
        """Get the related designer via relations."""
        if self.designer_id:
            from common.relations import get_related
            from django.contrib.auth.models import User
            users = get_related(self, 'TopDesignersReport:User', User)
            return users.first() if users.exists() else None
        return None
    
    def set_designer(self, designer_obj):
        """Set the related designer via relations."""
        if designer_obj:
            self.designer_id = designer_obj.pk
            attach_relation('TopDesignersReport:User', self, designer_obj)
        else:
            self.designer_id = None


class ActiveUsersReport(models.Model):
    """
    Model for storing active user statistics.
    """
    REPORT_TYPE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom Range'),
    ]
    
    report_name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # User metrics
    total_active_users = models.IntegerField(default=0)
    new_signups = models.IntegerField(default=0)
    returning_users = models.IntegerField(default=0)
    customer_count = models.IntegerField(default=0)
    designer_count = models.IntegerField(default=0)
    
    # Subscription metrics
    active_subscriptions = models.IntegerField(default=0)
    subscription_renewals = models.IntegerField(default=0)
    expired_subscriptions = models.IntegerField(default=0)
    churn_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    # Activity metrics
    total_logins = models.IntegerField(default=0)
    average_session_duration = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    page_views = models.IntegerField(default=0)
    
    # Standard fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_active_users_reports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_active_users_reports', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'active_users_report'
        verbose_name = 'Active Users Report'
        verbose_name_plural = 'Active Users Reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.report_name} ({self.report_type}) - {self.total_active_users} active users"
    
    def calculate_churn_rate(self):
        """Calculate churn rate based on expired vs renewed subscriptions."""
        if self.subscription_renewals > 0:
            self.churn_rate = (self.expired_subscriptions / (self.subscription_renewals + self.expired_subscriptions)) * 100
        return self.churn_rate


class GrowthChart(models.Model):
    """
    Model for storing growth chart data points.
    """
    CHART_TYPE_CHOICES = [
        ('sales_growth', 'Sales Growth'),
        ('subscription_growth', 'Subscription Growth'),
        ('user_registrations', 'User Registrations'),
        ('revenue_growth', 'Revenue Growth'),
        ('design_uploads', 'Design Uploads'),
        ('downloads', 'Downloads'),
    ]
    
    chart_type = models.CharField(max_length=50, choices=CHART_TYPE_CHOICES)
    date = models.DateField()
    value = models.DecimalField(max_digits=15, decimal_places=2)
    
    # Additional metrics for the same date
    secondary_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Standard fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_growth_charts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_growth_charts', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'growth_chart'
        verbose_name = 'Growth Chart'
        verbose_name_plural = 'Growth Charts'
        ordering = ['chart_type', 'date']
        unique_together = ['chart_type', 'date']
    
    def __str__(self):
        return f"{self.get_chart_type_display()} - {self.date}: {self.value}"


class ReportExport(models.Model):
    """
    Model for tracking report exports.
    """
    EXPORT_TYPE_CHOICES = [
        ('revenue_report', 'Revenue Report'),
        ('top_designs', 'Top Designs Report'),
        ('top_designers', 'Top Designers Report'),
        ('active_users', 'Active Users Report'),
        ('growth_charts', 'Growth Charts'),
        ('custom', 'Custom Report'),
    ]
    
    EXPORT_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('pdf', 'PDF'),
        ('json', 'JSON'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    export_type = models.CharField(max_length=50, choices=EXPORT_TYPE_CHOICES)
    export_format = models.CharField(max_length=10, choices=EXPORT_FORMAT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # File information
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    download_url = models.URLField(blank=True, null=True)
    
    # Export parameters
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    
    # Processing information
    celery_task_id = models.CharField(max_length=200, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    processing_completed_at = models.DateTimeField(null=True, blank=True)
    
    # Standard fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_report_exports')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_report_exports', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'report_export'
        verbose_name = 'Report Export'
        verbose_name_plural = 'Report Exports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_export_type_display()} ({self.export_format}) - {self.status}"


class AnalyticsCache(models.Model):
    """
    Model for caching analytics data for performance.
    """
    CACHE_TYPE_CHOICES = [
        ('revenue_metrics', 'Revenue Metrics'),
        ('user_stats', 'User Statistics'),
        ('design_performance', 'Design Performance'),
        ('growth_data', 'Growth Data'),
        ('top_performers', 'Top Performers'),
    ]
    
    cache_key = models.CharField(max_length=200, unique=True)
    cache_type = models.CharField(max_length=50, choices=CACHE_TYPE_CHOICES)
    cached_data = models.JSONField()
    
    # Cache management
    expires_at = models.DateTimeField()
    is_valid = models.BooleanField(default=True)
    
    # Standard fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_analytics_caches')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_analytics_caches', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'analytics_cache'
        verbose_name = 'Analytics Cache'
        verbose_name_plural = 'Analytics Caches'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.cache_key} ({self.cache_type}) - Expires: {self.expires_at}"
    
    def is_expired(self):
        """Check if cache is expired."""
        from django.utils import timezone
        return timezone.now() > self.expires_at
