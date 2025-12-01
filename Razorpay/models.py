from django.db import models
from django.contrib.auth.models import User
from common.relations import attach_relation, get_related_ids, get_related, detach_relation


class RazorpayPayment(models.Model):
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('authorized', 'Authorized'),
        ('captured', 'Captured'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
    ]
    
    order = models.ForeignKey('Orders.Order', on_delete=models.CASCADE, related_name='razorpay_payments', null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    method = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    notes = models.JSONField(default=dict, blank=True)
    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True, null=True)
    error_description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_razorpay_payments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_razorpay_payments', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'razorpay_payment'
        verbose_name = 'Razorpay Payment'
        verbose_name_plural = 'Razorpay Payments'
    
    def __str__(self):
        payment_id = self.razorpay_payment_id or 'Pending'
        return f"Razorpay Payment {payment_id} - {self.status}"


class RazorpayWebhookEvent(models.Model):
    EVENT_TYPES = [
        ('payment.authorized', 'Payment Authorized'),
        ('payment.captured', 'Payment Captured'),
        ('payment.failed', 'Payment Failed'),
        ('order.paid', 'Order Paid'),
        ('refund.created', 'Refund Created'),
        ('refund.processed', 'Refund Processed'),
    ]
    
    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    payment = models.ForeignKey(RazorpayPayment, on_delete=models.CASCADE, related_name='webhook_events', null=True, blank=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'razorpay_webhook_event'
        verbose_name = 'Razorpay Webhook Event'
        verbose_name_plural = 'Razorpay Webhook Events'
    
    def __str__(self):
        return f"Webhook Event {self.event_id} - {self.event_type}"