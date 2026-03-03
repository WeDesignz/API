from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class PinterestIntegration(models.Model):
    """
    Model to store Pinterest OAuth tokens and configuration.
    Only one instance should exist (singleton pattern).
    """
    access_token = models.TextField(help_text="Pinterest OAuth access token")
    refresh_token = models.TextField(null=True, blank=True, help_text="Pinterest OAuth refresh token")
    token_expires_at = models.DateTimeField(null=True, blank=True, help_text="When the access token expires")
    board_id = models.CharField(max_length=255, help_text="Pinterest board ID where pins will be posted")
    board_name = models.CharField(max_length=255, null=True, blank=True, help_text="Pinterest board name (for display)")
    is_enabled = models.BooleanField(default=True, help_text="Enable/disable Pinterest posting")
    
    # Status tracking
    last_successful_post = models.DateTimeField(null=True, blank=True, help_text="Last successful Pinterest post")
    last_error = models.TextField(null=True, blank=True, help_text="Last error message if any")
    last_error_at = models.DateTimeField(null=True, blank=True, help_text="When the last error occurred")

    # Rate limit (from Pinterest API response headers)
    rate_limit_remaining = models.IntegerField(null=True, blank=True, help_text="Remaining API requests in current window")
    rate_limit_limit = models.IntegerField(null=True, blank=True, help_text="Max API requests per window")
    rate_limit_reset_at = models.DateTimeField(null=True, blank=True, help_text="When the rate limit window resets")
    rate_limit_retry_after_at = models.DateTimeField(null=True, blank=True, help_text="When safe to retry after 429")

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='pinterest_integrations')
    
    class Meta:
        db_table = 'pinterest_integration'
        verbose_name = 'Pinterest Integration'
        verbose_name_plural = 'Pinterest Integrations'
    
    def __str__(self):
        status = "✅ Enabled" if self.is_enabled else "❌ Disabled"
        return f"Pinterest Integration - {status}"
    
    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance."""
        instance, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'access_token': '',
                'board_id': '',
                'is_enabled': False
            }
        )
        return instance
    
    def is_token_valid(self):
        """Check if the access token is still valid."""
        if not self.access_token:
            return False
        if self.token_expires_at and timezone.now() > self.token_expires_at:
            return False
        return True
    
    def update_error(self, error_message):
        """Update error tracking."""
        self.last_error = error_message
        self.last_error_at = timezone.now()
        self.save(update_fields=['last_error', 'last_error_at'])
    
    def update_success(self):
        """Update success tracking."""
        self.last_successful_post = timezone.now()
        self.last_error = None
        self.last_error_at = None
        self.save(update_fields=['last_successful_post', 'last_error', 'last_error_at'])

    def update_rate_limit_from_response(self, response):
        """
        Update rate limit fields from Pinterest API response headers.
        Call after every Pinterest API request (success or 429).
        Supports x-userendpoint-ratelimit-* and X-RateLimit-* style headers.
        """
        if response is None:
            return
        headers = getattr(response, 'headers', {})
        if not headers:
            return
        # Pinterest v5/Ads: x-userendpoint-ratelimit-*; older: X-RateLimit-*
        remaining = headers.get('x-userendpoint-ratelimit-remaining') or headers.get('X-RateLimit-Remaining')
        limit = headers.get('x-userendpoint-ratelimit-limit') or headers.get('X-RateLimit-Limit')
        reset_seconds = headers.get('x-userendpoint-ratelimit-reset-seconds') or headers.get('X-RateLimit-Reset')
        retry_after = headers.get('Retry-After')
        update_fields = []
        if remaining is not None:
            try:
                self.rate_limit_remaining = int(remaining)
                update_fields.append('rate_limit_remaining')
            except (TypeError, ValueError):
                pass
        if limit is not None:
            try:
                self.rate_limit_limit = int(limit)
                update_fields.append('rate_limit_limit')
            except (TypeError, ValueError):
                pass
        if reset_seconds is not None:
            try:
                from datetime import timedelta
                self.rate_limit_reset_at = timezone.now() + timedelta(seconds=int(reset_seconds))
                update_fields.append('rate_limit_reset_at')
            except (TypeError, ValueError):
                pass
        if retry_after is not None and response.status_code == 429:
            try:
                from datetime import timedelta
                self.rate_limit_retry_after_at = timezone.now() + timedelta(seconds=int(retry_after))
                update_fields.append('rate_limit_retry_after_at')
            except (TypeError, ValueError):
                pass
        if update_fields:
            self.save(update_fields=update_fields)


class PinterestPost(models.Model):
    """
    Model to track Pinterest post attempts for each approved design.
    This allows retrying failed posts when Pinterest is reconnected.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
    ]
    
    product = models.ForeignKey('Catalog.Product', on_delete=models.CASCADE, related_name='pinterest_posts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Pinterest pin information
    pin_id = models.CharField(max_length=255, null=True, blank=True, help_text="Pinterest pin ID if successfully posted (legacy - use pins_data)")
    pin_url = models.URLField(null=True, blank=True, help_text="URL to the Pinterest pin (legacy - use pins_data)")
    pins_data = models.JSONField(default=dict, blank=True, help_text="Dictionary of pin data: {'mockup': {'id': '...', 'url': '...'}, 'design': {'id': '...', 'url': '...'}}")
    
    # Error tracking
    error_message = models.TextField(null=True, blank=True, help_text="Error message if posting failed")
    retry_count = models.IntegerField(default=0, help_text="Number of retry attempts")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True, help_text="When the pin was successfully posted")
    last_retry_at = models.DateTimeField(null=True, blank=True, help_text="Last retry attempt timestamp")
    
    class Meta:
        db_table = 'pinterest_post'
        verbose_name = 'Pinterest Post'
        verbose_name_plural = 'Pinterest Posts'
        ordering = ['-created_at']
        # Ensure one Pinterest post record per product (can retry but not duplicate)
        unique_together = [['product']]
    
    def __str__(self):
        return f"Pinterest Post - {self.product.title} ({self.get_status_display()})"
    
    def mark_success(self, pin_id=None, pin_url=None, pins_data=None):
        """Mark the post as successful."""
        self.status = 'success'
        self.posted_at = timezone.now()
        
        if pins_data:
            # New format: store multiple pins
            self.pins_data = pins_data
            # For backward compatibility, set first pin as primary
            if pins_data and isinstance(pins_data, dict):
                first_pin = next(iter(pins_data.values()), {})
                if isinstance(first_pin, dict):
                    self.pin_id = first_pin.get('id')
                    self.pin_url = first_pin.get('url')
        elif pin_id:
            # Legacy format: single pin
            self.pin_id = pin_id
            if pin_url:
                self.pin_url = pin_url
        
        self.save(update_fields=['status', 'posted_at', 'pin_id', 'pin_url', 'pins_data'])
    
    def mark_failed(self, error_message):
        """Mark the post as failed."""
        self.status = 'failed'
        
        # Truncate error message if too long (database field limits)
        # TextField can hold ~65KB, but let's keep it reasonable for readability
        max_length = 5000
        if len(error_message) > max_length:
            error_message = error_message[:max_length] + f"... (truncated, full length: {len(error_message)})"
        
        self.error_message = error_message
        self.last_retry_at = timezone.now()
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'last_retry_at', 'retry_count'])
    
    def mark_retrying(self):
        """Mark the post as being retried."""
        self.status = 'retrying'
        self.last_retry_at = timezone.now()
        self.save(update_fields=['status', 'last_retry_at'])
    
    def get_error_summary(self):
        """Get a formatted error summary for display."""
        if not self.error_message:
            return "No error details available"
        
        # Extract key information from error message
        lines = self.error_message.split(' | ')
        summary_parts = []
        
        for line in lines:
            if any(keyword in line.lower() for keyword in ['failed', 'error', '401', '403', '404', '429', '500', 'timeout', 'connection']):
                summary_parts.append(line)
        
        if summary_parts:
            return " | ".join(summary_parts[:3])  # Show first 3 relevant lines
        else:
            return self.error_message[:200] + ("..." if len(self.error_message) > 200 else "")


