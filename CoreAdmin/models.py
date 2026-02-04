from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone
from cryptography.fernet import Fernet
from django.conf import settings
import base64
import pyotp
import qrcode
import io
from django.core.files.base import ContentFile


class AdminPermissionGroup(models.Model):
    """
    Permission groups for admin users (moderators).
    Allows grouping permissions together for easier management.
    """
    name = models.CharField(max_length=100, unique=True, help_text='Name of the permission group')
    description = models.TextField(blank=True, help_text='Description of what this group is for')
    permissions = models.JSONField(
        default=list,
        blank=True,
        help_text='List of permission strings in this group'
    )
    is_active = models.BooleanField(default=True, help_text='Whether this group is active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'admin_permission_group'
        verbose_name = 'Admin Permission Group'
        verbose_name_plural = 'Admin Permission Groups'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_permission_count(self):
        """Get the number of permissions in this group"""
        return len(self.permissions or [])


class AdminUserProfile(models.Model):
    """
    Extended profile for admin users with 2FA settings.
    """
    ADMIN_GROUP_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('moderator', 'Moderator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    admin_group = models.CharField(max_length=20, choices=ADMIN_GROUP_CHOICES, default='moderator')
    permission_group = models.ForeignKey(
        AdminPermissionGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        help_text='Permission group this user belongs to (moderators only)'
    )
    is_2fa_enabled = models.BooleanField(default=False)
    two_factor_secret = models.TextField(blank=True)  # Encrypted secret key
    backup_codes = models.JSONField(default=list, blank=True)  # Backup codes for 2FA
    last_2fa_verification = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    permissions = models.JSONField(
        default=list,
        blank=True,
        help_text='Additional individual permissions (combined with group permissions)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'admin_user_profile'
        verbose_name = 'Admin User Profile'
        verbose_name_plural = 'Admin User Profiles'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_admin_group_display()}"
    
    def get_all_permissions(self) -> list:
        """Get all permissions for this user (group + individual)"""
        if self.admin_group == 'superadmin':
            return []  # Super Admin has all permissions, return empty to indicate "all"
        
        all_perms = set()
        
        # Add group permissions
        if self.permission_group and self.permission_group.is_active:
            all_perms.update(self.permission_group.permissions or [])
        
        # Add individual permissions
        all_perms.update(self.permissions or [])
        
        return list(all_perms)
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        if self.admin_group == 'superadmin':
            return True  # Super Admin has all permissions
        
        all_perms = self.get_all_permissions()
        return permission in all_perms
    
    def has_any_permission(self, permissions: list) -> bool:
        """Check if user has any of the given permissions"""
        if self.admin_group == 'superadmin':
            return True
        user_perms = set(self.get_all_permissions())
        return bool(user_perms.intersection(set(permissions)))
    
    def has_all_permissions(self, permissions: list) -> bool:
        """Check if user has all of the given permissions"""
        if self.admin_group == 'superadmin':
            return True
        user_perms = set(self.get_all_permissions())
        return user_perms.issuperset(set(permissions))
    
    def set_two_factor_secret(self, secret):
        """Encrypt and store the 2FA secret key"""
        # Use the same key generation logic as get_two_factor_secret
        f = self._get_fernet_instance()
        
        encrypted_secret = f.encrypt(secret.encode())
        self.two_factor_secret = base64.urlsafe_b64encode(encrypted_secret).decode()
        self.save()
    
    def _get_fernet_instance(self):
        """Get a Fernet instance using consistent key generation/validation logic"""
        encryption_key = getattr(settings, 'ENCRYPTION_KEY', None)
        
        # If ENCRYPTION_KEY is not set or is the default placeholder, generate a new one
        if not encryption_key or encryption_key == 'your-32-character-secret-key-here':
            # Generate a new Fernet key
            new_key = Fernet.generate_key()
            key_str = new_key.decode()
            # Log a warning (in production, this should be set in environment)
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f'ENCRYPTION_KEY not set or invalid. Generated new key: {key_str}. '
                'Please set ENCRYPTION_KEY in your .env file for production use.'
            )
            # Update settings for this session (like the demo command does)
            import django.conf
            django.conf.settings.ENCRYPTION_KEY = key_str
            settings.ENCRYPTION_KEY = key_str
            encryption_key = key_str
        
        # Try to create Fernet instance with the key
        try:
            # Try using the key directly (Fernet.generate_key() format - 44 chars base64)
            return Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
        except (ValueError, TypeError):
            # If that fails, try to fix common issues
            try:
                # If key is too short/long, generate a new one
                if isinstance(encryption_key, str) and len(encryption_key) != 44:
                    # Generate a new key
                    new_key = Fernet.generate_key()
                    key_str = new_key.decode()
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        f'ENCRYPTION_KEY has invalid length ({len(encryption_key)}). '
                        f'Generated new key: {key_str}. '
                        'Please set ENCRYPTION_KEY in your .env file for production use.'
                    )
                    # Update settings for this session
                    import django.conf
                    django.conf.settings.ENCRYPTION_KEY = key_str
                    settings.ENCRYPTION_KEY = key_str
                    return Fernet(key_str.encode())
                else:
                    # Try decoding it (for backward compatibility)
                    key = base64.urlsafe_b64decode(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
                    return Fernet(key)
            except Exception as e:
                # Last resort: generate a new key
                new_key = Fernet.generate_key()
                key_str = new_key.decode()
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f'Failed to use ENCRYPTION_KEY: {e}. '
                    f'Generated new key: {key_str}. '
                    'Please set ENCRYPTION_KEY in your .env file for production use.'
                )
                # Update settings for this session
                import django.conf
                django.conf.settings.ENCRYPTION_KEY = key_str
                settings.ENCRYPTION_KEY = key_str
                return Fernet(key_str.encode())
    
    def get_two_factor_secret(self):
        """Decrypt and return the 2FA secret key"""
        if not self.two_factor_secret:
            return None
        
        try:
            f = self._get_fernet_instance()
            encrypted_secret = base64.urlsafe_b64decode(self.two_factor_secret.encode())
            decrypted_secret = f.decrypt(encrypted_secret)
            return decrypted_secret.decode()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error decrypting 2FA secret: {e}')
            return None
    
    def generate_qr_code(self):
        """Generate QR code for 2FA setup"""
        secret = self.get_two_factor_secret()
        if not secret:
            return None
        
        # Create TOTP URI
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=self.user.email,
            issuer_name="WeDesignz Admin"
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer.getvalue()
    
    def verify_totp(self, token):
        """Verify TOTP token"""
        secret = self.get_two_factor_secret()
        if not secret:
            return False
        
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)  # Allow 1 time step tolerance
    
    def generate_backup_codes(self, count=10):
        """Generate backup codes for 2FA"""
        import secrets
        import string
        
        codes = []
        chars = string.ascii_uppercase + string.digits
        for _ in range(count):
            # Use secrets.choice() in a loop for compatibility
            code = ''.join(secrets.choice(chars) for _ in range(8))
            codes.append(code)
        
        self.backup_codes = codes
        self.save()
        return codes


