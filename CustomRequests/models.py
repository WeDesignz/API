from django.db import models
from django.contrib.auth.models import User
from common.relations import attach_relation, get_related_ids, get_related, detach_relation
from MediaFiles.models import Media


class CustomOrderRequest(models.Model):
    # Workflow status choices (for order processing workflow)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('delayed', 'Delayed'),
    ]
    
    # Payment status choices (for payment processing)
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    CANCELLATION_TYPE_CHOICES = [
        ('customer', 'Customer Requested'),
        ('admin', 'Admin Cancelled'),
        ('system', 'System Error'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', help_text="Payment status: pending (payment not yet processed), success (payment successful), failed (payment failed)")
    used_free_custom_order_allowance = models.BooleanField(
        default=False,
        help_text="True if this custom order used the user's free custom order allowance (no payment)."
    )
    budget = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # SLA and Delivery Tracking
    sla_deadline = models.DateTimeField(help_text="Custom order delivery deadline from creation")
    started_at = models.DateTimeField(null=True, blank=True, help_text="When work started on the order")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When order was completed")
    delivered_at = models.DateTimeField(null=True, blank=True, help_text="When final deliverable was uploaded")
    
    # Admin Assignment
    assigned_to_id = models.IntegerField(null=True, blank=True, help_text="Admin user assigned to this order")
    assigned_at = models.DateTimeField(null=True, blank=True, help_text="When order was assigned")
    
    # Cancellation and Refund
    cancellation_reason = models.TextField(blank=True, null=True, help_text="Reason for cancellation")
    cancellation_type = models.CharField(max_length=20, choices=CANCELLATION_TYPE_CHOICES, blank=True, null=True)
    
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Refund amount (0-100% of budget)")
    refund_reason = models.TextField(blank=True, null=True, help_text="Reason for refund amount")
    
    # Delivery Files
    delivery_files_uploaded = models.BooleanField(default=False, help_text="Whether final deliverable files have been uploaded")
    delivery_message = models.TextField(blank=True, null=True, help_text="Message sent with delivery")
    
    # Notification Tracking
    admin_notified = models.BooleanField(default=False, help_text="Whether admins have been notified")
    customer_notified = models.BooleanField(default=False, help_text="Whether customer has been notified")

    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_custom_order_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_custom_order_requests', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'custom_order_request'
        verbose_name = 'Custom Order Request'
        verbose_name_plural = 'Custom Order Requests'
    
    def __str__(self):
        return f"Custom Order {self.pk} - {self.title} ({self.status})"
    
    def get_media(self):
        return get_related(self, 'CustomRequest:Media', Media)
    
    def attach_media(self, media_obj, meta=None, created_by=None):
        return attach_relation('CustomRequest:Media', self, media_obj, meta=meta, created_by=created_by)
    
    def detach_media(self, media_obj):
        return detach_relation('CustomRequest:Media', self, media_obj)
    
    def save(self, *args, **kwargs):
        # Set SLA deadline from settings if not set
        if not self.pk and not self.sla_deadline:
            from django.utils import timezone
            from common.business_config import BusinessConfig
            from Plans.models import Subscription
            
            # Check if user has an active subscription with a plan
            hours = BusinessConfig.get_custom_order_time_slot_hours()  # Default from .env
            
            try:
                subscription = Subscription.objects.filter(
                    created_by=self.created_by,
                    status='active'
                ).select_related('plan').first()
                
                if subscription and subscription.plan and hasattr(subscription.plan, 'custom_design_hour'):
                    # Use plan's custom_design_hour if available
                    plan_hours = subscription.plan.custom_design_hour
                    if plan_hours and plan_hours > 0:
                        hours = plan_hours
            except Exception:
                # If any error occurs, fall back to default from .env
                pass
            
            self.sla_deadline = timezone.now() + timezone.timedelta(hours=hours)
        super().save(*args, **kwargs)
    
    @property
    def assigned_to(self):
        """Get the assigned admin user via relations."""
        if self.assigned_to_id:
            from common.relations import get_related
            from django.contrib.auth.models import User
            users = get_related(self, 'CustomOrderRequest:User', User)
            return users.first() if users.exists() else None
        return None
    
    def set_assigned_to(self, admin_user):
        """Set the assigned admin user via relations."""
        from common.relations import attach_relation
        if admin_user:
            self.assigned_to_id = admin_user.pk
            attach_relation('CustomOrderRequest:User', self, admin_user)
            from django.utils import timezone
            self.assigned_at = timezone.now()
        else:
            self.assigned_to_id = None
            self.assigned_at = None
    
    def start_order(self, admin_user):
        """Start working on the order."""
        from django.utils import timezone
        self.status = 'in_progress'
        self.started_at = timezone.now()
        self.set_assigned_to(admin_user)
        self.save()
    
    def complete_order(self, admin_user):
        """Mark order as completed."""
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.updated_by = admin_user
        self.save()
    
    def deliver_order(self, admin_user, delivery_message=""):
        """Mark order as delivered with files."""
        from django.utils import timezone
        if not self.delivery_files_uploaded:
            raise ValueError("Cannot deliver order without uploaded files")
        
        self.delivered_at = timezone.now()
        self.delivery_message = delivery_message
        self.customer_notified = True
        self.updated_by = admin_user
        self.save()
    
    def cancel_order(self, admin_user, reason, cancellation_type='admin', refund_amount=None, refund_reason=""):
        """Cancel the order with reason and refund details."""
        from django.utils import timezone
        self.status = 'cancelled'
        self.cancellation_reason = reason
        self.cancellation_type = cancellation_type
        self.refund_amount = refund_amount
        self.refund_reason = refund_reason
        self.updated_by = admin_user
        self.save()
    
    def mark_delayed(self, admin_user):
        """Mark order as delayed."""
        from django.utils import timezone
        self.status = 'delayed'
        self.updated_by = admin_user
        self.save()
    
    def check_sla_breach(self):
        """Check if SLA has been breached."""
        from django.utils import timezone
        if self.status in ['completed', 'cancelled']:
            return False
        
        if timezone.now() > self.sla_deadline:
            if self.status != 'delayed':
                self.mark_delayed(None)
            return True
        return False
    
    def get_time_remaining(self):
        """Get time remaining until SLA deadline."""
        from django.utils import timezone
        if self.status in ['completed', 'cancelled']:
            return None
        
        remaining = self.sla_deadline - timezone.now()
        return max(remaining, timezone.timedelta(seconds=0))
    
    def get_sla_status(self):
        """Get SLA status information."""
        from django.utils import timezone
        if self.status in ['completed', 'cancelled']:
            return 'completed'
        
        if self.status == 'delayed':
            return 'breached'
        
        time_remaining = self.get_time_remaining()
        if time_remaining and time_remaining.total_seconds() < 300:  # 5 minutes
            return 'critical'
        elif time_remaining and time_remaining.total_seconds() < 900:  # 15 minutes
            return 'warning'
        
        return 'normal'
    
    def can_be_cancelled(self):
        """Check if order can be cancelled."""
        return self.status in ['pending', 'in_progress']
    
    def can_be_delivered(self):
        """Check if order can be delivered."""
        return self.status == 'completed' and self.delivery_files_uploaded
    
    def get_refund_percentage(self):
        """Get refund percentage based on cancellation type."""
        if self.cancellation_type == 'customer':
            return 50  # 50% refund for customer cancellation
        elif self.cancellation_type == 'admin':
            return 100  # Up to 100% for admin cancellation
        elif self.cancellation_type == 'system':
            return 100  # Full refund for system errors
        return 0