class InstagramIntegration(models.Model):
    """
    Model to store Instagram OAuth tokens and configuration.
    Only one instance should exist (singleton pattern).
    """
    access_token = models.TextField(help_text="Instagram OAuth access token")
    refresh_token = models.TextField(null=True, blank=True, help_text="Instagram OAuth refresh token")
    token_expires_at = models.DateTimeField(null=True, blank=True, help_text="When the access token expires")
    user_id = models.CharField(max_length=255, null=True, blank=True, help_text="Instagram user ID")
    username = models.CharField(max_length=255, null=True, blank=True, help_text="Instagram username")
    is_enabled = models.BooleanField(default=True, help_text="Enable/disable Instagram posting")
    
    # Status tracking
    last_successful_post = models.DateTimeField(null=True, blank=True, help_text="Last successful Instagram post")
    last_error = models.TextField(null=True, blank=True, help_text="Last error message if any")
    last_error_at = models.DateTimeField(null=True, blank=True, help_text="When the last error occurred")

    # Rate limit (from Instagram/Facebook Graph API response headers)
    rate_limit_remaining = models.IntegerField(null=True, blank=True, help_text="Remaining API requests in current window")
    rate_limit_limit = models.IntegerField(null=True, blank=True, help_text="Max API requests per window")
    rate_limit_reset_at = models.DateTimeField(null=True, blank=True, help_text="When the rate limit window resets")
    rate_limit_retry_after_at = models.DateTimeField(null=True, blank=True, help_text="When safe to retry after 429")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='instagram_integrations')
    
    class Meta:
        db_table = 'instagram_integration'
        verbose_name = 'Instagram Integration'
        verbose_name_plural = 'Instagram Integrations'
    
    def __str__(self):
        status = "✅ Enabled" if self.is_enabled else "❌ Disabled"
        return f"Instagram Integration - {status}"
    
    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance."""
        instance, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'access_token': '',
                'is_enabled': False
            }
        )
        return instance
    
    def is_token_valid(self):
        """Check if the access token is still valid."""
        if not self.access_token:
            return False
        if self.token_expires_at and timezone.now() > self.token_expires_at:
            return False
        return True
    
    def update_error(self, error_message):
        """Update error tracking."""
        self.last_error = error_message
        self.last_error_at = timezone.now()
        self.save(update_fields=['last_error', 'last_error_at'])
    
    def update_success(self):
        """Update success tracking."""
        self.last_successful_post = timezone.now()
        self.last_error = None
        self.last_error_at = None
        self.save(update_fields=['last_successful_post', 'last_error', 'last_error_at'])

    def update_rate_limit_from_response(self, response):
        """
        Update rate limit fields from Instagram/Facebook Graph API response headers.
        Call after every Graph API request (success or 429).
        Supports X-Ratelimit-*, x-app-usage, and Retry-After.
        """
        if response is None:
            return
        headers = getattr(response, 'headers', {})
        if not headers:
            return
        # Graph API: X-Ratelimit-Limit, X-Ratelimit-Remaining; some endpoints use x-app-usage
        remaining = headers.get('X-Ratelimit-Remaining') or headers.get('x-ratelimit-remaining')
        limit = headers.get('X-Ratelimit-Limit') or headers.get('x-ratelimit-limit')
        reset_seconds = headers.get('X-Ratelimit-Reset') or headers.get('x-ratelimit-reset')
        retry_after = headers.get('Retry-After') or headers.get('retry-after')
        update_fields = []
        if remaining is not None:
            try:
                self.rate_limit_remaining = int(remaining)
                update_fields.append('rate_limit_remaining')
            except (TypeError, ValueError):
                pass
        if limit is not None:
            try:
                self.rate_limit_limit = int(limit)
                update_fields.append('rate_limit_limit')
            except (TypeError, ValueError):
                pass
        if reset_seconds is not None:
            try:
                from datetime import timedelta
                self.rate_limit_reset_at = timezone.now() + timedelta(seconds=int(reset_seconds))
                update_fields.append('rate_limit_reset_at')
            except (TypeError, ValueError):
                pass
        if retry_after is not None and getattr(response, 'status_code', None) == 429:
            try:
                from datetime import timedelta
                self.rate_limit_retry_after_at = timezone.now() + timedelta(seconds=int(retry_after))
                update_fields.append('rate_limit_retry_after_at')
            except (TypeError, ValueError):
                pass
        if update_fields:
            self.save(update_fields=update_fields)


class InstagramPost(models.Model):
    """
    Model to track Instagram post attempts for each design.
    Supports both regular posts and stories.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
    ]
    
    POST_TYPE_CHOICES = [
        ('post', 'Post'),
        ('story', 'Story'),
    ]
    
    MEDIA_TYPE_CHOICES = [
        ('mockup', 'Mockup'),
        ('jpg', 'JPG'),
        ('png', 'PNG'),
    ]
    
    product = models.ForeignKey('Catalog.Product', on_delete=models.CASCADE, related_name='instagram_posts')
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES, help_text="Type of media to post")
    caption = models.TextField(help_text="Caption for the Instagram post")
    post_type = models.CharField(max_length=10, choices=POST_TYPE_CHOICES, default='post', help_text="Post or Story")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Instagram post information
    media_id = models.CharField(max_length=255, null=True, blank=True, help_text="Instagram media ID if successfully posted")
    post_id = models.CharField(max_length=255, null=True, blank=True, help_text="Instagram post ID if successfully posted")
    post_url = models.URLField(null=True, blank=True, help_text="URL to the Instagram post")
    
    # Error tracking
    error_message = models.TextField(null=True, blank=True, help_text="Error message if posting failed")
    retry_count = models.IntegerField(default=0, help_text="Number of retry attempts")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(null=True, blank=True, help_text="When the post was successfully posted")
    last_retry_at = models.DateTimeField(null=True, blank=True, help_text="Last retry attempt timestamp")
    
    class Meta:
        db_table = 'instagram_post'
        verbose_name = 'Instagram Post'
        verbose_name_plural = 'Instagram Posts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Instagram {self.get_post_type_display()} - {self.product.title} ({self.get_status_display()})"
    
    def mark_success(self, media_id=None, post_id=None, post_url=None):
        """Mark the post as successful."""
        self.status = 'success'
        self.posted_at = timezone.now()
        self.error_message = None  # Clear any previous error
        if media_id:
            self.media_id = media_id
        if post_id:
            self.post_id = post_id
        if post_url:
            self.post_url = post_url
        self.save(update_fields=['status', 'posted_at', 'error_message', 'media_id', 'post_id', 'post_url'])
    
    def mark_failed(self, error_message):
        """Mark the post as failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.last_retry_at = timezone.now()
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'last_retry_at', 'retry_count'])
    
    def mark_retrying(self):
        """Mark the post as being retried."""
        self.status = 'retrying'
        self.last_retry_at = timezone.now()
        self.save(update_fields=['status', 'last_retry_at'])
    
    def mark_processing(self):
        """Mark the post as being processed."""
        self.status = 'processing'
        self.save(update_fields=['status'])