class AdminActivityLog(models.Model):
    """
    Model to track admin activities for audit purposes.
    Only superusers can view these logs.
    """
    ACTIVITY_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('2fa_setup', '2FA Setup'),
        ('2fa_verify', '2FA Verification'),
        ('password_change', 'Password Change'),
        ('profile_update', 'Profile Update'),
        ('user_management', 'User Management'),
        ('system_config', 'System Configuration'),
        ('data_export', 'Data Export'),
        ('data_import', 'Data Import'),
        ('other', 'Other'),
    ]
    
    # Using relation system instead of direct ForeignKey
    user_id = models.IntegerField()  # Will be linked via relation
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)  # Additional data
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'admin_activity_log'
        verbose_name = 'Admin Activity Log'
        verbose_name_plural = 'Admin Activity Logs'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Admin Activity Log {self.pk} - {self.get_activity_type_display()} - {self.timestamp}"
    
    @property
    def user(self):
        """Get the related user via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            # Create a temporary object with the user_id
            temp_obj = type('TempObj', (), {'pk': self.user_id})()
            users = get_related(temp_obj, 'User:AdminActivityLog', User)
            return users.first()
        except:
            return None
    
    def set_user(self, user):
        """Set the related user via relation system"""
        from common.relations import attach_relation
        attach_relation('User:AdminActivityLog', user, self)
    
    @classmethod
    def log_activity(cls, user, activity_type, description, request=None, metadata=None):
        """Helper method to log admin activities"""
        ip_address = '127.0.0.1'
        user_agent = ''
        
        if request:
            ip_address = cls.get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Create the activity log
        activity_log = cls.objects.create(
            user_id=user.pk,
            activity_type=activity_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {}
        )
        
        # Create the relation
        from common.relations import attach_relation
        attach_relation('User:AdminActivityLog', user, activity_log, created_by=user)
        
        return activity_log
    
    @staticmethod
    def get_client_ip(request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class AdminSession(models.Model):
    """
    Model to track admin sessions for security purposes.
    """
    # Using relation system instead of direct ForeignKey
    user_id = models.IntegerField()  # Will be linked via relation
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    is_active = models.BooleanField(default=True)
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'admin_session'
        verbose_name = 'Admin Session'
        verbose_name_plural = 'Admin Sessions'
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"Admin Session {self.pk} - {self.session_key[:8]}... - {self.last_activity}"
    
    @property
    def user(self):
        """Get the related user via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            # Create a temporary object with the user_id
            temp_obj = type('TempObj', (), {'pk': self.user_id})()
            users = get_related(temp_obj, 'User:AdminSession', User)
            return users.first()
        except:
            return None
    
    def set_user(self, user):
        """Set the related user via relation system"""
        from common.relations import attach_relation
        attach_relation('User:AdminSession', user, self)
    
    def is_expired(self, max_age_hours=24):
        """Check if session is expired"""
        from django.utils import timezone
        from datetime import timedelta
        
        expiry_time = self.last_activity + timedelta(hours=max_age_hours)
        return timezone.now() > expiry_time


