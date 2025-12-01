from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta, date, datetime
from common.relations import attach_relation, get_related_ids, get_related, detach_relation


class Plan(models.Model):
    PLAN_NAME_CHOICES = [
        ('basic', 'Basic'),
        ('prime', 'Prime'),
        ('premium', 'Premium'),
    ]
    
    DURATION_CHOICES = [
        ('monthly', 'Monthly'),
        ('annually', 'Annually'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    plan_name = models.CharField(max_length=20, choices=PLAN_NAME_CHOICES)
    description = models.JSONField(default=dict)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    plan_duration = models.CharField(max_length=20, choices=DURATION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # New fields for plan features
    discount = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Discount percentage for this plan (e.g., 60.00 for 60%)"
    )
    custom_design_hour = models.IntegerField(
        default=2,
        help_text="Hours for custom design delivery (e.g., 2 for Basic, 1 for Premium)"
    )
    mock_pdf_count = models.IntegerField(
        default=0,
        help_text="Number of mock PDFs allowed in this plan"
    )
    no_of_free_downloads = models.IntegerField(
        default=0,
        help_text="Number of free downloads allowed in this plan"
    )
    
    is_most_popular = models.BooleanField(
        default=False,
        help_text="Mark this plan as 'Most Popular' for its duration (monthly/annual). Only one plan per duration should be marked."
    )
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_plans')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_plans', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'plan'
        verbose_name = 'Plan'
        verbose_name_plural = 'Plans'
        unique_together = ['plan_name', 'plan_duration']
    
    def __str__(self):
        return f"{self.get_plan_name_display()} - {self.get_plan_duration_display()}"


class Subscription(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('failed', 'Failed'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    auto_renew = models.BooleanField(default=True)
    
    # Track free downloads usage
    free_downloads_used = models.IntegerField(
        default=0,
        help_text="Number of free downloads used from this subscription"
    )
    
    # Track mock PDF downloads usage
    mock_pdf_downloads_used = models.IntegerField(
        default=0,
        help_text="Number of mock PDF downloads used from this subscription"
    )
    
    # Track if settlement has been processed for this subscription period
    settlement_processed = models.BooleanField(
        default=False,
        help_text="Whether earnings have been distributed to designers for this subscription period"
    )
    
    # Track last settled month for annual subscriptions (for monthly settlements)
    last_settled_month = models.DateField(
        null=True,
        blank=True,
        help_text="Last month for which settlement was processed (for annual subscriptions with monthly settlements)"
    )
    
    # Track current period downloads for annual subscriptions (monthly limit enforcement)
    current_period_downloads_used = models.IntegerField(
        default=0,
        help_text="Number of downloads used in current 30-day settlement period (for annual plans only)"
    )
    
    current_period_start = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of current 30-day settlement period (for annual plans only)"
    )
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_subscriptions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_subscriptions', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'subscription'
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
    
    def __str__(self):
        return f"Subscription {self.pk} - {self.plan.plan_name} ({self.status})"
    
    def get_current_settlement_period(self):
        """
        Calculate current settlement period for annual subscriptions.
        Returns (period_start, period_end) tuple.
        For monthly subscriptions, returns None.
        """
        if self.plan.plan_duration != 'annually':
            return None, None
        
        if self.last_settled_month:
            # Next period starts from day after last settlement
            period_start = self.last_settled_month + timedelta(days=1)
        else:
            # First period starts from subscription creation
            period_start = self.created_at.date()
        
        period_end = period_start + timedelta(days=30)
        return period_start, period_end
    
    def get_current_period_downloads_used(self):
        """
        Get number of downloads used in current settlement period.
        For annual plans, counts downloads in current 30-day period.
        For monthly plans, returns total downloads used.
        """
        if self.plan.plan_duration != 'annually':
            # For monthly plans, return total downloads used
            return self.free_downloads_used
        
        # For annual plans, calculate downloads in current period
        period_start, period_end = self.get_current_settlement_period()
        if not period_start:
            return 0
        
        # Count downloads from orders in current period
        from Orders.models import Order
        
        period_start_dt = timezone.make_aware(datetime.combine(period_start, datetime.min.time()))
        period_end_dt = timezone.make_aware(datetime.combine(period_end, datetime.max.time()))
        
        orders_in_period = Order.objects.filter(
            subscription=self,
            order_type='subscription',
            status='success',
            created_at__gte=period_start_dt,
            created_at__lt=period_end_dt
        )
        
        total_downloads = 0
        for order in orders_in_period:
            if order.product_ids:
                product_ids = [pid.strip() for pid in order.product_ids.split(',') if pid.strip()]
                total_downloads += len(product_ids)
        
        return total_downloads
    
    def get_monthly_download_limit(self):
        """Get monthly download limit for annual subscriptions."""
        if self.plan.plan_duration != 'annually':
            return None  # Monthly plans don't have monthly limits
        
        if not self.plan or not hasattr(self.plan, 'no_of_free_downloads'):
            return 0
        
        # Monthly allocation = total annual downloads / 12
        return self.plan.no_of_free_downloads // 12
    
    def get_remaining_free_downloads(self):
        """Get remaining free downloads for this subscription."""
        if not self.plan or not hasattr(self.plan, 'no_of_free_downloads'):
            return 0
        return max(0, self.plan.no_of_free_downloads - self.free_downloads_used)
    
    def get_remaining_monthly_downloads(self):
        """
        Get remaining downloads in current period for annual subscriptions.
        Returns None for monthly subscriptions.
        """
        if self.plan.plan_duration != 'annually':
            return None
        
        monthly_limit = self.get_monthly_download_limit()
        if monthly_limit is None:
            return None
        
        current_period_used = self.get_current_period_downloads_used()
        return max(0, monthly_limit - current_period_used)
    
    def can_use_free_downloads(self, count=1):
        """
        Check if subscription can use specified number of free downloads.
        For annual plans, also checks monthly limit.
        """
        # Check total annual limit
        if not self.get_remaining_free_downloads() >= count:
            return False
        
        # For annual plans, also check monthly limit
        if self.plan.plan_duration == 'annually':
            remaining_monthly = self.get_remaining_monthly_downloads()
            if remaining_monthly is not None and remaining_monthly < count:
                return False
        
        return True
    
    def use_free_downloads(self, count=1):
        """
        Use free downloads from subscription.
        For annual plans, also enforces monthly limit.
        """
        # Check total limit
        if not self.get_remaining_free_downloads() >= count:
            raise ValueError(
                f"Not enough free downloads. Available: {self.get_remaining_free_downloads()}, Requested: {count}"
            )
        
        # For annual plans, check monthly limit
        if self.plan.plan_duration == 'annually':
            remaining_monthly = self.get_remaining_monthly_downloads()
            if remaining_monthly is not None and remaining_monthly < count:
                period_start, period_end = self.get_current_settlement_period()
                raise ValueError(
                    f"Monthly download limit reached. You have used {self.get_current_period_downloads_used()} downloads "
                    f"this month (limit: {self.get_monthly_download_limit()}). "
                    f"Next period starts on {period_end.strftime('%B %d, %Y')}."
                )
        
        # Update total downloads used
        self.free_downloads_used += count
        
        # For annual plans, update current period counter
        if self.plan.plan_duration == 'annually':
            # Initialize current_period_start if not set
            if not self.current_period_start:
                period_start, _ = self.get_current_settlement_period()
                self.current_period_start = period_start
            
            self.current_period_downloads_used += count
        
        self.save()
    
    def get_remaining_mock_pdf_downloads(self):
        """Get remaining mock PDF downloads for this subscription."""
        if not self.plan or not hasattr(self.plan, 'mock_pdf_count'):
            return 0
        return max(0, self.plan.mock_pdf_count - self.mock_pdf_downloads_used)
    
    def can_use_mock_pdf_download(self):
        """Check if subscription can use a mock PDF download."""
        return self.get_remaining_mock_pdf_downloads() > 0
    
    def use_mock_pdf_download(self):
        """Use a mock PDF download from subscription."""
        if not self.can_use_mock_pdf_download():
            raise ValueError(f"No mock PDF downloads remaining. Available: {self.get_remaining_mock_pdf_downloads()}")
        self.mock_pdf_downloads_used += 1
        self.save()