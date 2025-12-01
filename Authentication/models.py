from django.db import models
from django.contrib.auth.models import User
from common.relations import attach_relation, get_related_ids, get_related, detach_relation


class Email(models.Model):
    """
    Model to store email addresses with verification and primary status.
    
    This model manages user email addresses, tracking verification status
    and identifying primary email addresses for users.
    """
    email = models.EmailField(unique=True)
    is_verified = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_emails')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_emails', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'email'
        verbose_name = 'Email'
        verbose_name_plural = 'Emails'
    
    def __str__(self):
        return f"Email {self.pk} - {self.email}"


class MobileNumber(models.Model):
    """
    Model to store mobile numbers with verification and primary status.
    
    This model manages user mobile numbers, tracking verification status
    and identifying primary mobile numbers for users.
    """
    mobile_number = models.CharField(max_length=15, unique=True)
    is_verified = models.BooleanField(default=False)
    is_primary = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_mobile_numbers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_mobile_numbers', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'mobile_number'
        verbose_name = 'Mobile Number'
        verbose_name_plural = 'Mobile Numbers'
    
    def __str__(self):
        return f"Mobile {self.pk} - {self.mobile_number}"


class OTP(models.Model):
    """
    Model to store One-Time Passwords for authentication and verification.
    
    This model manages OTPs for various purposes like registration, password reset,
    and other verification processes. OTPs can be sent via email or mobile.
    """
    OTP_TYPE_CHOICES = [
        ('E', 'Email'),
        ('M', 'Mobile'),
    ]
    
    OTP_FOR_CHOICES = [
        ('email_verification', 'Email Verification'),
        ('password_reset', 'Password Reset'),
        ('mobile_verification', 'Mobile Verification'),
    ]
    
    otp = models.CharField(max_length=10)
    otp_type = models.CharField(max_length=1, choices=OTP_TYPE_CHOICES)
    otp_for = models.CharField(max_length=30, choices=OTP_FOR_CHOICES)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_otps')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_otps', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'otp'
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"OTP {self.pk} - {self.otp_type}"
    
    def is_expired(self):
        """Check if OTP has expired"""
        from django.utils import timezone
        return timezone.now() > self.expires_at