class DesignApproval(models.Model):
    """
    Model to track design approval history and status changes.
    """
    ACTION_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('disabled', 'Disabled'),
        ('enabled', 'Enabled'),
    ]
    
    # Using relation system instead of direct ForeignKey
    product_id = models.IntegerField()  # Will be linked via relation
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    admin_notes = models.TextField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    approved_by_id = models.IntegerField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Audit fields
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'design_approval'
        verbose_name = 'Design Approval'
        verbose_name_plural = 'Design Approvals'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Design Approval {self.pk} - {self.get_action_display()}"
    
    @property
    def product(self):
        """Get the related product via relation system"""
        from Catalog.models import Product
        from common.relations import get_related
        try:
            # Create a temporary object with the product_id
            temp_obj = type('TempObj', (), {'pk': self.product_id})()
            products = get_related(temp_obj, 'Product:DesignApproval', Product)
            return products.first()
        except:
            return None
    
    def set_product(self, product):
        """Set the related product via relation system"""
        from common.relations import attach_relation
        attach_relation('Product:DesignApproval', product, self)
    
    @property
    def approved_by(self):
        """Get the admin who approved/rejected"""
        from django.contrib.auth.models import User
        try:
            return User.objects.get(pk=self.approved_by_id)
        except:
            return None
    
    def approve_design(self, approved_by, admin_notes, request=None):
        """
        Approve design - optimized for performance.
        Returns True on success, False on failure.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Update approval record
            self.action = 'approved'
            self.approved_by_id = approved_by.pk
            self.approved_at = timezone.now()
            self.admin_notes = admin_notes
            
            if request:
                self.ip_address = AdminActivityLog.get_client_ip(request)
                self.user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Use update_fields for better performance
            self.save(update_fields=['action', 'approved_by_id', 'approved_at', 'admin_notes', 'ip_address', 'user_agent'])
            logger.debug(f'[approve_design] Approval record saved: {self.id}')
        
            # Update product status - use update() to bypass signals and avoid hanging
            from Catalog.models import Product
            try:
                # Use update() instead of save() to bypass signals and avoid hanging
                # This is much faster and avoids pre_save/post_save signals
                Product.objects.filter(pk=self.product_id).update(
                    status='active',
                    rejection_reason=None
                )
                logger.debug(f'[approve_design] Product status updated: {self.product_id}, status=active')
            except Product.DoesNotExist:
                logger.error(f'[approve_design] Product {self.product_id} not found when approving design')
                return False
            except Exception as e:
                logger.error(f'[approve_design] Error updating product status: {str(e)}', exc_info=True)
                return False
            
            # Post to Pinterest (async - don't block approval)
            try:
                from django.conf import settings
                from common.models import PinterestPost, PinterestIntegration
                
                # Check if Pinterest is enabled
                integration = PinterestIntegration.get_instance()
                if integration.is_enabled:
                    # Create or get PinterestPost record
                    pinterest_post, created = PinterestPost.objects.get_or_create(
                        product_id=self.product_id,
                        defaults={'status': 'pending'}
                    )
                    
                    if created or pinterest_post.status == 'failed':
                        # Queue async task to post to Pinterest
                        from common.tasks import post_design_to_pinterest
                        
                        base_url = None
                        if request:
                            base_url = request.build_absolute_uri('/').rstrip('/')
                        
                        post_design_to_pinterest.delay(pinterest_post.id, base_url)
                        logger.info(f'[approve_design] Queued Pinterest post for product {self.product_id}')
                    else:
                        logger.debug(f'[approve_design] PinterestPost already exists for product {self.product_id}')
            except Exception as e:
                # Don't fail approval if Pinterest posting fails
                logger.warning(f'[approve_design] Failed to queue Pinterest post: {str(e)}', exc_info=True)
            
            # Index product PNG images into Qdrant for visual search (async - don't block approval)
            try:
                from Catalog.tasks import index_product_visual_search
                index_product_visual_search.delay(self.product_id)
                logger.info(f'[approve_design] Queued visual search indexing for product {self.product_id}')
            except Exception as e:
                logger.warning(f'[approve_design] Failed to queue visual search indexing: {str(e)}', exc_info=True)
            
            # TODO: Send notification to designer (async - don't block)
            # TODO: Send email notification (async - don't block)
            
            logger.info(f'[approve_design] Design approved successfully: product_id={self.product_id}')
            return True
            
        except Exception as e:
            logger.error(f'[approve_design] Exception during approval: {str(e)}', exc_info=True)
            return False
    
    def reject_design(self, approved_by, rejection_reason, admin_notes, request=None):
        """Reject design - optimized for performance"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Update approval record
            self.action = 'rejected'
            self.approved_by_id = approved_by.pk
            self.approved_at = timezone.now()
            self.rejection_reason = rejection_reason
            self.admin_notes = admin_notes
            
            if request:
                self.ip_address = AdminActivityLog.get_client_ip(request)
                self.user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Use update_fields for better performance
            self.save(update_fields=['action', 'approved_by_id', 'approved_at', 'rejection_reason', 'admin_notes', 'ip_address', 'user_agent'])
            logger.debug(f'[reject_design] Approval record saved: {self.id}')
        
            # Update product status - use update() to bypass signals and avoid hanging
            from Catalog.models import Product
            try:
                # Use update() instead of save() to bypass signals and avoid hanging
                # This is much faster and avoids pre_save/post_save signals
                Product.objects.filter(pk=self.product_id).update(
                    status='inactive',
                    rejection_reason=rejection_reason
                )
                logger.debug(f'[reject_design] Product status updated: {self.product_id}, status=inactive')
            except Product.DoesNotExist:
                logger.error(f'[reject_design] Product {self.product_id} not found when rejecting design')
                return False
            except Exception as e:
                logger.error(f'[reject_design] Error updating product status: {str(e)}', exc_info=True)
                return False
            
            # Send email notification to designer (async - don't block)
            try:
                from common.tasks import send_design_rejection_email_async
                send_design_rejection_email_async.delay(self.product_id, rejection_reason)
                logger.info(f'[reject_design] Queued rejection email for product {self.product_id}')
            except Exception as e:
                # Don't fail rejection if email queuing fails
                logger.warning(f'[reject_design] Failed to queue rejection email: {str(e)}', exc_info=True)
            
            logger.info(f'[reject_design] Design rejected successfully: product_id={self.product_id}')
            return True
            
        except Exception as e:
            logger.error(f'[reject_design] Exception during rejection: {str(e)}', exc_info=True)
            return False
    
    def disable_design(self, approved_by, admin_notes, request=None):
        """Disable design - optimized for performance"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Update approval record
            self.action = 'disabled'
            self.approved_by_id = approved_by.pk
            self.approved_at = timezone.now()
            self.admin_notes = admin_notes
            
            if request:
                self.ip_address = AdminActivityLog.get_client_ip(request)
                self.user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            # Use update_fields for better performance
            self.save(update_fields=['action', 'approved_by_id', 'approved_at', 'admin_notes', 'ip_address', 'user_agent'])
            logger.debug(f'[disable_design] Approval record saved: {self.id}')
        
            # Update product status - use update() to bypass signals and avoid hanging
            from Catalog.models import Product
            try:
                # Use update() instead of save() to bypass signals and avoid hanging
                # This is much faster and avoids pre_save/post_save signals
                Product.objects.filter(pk=self.product_id).update(
                    status='inactive'
                )
                logger.debug(f'[disable_design] Product status updated: {self.product_id}, status=inactive')
            except Product.DoesNotExist:
                logger.error(f'[disable_design] Product {self.product_id} not found when disabling design')
                return False
            except Exception as e:
                logger.error(f'[disable_design] Error updating product status: {str(e)}', exc_info=True)
                return False
            
            # TODO: Send notification to designer (async - don't block)
            # TODO: Send email notification (async - don't block)
            
            logger.info(f'[disable_design] Design disabled successfully: product_id={self.product_id}')
            return True
            
        except Exception as e:
            logger.error(f'[disable_design] Exception during disable: {str(e)}', exc_info=True)
            return False


class DesignAnalytics(models.Model):
    """
    Model to track design analytics and performance metrics.
    """
    # Using relation system instead of direct ForeignKey
    product_id = models.IntegerField()  # Will be linked via relation
    
    # Analytics metrics
    total_views = models.PositiveIntegerField(default=0)
    total_downloads = models.PositiveIntegerField(default=0)
    total_purchases = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    average_rating = models.FloatField(default=0.0)
    trending_score = models.FloatField(default=0.0)
    
    # Timestamps
    last_viewed_at = models.DateTimeField(null=True, blank=True)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    last_purchased_at = models.DateTimeField(null=True, blank=True)
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'design_analytics'
        verbose_name = 'Design Analytics'
        verbose_name_plural = 'Design Analytics'
        ordering = ['-trending_score', '-total_views']
    
    def __str__(self):
        return f"Design Analytics {self.pk} - Views: {self.total_views}"
    
    @property
    def product(self):
        """Get the related product via relation system"""
        from Catalog.models import Product
        from common.relations import get_related
        try:
            # Create a temporary object with the product_id
            temp_obj = type('TempObj', (), {'pk': self.product_id})()
            products = get_related(temp_obj, 'Product:DesignAnalytics', Product)
            return products.first()
        except:
            return None
    
    def set_product(self, product):
        """Set the related product via relation system"""
        from common.relations import attach_relation
        attach_relation('Product:DesignAnalytics', product, self)
    
    def update_views(self, count=1):
        """Update view count"""
        self.total_views += count
        self.last_viewed_at = timezone.now()
        self.calculate_trending_score()
        self.save()
    
    def update_downloads(self, count=1):
        """Update download count"""
        self.total_downloads += count
        self.last_downloaded_at = timezone.now()
        self.calculate_trending_score()
        self.save()
    
    def update_purchases(self, count=1, revenue=0.0):
        """Update purchase count and revenue"""
        self.total_purchases += count
        self.total_revenue += revenue
        self.last_purchased_at = timezone.now()
        self.calculate_trending_score()
        self.save()
    
    def update_rating(self, rating):
        """Update average rating"""
        self.average_rating = rating
        self.calculate_trending_score()
        self.save()
    
    def calculate_trending_score(self):
        """Calculate trending score based on various metrics"""
        # Simple trending score calculation
        # Can be enhanced with more sophisticated algorithms
        score = (
            self.total_views * 0.1 +
            self.total_downloads * 0.3 +
            self.total_purchases * 0.5 +
            self.average_rating * 0.1
        )
        self.trending_score = score


class CopyrightReport(models.Model):
    """
    Model to track copyright violation reports for designs.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
        ('design_disabled', 'Design Disabled'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Using relation system instead of direct ForeignKey
    product_id = models.IntegerField()  # Will be linked via relation
    reporter_id = models.IntegerField()  # Will be linked via relation
    
    # Report details
    title = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Resolution details
    resolution = models.TextField(blank=True, null=True)
    admin_notes = models.TextField(blank=True, null=True)
    resolved_by_id = models.IntegerField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Audit fields
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'copyright_report'
        verbose_name = 'Copyright Report'
        verbose_name_plural = 'Copyright Reports'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Copyright Report {self.pk} - {self.title}"
    
    @property
    def product(self):
        """Get the related product via relation system"""
        from Catalog.models import Product
        from common.relations import get_related
        try:
            # Create a temporary object with the product_id
            temp_obj = type('TempObj', (), {'pk': self.product_id})()
            products = get_related(temp_obj, 'Product:CopyrightReport', Product)
            return products.first()
        except:
            return None
    
    def set_product(self, product):
        """Set the related product via relation system"""
        from common.relations import attach_relation
        attach_relation('Product:CopyrightReport', product, self)
    
    @property
    def reporter(self):
        """Get the reporter user"""
        from django.contrib.auth.models import User
        try:
            return User.objects.get(pk=self.reporter_id)
        except:
            return None
    
    def set_reporter(self, user):
        """Set the reporter user"""
        self.reporter_id = user.pk
        self.save()
    
    @property
    def resolved_by(self):
        """Get the admin who resolved the report"""
        from django.contrib.auth.models import User
        try:
            return User.objects.get(pk=self.resolved_by_id)
        except:
            return None
    
    def resolve_report(self, resolved_by, resolution, admin_notes, request=None):
        """Resolve copyright report"""
        self.status = 'resolved'
        self.resolved_by_id = resolved_by.pk
        self.resolved_at = timezone.now()
        self.resolution = resolution
        self.admin_notes = admin_notes
        
        if request:
            self.ip_address = AdminActivityLog.get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        self.save()
        
        # TODO: Send notification to reporter
        # TODO: Send email notification
        
        return True
    
    def reject_report(self, resolved_by, admin_notes, request=None):
        """Reject copyright report"""
        self.status = 'rejected'
        self.resolved_by_id = resolved_by.pk
        self.resolved_at = timezone.now()
        self.admin_notes = admin_notes
        
        if request:
            self.ip_address = AdminActivityLog.get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        self.save()
        
        # TODO: Send notification to reporter
        # TODO: Send email notification
        
        return True
    
    def disable_design(self, resolved_by, resolution, admin_notes, request=None):
        """Disable design due to copyright violation"""
        self.status = 'design_disabled'
        self.resolved_by_id = resolved_by.pk
        self.resolved_at = timezone.now()
        self.resolution = resolution
        self.admin_notes = admin_notes
        
        if request:
            self.ip_address = AdminActivityLog.get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        self.save()
        
        # Disable the design - use update() to bypass signals and avoid hanging
        product = self.product
        if product:
            # Use update() instead of save() to bypass signals and avoid hanging
            # This is much faster and avoids pre_save/post_save signals
            from Catalog.models import Product
            Product.objects.filter(pk=product.pk).update(status='inactive')
        
        # TODO: Send notification to designer
        # TODO: Send notification to reporter
        # TODO: Send email notifications
        
        return True


class Refund(models.Model):
    """
    Model to track refunds for transactions.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('completed', 'Completed'),
    ]
    
    # Using relation system instead of direct ForeignKey
    order_id = models.IntegerField()  # Will be linked via relation
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    refund_reason = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Razorpay refund details
    razorpay_refund_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Admin details
    processed_by_id = models.IntegerField(null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, null=True)
    
    # Audit fields
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'refund'
        verbose_name = 'Refund'
        verbose_name_plural = 'Refunds'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Refund {self.pk} - {self.refund_amount} ({self.status})"
    
    @property
    def order(self):
        """Get the related order via relation system"""
        from Orders.models import Order
        from common.relations import get_related
        try:
            # Create a temporary object with the order_id
            temp_obj = type('TempObj', (), {'pk': self.order_id})()
            orders = get_related(temp_obj, 'Order:Refund', Order)
            return orders.first()
        except:
            return None
    
    def set_order(self, order):
        """Set the related order via relation system"""
        from common.relations import attach_relation
        attach_relation('Order:Refund', order, self)
    
    @property
    def processed_by(self):
        """Get the admin who processed the refund"""
        from django.contrib.auth.models import User
        try:
            return User.objects.get(pk=self.processed_by_id)
        except:
            return None
    
    def process_refund(self, processed_by, razorpay_refund_id, admin_notes, request=None):
        """Process refund"""
        self.status = 'processed'
        self.processed_by_id = processed_by.pk
        self.processed_at = timezone.now()
        self.razorpay_refund_id = razorpay_refund_id
        self.admin_notes = admin_notes
        
        if request:
            self.ip_address = AdminActivityLog.get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        self.save()
        
        # TODO: Send notification to customer
        # TODO: Send email notification
        
        return True
    
    def complete_refund(self, admin_notes=None):
        """Mark refund as completed"""
        self.status = 'completed'
        if admin_notes:
            self.admin_notes = admin_notes
        self.save()
        
        # TODO: Send notification to customer
        # TODO: Send email notification
        
        return True
    
    def fail_refund(self, admin_notes=None):
        """Mark refund as failed"""
        self.status = 'failed'
        if admin_notes:
            self.admin_notes = admin_notes
        self.save()
        
        # TODO: Send notification to customer
        # TODO: Send email notification
        
        return True


class RefundLog(models.Model):
    """
    Model to track refund activity logs.
    """
    ACTION_CHOICES = [
        ('created', 'Refund Created'),
        ('processed', 'Refund Processed'),
        ('completed', 'Refund Completed'),
        ('failed', 'Refund Failed'),
        ('cancelled', 'Refund Cancelled'),
    ]
    
    # Using relation system instead of direct ForeignKey
    refund_id = models.IntegerField()  # Will be linked via relation
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField()
    admin_user_id = models.IntegerField(null=True, blank=True)
    
    # Audit fields
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'refund_log'
        verbose_name = 'Refund Log'
        verbose_name_plural = 'Refund Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Refund Log {self.pk} - {self.get_action_display()}"
    
    @property
    def refund(self):
        """Get the related refund via relation system"""
        from .models import Refund
        from common.relations import get_related
        try:
            # Create a temporary object with the refund_id
            temp_obj = type('TempObj', (), {'pk': self.refund_id})()
            refunds = get_related(temp_obj, 'Refund:RefundLog', Refund)
            return refunds.first()
        except:
            return None
    
    def set_refund(self, refund):
        """Set the related refund via relation system"""
        from common.relations import attach_relation
        attach_relation('Refund:RefundLog', refund, self)
    
    @property
    def admin_user(self):
        """Get the admin user who performed the action"""
        from django.contrib.auth.models import User
        try:
            return User.objects.get(pk=self.admin_user_id)
        except:
            return None


class FinancialReport(models.Model):
    """
    Model to store generated financial reports.
    """
    REPORT_TYPE_CHOICES = [
        ('daily', 'Daily Report'),
        ('monthly', 'Monthly Report'),
        ('yearly', 'Yearly Report'),
        ('custom', 'Custom Period Report'),
    ]
    
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    
    # Report data
    total_transactions = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_refunds = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Transaction breakdown
    plan_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    bundle_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    design_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    custom_order_sales = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    designer_payouts = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Additional metrics
    pending_settlements = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    platform_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Report metadata
    report_data = models.JSONField(default=dict, blank=True)
    generated_by_id = models.IntegerField(null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    
    # File storage
    csv_file_path = models.CharField(max_length=500, blank=True, null=True)
    pdf_file_path = models.CharField(max_length=500, blank=True, null=True)
    
    class Meta:
        db_table = 'financial_report'
        verbose_name = 'Financial Report'
        verbose_name_plural = 'Financial Reports'
        ordering = ['-generated_at']
    
    def __str__(self):
        return f"Financial Report {self.pk} - {self.get_report_type_display()} ({self.period_start.date()} to {self.period_end.date()})"
    
    @property
    def generated_by(self):
        """Get the admin who generated the report"""
        from django.contrib.auth.models import User
        try:
            return User.objects.get(pk=self.generated_by_id)
        except:
            return None
    
    def generate_csv_export(self):
        """Generate CSV export of the report"""
        # TODO: Implement CSV export generation
        pass
    
    def generate_pdf_export(self):
        """Generate PDF export of the report"""
        # TODO: Implement PDF export generation
        pass
    
    def get_report_summary(self):
        """Get report summary data"""
        return {
            'period': f"{self.period_start.date()} to {self.period_end.date()}",
            'total_transactions': self.total_transactions,
            'total_amount': float(self.total_amount),
            'total_refunds': float(self.total_refunds),
            'net_revenue': float(self.net_revenue),
            'breakdown': {
                'plan_sales': float(self.plan_sales),
                'bundle_sales': float(self.bundle_sales),
                'design_sales': float(self.design_sales),
                'custom_order_sales': float(self.custom_order_sales),
                'designer_payouts': float(self.designer_payouts),
            },
            'pending_settlements': float(self.pending_settlements),
            'platform_commission': float(self.platform_commission),
        }


class DesignerOnboardingStatus(models.Model):
    """
    Model to track designer onboarding status and verification process.
    """
    ONBOARDING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    # Using relation system instead of direct ForeignKey
    designer_id = models.IntegerField()  # Will be linked via relation
    status = models.CharField(max_length=20, choices=ONBOARDING_STATUS_CHOICES, default='pending')
    
    # Verification flags
    superadmin_verified = models.BooleanField(default=False)
    moderator_verified = models.BooleanField(default=False)
    final_approval = models.BooleanField(default=False)
    
    # Rejection details
    rejection_reason = models.TextField(blank=True, null=True)
    rejected_by_id = models.IntegerField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    
    # Approval details
    approved_by_id = models.IntegerField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Verification details
    superadmin_verified_by_id = models.IntegerField(null=True, blank=True)
    superadmin_verified_at = models.DateTimeField(null=True, blank=True)
    
    moderator_verified_by_id = models.IntegerField(null=True, blank=True)
    moderator_verified_at = models.DateTimeField(null=True, blank=True)
    
    # Bank account details (encrypted)
    bank_account_number = models.TextField(blank=True, null=True)  # Encrypted
    bank_ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    bank_account_holder_name = models.CharField(max_length=255, blank=True, null=True)
    
    # Contact details (hidden from moderators)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    contact_address = models.TextField(blank=True, null=True)
    
    # Financial details (hidden from moderators)
    pan_number = models.CharField(max_length=20, blank=True, null=True)
    aadhar_number = models.CharField(max_length=20, blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'designer_onboarding_status'
        verbose_name = 'Designer Onboarding Status'
        verbose_name_plural = 'Designer Onboarding Statuses'
    
    def __str__(self):
        return f"Designer Onboarding {self.pk} - {self.get_status_display()}"
    
    @property
    def designer(self):
        """Get the related designer via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            # Create a temporary object with the designer_id
            temp_obj = type('TempObj', (), {'pk': self.designer_id})()
            users = get_related(temp_obj, 'User:DesignerOnboardingStatus', User)
            return users.first()
        except:
            return None
    
    def set_designer(self, designer):
        """Set the related designer via relation system"""
        from common.relations import attach_relation
        attach_relation('User:DesignerOnboardingStatus', designer, self)
    
    def can_be_approved(self):
        """Check if onboarding can be approved (both verifications done)"""
        return self.superadmin_verified and self.moderator_verified
    
    def approve_onboarding(self, approved_by):
        """Approve the onboarding request"""
        if not self.can_be_approved():
            return False
        
        self.status = 'approved'
        self.final_approval = True
        self.approved_by_id = approved_by.pk
        self.approved_at = timezone.now()
        self.save()
        return True
    
    def reject_onboarding(self, rejected_by, reason):
        """Reject the onboarding request"""
        self.status = 'rejected'
        self.rejection_reason = reason
        self.rejected_by_id = rejected_by.pk
        self.rejected_at = timezone.now()
        self.save()
        return True


class DesignerAccountSuspension(models.Model):
    """
    Model to track designer account suspensions and deletions.
    """
    SUSPENSION_REASON_CHOICES = [
        ('policy_violation', 'Policy Violation'),
        ('fraudulent_activity', 'Fraudulent Activity'),
        ('inactive_account', 'Inactive Account'),
        ('requested_by_designer', 'Requested by Designer'),
        ('other', 'Other'),
    ]
    
    # Using relation system instead of direct ForeignKey
    designer_id = models.IntegerField()  # Will be linked via relation
    is_suspended = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    
    # Suspension details
    suspension_reason = models.CharField(max_length=50, choices=SUSPENSION_REASON_CHOICES)
    suspension_notes = models.TextField(blank=True, null=True)
    suspended_by_id = models.IntegerField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    
    # Deletion details
    deletion_reason = models.CharField(max_length=50, choices=SUSPENSION_REASON_CHOICES, blank=True, null=True)
    deletion_notes = models.TextField(blank=True, null=True)
    deleted_by_id = models.IntegerField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Audit fields
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'designer_account_suspension'
        verbose_name = 'Designer Account Suspension'
        verbose_name_plural = 'Designer Account Suspensions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Designer Account Suspension {self.pk} - {'Suspended' if self.is_suspended else 'Deleted'}"
    
    @property
    def designer(self):
        """Get the related designer via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            # Create a temporary object with the designer_id
            temp_obj = type('TempObj', (), {'pk': self.designer_id})()
            users = get_related(temp_obj, 'User:DesignerAccountSuspension', User)
            return users.first()
        except:
            return None
    
    def set_designer(self, designer):
        """Set the related designer via relation system"""
        from common.relations import attach_relation
        attach_relation('User:DesignerAccountSuspension', designer, self)
    
    def suspend_account(self, suspended_by, reason, notes, request=None):
        """Suspend designer account"""
        self.is_suspended = True
        self.suspension_reason = reason
        self.suspension_notes = notes
        self.suspended_by_id = suspended_by.pk
        self.suspended_at = timezone.now()
        
        if request:
            self.ip_address = AdminActivityLog.get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        self.save()
        
        # Deactivate designer account
        designer = self.designer
        if designer:
            designer.is_active = False
            designer.save()
        
        return True
    
    def delete_account(self, deleted_by, reason, notes, request=None):
        """Delete designer account"""
        self.is_deleted = True
        self.deletion_reason = reason
        self.deletion_notes = notes
        self.deleted_by_id = deleted_by.pk
        self.deleted_at = timezone.now()
        
        if request:
            self.ip_address = AdminActivityLog.get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        self.save()
        
        # Permanently deactivate designer account
        designer = self.designer
        if designer:
            designer.is_active = False
            designer.save()
        
        return True


class DesignerNotification(models.Model):
    """
    Model to track system notifications sent to designers.
    """
    NOTIFICATION_TYPES = [
        ('onboarding_approved', 'Onboarding Approved'),
        ('onboarding_rejected', 'Onboarding Rejected'),
        ('payout_processed', 'Payout Processed'),
        ('payout_failed', 'Payout Failed'),
        ('account_suspended', 'Account Suspended'),
        ('account_deleted', 'Account Deleted'),
        ('system_update', 'System Update'),
        ('other', 'Other'),
    ]
    
    # Using relation system instead of direct ForeignKey
    designer_id = models.IntegerField()  # Will be linked via relation
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Priority field
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Scheduled notification fields
    scheduled_at = models.DateTimeField(null=True, blank=True)
    is_scheduled = models.BooleanField(default=False)
    
    # Delivery tracking
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    push_sent = models.BooleanField(default=False)
    push_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Read tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'designer_notification'
        verbose_name = 'Designer Notification'
        verbose_name_plural = 'Designer Notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Designer Notification {self.pk} - {self.get_notification_type_display()}"
    
    @property
    def designer(self):
        """Get the related designer via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            # Create a temporary object with the designer_id
            temp_obj = type('TempObj', (), {'pk': self.designer_id})()
            users = get_related(temp_obj, 'User:DesignerNotification', User)
            return users.first()
        except:
            return None
    
    def set_designer(self, designer):
        """Set the related designer via relation system"""
        from common.relations import attach_relation
        attach_relation('User:DesignerNotification', designer, self)
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


class CustomerAccountStatus(models.Model):
    """
    Model to track customer account status and management.
    """
    ACCOUNT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('deactivated', 'Deactivated'),
        ('blocked', 'Blocked'),
    ]
    
    DEACTIVATION_REASON_CHOICES = [
        ('policy_violation', 'Policy Violation'),
        ('fraudulent_activity', 'Fraudulent Activity'),
        ('inactive_account', 'Inactive Account'),
        ('requested_by_customer', 'Requested by Customer'),
        ('payment_issues', 'Payment Issues'),
        ('other', 'Other'),
    ]
    
    # Using relation system instead of direct ForeignKey
    customer_id = models.IntegerField()  # Will be linked via relation
    status = models.CharField(max_length=20, choices=ACCOUNT_STATUS_CHOICES, default='active')
    
    # Deactivation details
    deactivation_reason = models.CharField(max_length=50, choices=DEACTIVATION_REASON_CHOICES, blank=True, null=True)
    deactivation_notes = models.TextField(blank=True, null=True)
    deactivated_by_id = models.IntegerField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    
    # Reactivation details
    reactivated_by_id = models.IntegerField(null=True, blank=True)
    reactivated_at = models.DateTimeField(null=True, blank=True)
    
    # Audit fields
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_account_status'
        verbose_name = 'Customer Account Status'
        verbose_name_plural = 'Customer Account Statuses'
    
    def __str__(self):
        return f"Customer Account Status {self.pk} - {self.get_status_display()}"
    
    @property
    def customer(self):
        """Get the related customer via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            # Create a temporary object with the customer_id
            temp_obj = type('TempObj', (), {'pk': self.customer_id})()
            users = get_related(temp_obj, 'User:CustomerAccountStatus', User)
            return users.first()
        except:
            return None
    
    def set_customer(self, customer):
        """Set the related customer via relation system"""
        from common.relations import attach_relation
        attach_relation('User:CustomerAccountStatus', customer, self)
    
    def deactivate_account(self, deactivated_by, reason, notes, request=None):
        """Deactivate customer account"""
        self.status = 'deactivated'
        self.deactivation_reason = reason
        self.deactivation_notes = notes
        self.deactivated_by_id = deactivated_by.pk
        self.deactivated_at = timezone.now()
        
        if request:
            self.ip_address = AdminActivityLog.get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        self.save()
        
        # Deactivate customer account
        customer = self.customer
        if customer:
            customer.is_active = False
            customer.save()
        
        # TODO: Pause active subscription if exists
        # TODO: Send deactivation notification email
        
        return True
    
    def reactivate_account(self, reactivated_by, request=None):
        """Reactivate customer account"""
        self.status = 'active'
        self.reactivated_by_id = reactivated_by.pk
        self.reactivated_at = timezone.now()
        
        if request:
            self.ip_address = AdminActivityLog.get_client_ip(request)
            self.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        self.save()
        
        # Reactivate customer account
        customer = self.customer
        if customer:
            customer.is_active = True
            customer.save()
        
        # TODO: Resume paused subscription if exists
        # TODO: Send reactivation notification email
        
        return True


class CustomerViewHistory(models.Model):
    """
    Model to track customer view history.
    """
    VIEW_TYPE_CHOICES = [
        ('product', 'Product'),
        ('design', 'Design'),
        ('bundle', 'Bundle'),
        ('category', 'Category'),
        ('search', 'Search'),
    ]
    
    # Using relation system instead of direct ForeignKey
    customer_id = models.IntegerField()  # Will be linked via relation
    view_type = models.CharField(max_length=20, choices=VIEW_TYPE_CHOICES)
    item_id = models.IntegerField()  # ID of the viewed item (product, design, etc.)
    item_title = models.CharField(max_length=255)
    item_category = models.CharField(max_length=100, blank=True, null=True)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'customer_view_history'
        verbose_name = 'Customer View History'
        verbose_name_plural = 'Customer View Histories'
        ordering = ['-viewed_at']
    
    def __str__(self):
        return f"Customer View History {self.pk} - {self.item_title} ({self.view_type})"
    
    @property
    def customer(self):
        """Get the related customer via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            # Create a temporary object with the customer_id
            temp_obj = type('TempObj', (), {'pk': self.customer_id})()
            users = get_related(temp_obj, 'User:CustomerViewHistory', User)
            return users.first()
        except:
            return None
    
    def set_customer(self, customer):
        """Set the related customer via relation system"""
        from common.relations import attach_relation
        attach_relation('User:CustomerViewHistory', customer, self)


