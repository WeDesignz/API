from django.db import models
from django.contrib.auth.models import User
from common.relations import attach_relation, get_related_ids, get_related, detach_relation


class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = [
        ('flat', 'Flat'),
        ('percentage', 'Percentage'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('expired', 'Expired'),
        ('scheduled', 'Scheduled'),
    ]
    
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    applied_to_base = models.BooleanField(default=False)
    applied_to_prime = models.BooleanField(default=False)
    applied_to_premium = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    coupon_discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    max_usage = models.IntegerField(default=0)
    max_usage_per_user = models.IntegerField(default=1)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    start_date_time = models.DateTimeField()
    end_date_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_coupons')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_coupons', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'coupon'
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def get_usages(self):
        return get_related(self, 'Coupon:Usage', CouponUsage)
    
    def attach_usage(self, usage_obj, meta=None, created_by=None):
        return attach_relation('Coupon:Usage', self, usage_obj, meta=meta, created_by=created_by)
    
    def detach_usage(self, usage_obj):
        return detach_relation('Coupon:Usage', self, usage_obj)


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='usages')
    order = models.ForeignKey('Orders.Order', on_delete=models.CASCADE, related_name='coupon_usages')
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2)
    order_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_coupon_usages')
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'coupon_usage'
        verbose_name = 'Coupon Usage'
        verbose_name_plural = 'Coupon Usages'
        unique_together = ['coupon', 'order']
    
    def __str__(self):
        return f"Coupon Usage - {self.coupon.code} on Order {self.order.pk}"