class CustomerDownloadHistory(models.Model):
    """
    Model to track customer download history.
    """
    DOWNLOAD_TYPE_CHOICES = [
        ('design', 'Design'),
        ('bundle', 'Bundle'),
        ('pdf', 'PDF'),
        ('other', 'Other'),
    ]
    
    # Using relation system instead of direct ForeignKey
    customer_id = models.IntegerField()  # Will be linked via relation
    download_type = models.CharField(max_length=20, choices=DOWNLOAD_TYPE_CHOICES)
    item_id = models.IntegerField()  # ID of the downloaded item
    item_title = models.CharField(max_length=255)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(blank=True, null=True)  # File size in bytes
    download_source = models.CharField(max_length=100, blank=True, null=True)  # order, subscription, etc.
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    downloaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'customer_download_history'
        verbose_name = 'Customer Download History'
        verbose_name_plural = 'Customer Download Histories'
        ordering = ['-downloaded_at']
    
    def __str__(self):
        return f"Customer Download History {self.pk} - {self.item_title} ({self.download_type})"
    
    @property
    def customer(self):
        """Get the related customer via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            # Create a temporary object with the customer_id
            temp_obj = type('TempObj', (), {'pk': self.customer_id})()
            users = get_related(temp_obj, 'User:CustomerDownloadHistory', User)
            return users.first()
        except:
            return None
    
    def set_customer(self, customer):
        """Set the related customer via relation system"""
        from common.relations import attach_relation
        attach_relation('User:CustomerDownloadHistory', customer, self)


class CustomerNotification(models.Model):
    """
    Model to track customer notifications.
    """
    NOTIFICATION_TYPES = [
        ('account_deactivated', 'Account Deactivated'),
        ('account_reactivated', 'Account Reactivated'),
        ('subscription_paused', 'Subscription Paused'),
        ('subscription_resumed', 'Subscription Resumed'),
        ('payment_successful', 'Payment Successful'),
        ('payment_failed', 'Payment Failed'),
        ('download_available', 'Download Available'),
        ('system_update', 'System Update'),
        ('other', 'Other'),
    ]
    
    # Using relation system instead of direct ForeignKey
    customer_id = models.IntegerField()  # Will be linked via relation
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Priority field
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Scheduled notification fields
    scheduled_at = models.DateTimeField(null=True, blank=True)
    is_scheduled = models.BooleanField(default=False)
    
    # Delivery tracking
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    push_sent = models.BooleanField(default=False)
    push_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Read tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'customer_notification'
        verbose_name = 'Customer Notification'
        verbose_name_plural = 'Customer Notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Customer Notification {self.pk} - {self.get_notification_type_display()}"
    
    @property
    def customer(self):
        """Get the related customer via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            # Create a temporary object with the customer_id
            temp_obj = type('TempObj', (), {'pk': self.customer_id})()
            users = get_related(temp_obj, 'User:CustomerNotification', User)
            return users.first()
        except:
            return None
    
    def set_customer(self, customer):
        """Set the related customer via relation system"""
        from common.relations import attach_relation
        attach_relation('User:CustomerNotification', customer, self)
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


class AdminNotification(models.Model):
    """
    Model to track admin notifications.
    """
    NOTIFICATION_TYPES = [
        ('support_message', 'Support Message'),
        ('order_update', 'Order Update'),
        ('design_submission', 'Design Submission'),
        ('custom_order', 'Custom Order'),
        ('system_update', 'System Update'),
        ('other', 'Other'),
    ]
    
    # Using relation system instead of direct ForeignKey
    admin_id = models.IntegerField()  # Will be linked via relation
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='other')
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Optional link to related object
    related_thread_id = models.IntegerField(null=True, blank=True)  # For support thread links
    related_order_id = models.IntegerField(null=True, blank=True)  # For order links
    
    # Delivery tracking
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    push_sent = models.BooleanField(default=False)
    push_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Read tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'admin_notification'
        verbose_name = 'Admin Notification'
        verbose_name_plural = 'Admin Notifications'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Admin Notification {self.pk} - {self.get_notification_type_display()}"
    
    @property
    def admin(self):
        """Get the related admin via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            temp_obj = type('TempObj', (), {'pk': self.admin_id})()
            users = get_related(temp_obj, 'User:AdminNotification', User)
            return users.first()
        except:
            return None
    
    def set_admin(self, admin):
        """Set the related admin via relation system"""
        from common.relations import attach_relation
        attach_relation('User:AdminNotification', admin, self)
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()


class AdminNotificationCampaign(models.Model):
    """
    Model to track admin-created notification campaigns (both sent and scheduled).
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    
    # Using relation system instead of direct ForeignKey
    admin_id = models.IntegerField()  # Will be linked via relation
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Priority field
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Recipients
    send_to_designers = models.BooleanField(default=False)
    send_to_customers = models.BooleanField(default=False)
    
    # Delivery method
    DELIVERY_METHOD_CHOICES = [
        ('in_app', 'In-App Only'),
        ('email', 'Email Only'),
        ('both', 'Both'),
    ]
    delivery_method = models.CharField(max_length=10, choices=DELIVERY_METHOD_CHOICES, default='both')
    
    # Status and scheduling
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    total_recipients = models.IntegerField(default=0)
    designers_count = models.IntegerField(default=0)
    customers_count = models.IntegerField(default=0)
    
    # Celery task tracking
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'admin_notification_campaign'
        verbose_name = 'Admin Notification Campaign'
        verbose_name_plural = 'Admin Notification Campaigns'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Admin Notification Campaign: {self.title} - {self.get_status_display()}"
    
    @property
    def admin(self):
        """Get the related admin via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            temp_obj = type('TempObj', (), {'pk': self.admin_id})()
            users = get_related(temp_obj, 'User:AdminNotificationCampaign', User)
            return users.first()
        except:
            return None
    
    def set_admin(self, admin):
        """Set the related admin via relation system"""
        from common.relations import attach_relation
        attach_relation('User:AdminNotificationCampaign', admin, self)
    
    def mark_as_sent(self, total_recipients, designers_count, customers_count):
        """Mark campaign as sent"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.total_recipients = total_recipients
        self.designers_count = designers_count
        self.customers_count = customers_count
        self.save()


class SystemConfig(models.Model):
    """
    Singleton model to store system-wide configuration.
    Only one instance should exist.
    """
    # Business settings
    commission_rate = models.FloatField(default=15.0)
    gst_percentage = models.FloatField(default=18.0)
    design_price = models.DecimalField(max_digits=10, decimal_places=2, default=50.00, help_text="Global price per design (all paid designs will use this price)")
    custom_order_price = models.DecimalField(max_digits=10, decimal_places=2, default=200.00, help_text="Default price for custom orders (minimum charge)")
    custom_order_time_slot_hours = models.IntegerField(default=1)
    minimum_required_designs = models.IntegerField(default=50)
    free_mock_pdf_downloads_no_plan_per_month = models.IntegerField(
        default=999,
        help_text="Free mock PDF downloads per month for users without a plan (use high value e.g. 999 for unlimited)"
    )
    maintenance_mode = models.BooleanField(default=False)
    
    # Landing page settings - Different sections need different designs
    hero_section_designs = models.JSONField(default=list, blank=True)  # [1, 2, 3] - For CardSwap in hero
    featured_designs = models.JSONField(default=list, blank=True)      # [4, 5, 6, 7, 8] - For featured section
    dome_gallery_designs = models.JSONField(default=list, blank=True)  # [1, 2, 3, ..., 50+] - For dome gallery
    
    # Landing page statistics
    landing_page_stats = models.JSONField(default=dict, blank=True)  # {totalClients, totalDesigners, totalDesignAssets}
    client_names = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'system_config'
        verbose_name = 'System Configuration'
        verbose_name_plural = 'System Configurations'
    
    def __str__(self):
        return "System Configuration"
    
    @classmethod
    def get_config(cls):
        """Get the singleton config instance, create if doesn't exist"""
        config, created = cls.objects.get_or_create(pk=1)
        return config
