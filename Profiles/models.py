from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from django.dispatch import receiver
from common.relations import attach_relation, get_related_ids, get_related, detach_relation
from MediaFiles.models import Media
from Catalog.models import Product
from common.studio_name_generator import generate_studio_name


class Addresses(models.Model):
    ADDRESS_TYPE_CHOICES = [
        ('home', 'Home'),
        ('work', 'Work'),
        ('other', 'Other'),
    ]
    
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    landmark = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES, default='home')
    is_postal = models.BooleanField(default=False)
    is_permanent = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_addresses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_addresses', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'addresses'
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'
    
    def __str__(self):
        return f"Address {self.pk} - {self.city}, {self.state}"


class DesignProcessingTask(models.Model):
    """
    Model to track asynchronous design processing tasks.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='design_processing_tasks')
    zip_file_path = models.CharField(max_length=500, help_text='Path to the stored zip file')
    total_designs = models.IntegerField(default=0, help_text='Total number of designs to process')
    processed_designs = models.IntegerField(default=0, help_text='Number of designs processed so far')
    failed_designs = models.IntegerField(default=0, help_text='Number of designs that failed to process')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_message = models.TextField(blank=True, null=True, help_text='Error message if processing failed')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'design_processing_task'
        verbose_name = 'Design Processing Task'
        verbose_name_plural = 'Design Processing Tasks'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Design Processing Task {self.pk} - {self.user.username} - {self.status}"
    
    @property
    def progress_percentage(self):
        """Calculate progress percentage."""
        if self.total_designs == 0:
            return 0
        return int((self.processed_designs / self.total_designs) * 100)


class DesignerProfile(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('suspended', 'Suspended'),
    ]
    
    bio = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True, help_text='User date of birth')
    skill_tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_individual = models.BooleanField(default=False, help_text='True if onboarding as individual, False if as company')
    onboarding_completed = models.BooleanField(default=False, db_index=True, help_text='True if all onboarding steps are completed')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_designer_profiles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_designer_profiles', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'designer_profile'
        verbose_name = 'Designer Profile'
        verbose_name_plural = 'Designer Profiles'
    
    def __str__(self):
        return f"Designer Profile {self.pk}"
    
    def get_media(self):
        return get_related(self, 'DesignerProfile:Media', Media)
    
    def attach_media(self, media_obj, meta=None, created_by=None):
        return attach_relation('DesignerProfile:Media', self, media_obj, meta=meta, created_by=created_by)
    
    def detach_media(self, media_obj):
        return detach_relation('DesignerProfile:Media', self, media_obj)
    
    def _calculate_onboarding_completion(self):
        """
        Calculate if all onboarding steps are completed.
        Returns True if onboarding is complete, False otherwise.
        """
        from Authentication.models import Email, MobileNumber
        from Catalog.models import Product
        # DesignProcessingTask is in the same file, so we can reference it directly
        
        # Step 1: Basic Profile (always True if DesignerProfile exists)
        step1_completed = True
        
        # Step 2: Studio created (for companies) or skip (for individuals)
        studio = Studio.objects.filter(created_by=self.created_by).first()
        if self.is_individual:
            step2_completed = True  # Individuals skip Step 2
        else:
            step2_completed = studio is not None
        
        # Email and Mobile verification
        email_verified = Email.objects.filter(
            email=self.created_by.email, 
            created_by=self.created_by, 
            is_verified=True
        ).exists()
        
        mobile_verified = MobileNumber.objects.filter(
            created_by=self.created_by, 
            is_primary=True, 
            is_verified=True
        ).exists()
        
        # Step 3: Legal Info (PAN card uploaded)
        step3_completed = False
        if studio:
            try:
                business_details = StudioBusinessDetails.objects.get(studio=studio)
                step3_completed = bool(business_details.pan_card)
            except StudioBusinessDetails.DoesNotExist:
                pass
        
        # Step 4: Designs uploaded 
        # Consider Step 4 complete if:
        # 1. Products exist (designs have been processed), OR
        # 2. A DesignProcessingTask exists (zip file was uploaded, processing in background)
        products_exist = Product.objects.filter(created_by=self.created_by).exists()
        processing_task_exists = DesignProcessingTask.objects.filter(
            user=self.created_by,
            status__in=['pending', 'processing', 'completed']
        ).exists()
        step4_completed = products_exist or processing_task_exists
        
        # All steps must be completed
        is_complete = (
            step1_completed and
            step2_completed and
            email_verified and
            mobile_verified and
            step3_completed and
            step4_completed
        )
        
        return is_complete
    
    def check_and_update_onboarding_status(self):
        """
        Check if all onboarding steps are completed and update onboarding_completed flag.
        Returns True if onboarding is complete, False otherwise.
        """
        is_complete = self._calculate_onboarding_completion()
        
        # Update the flag if it changed
        if self.onboarding_completed != is_complete:
            self.onboarding_completed = is_complete
            self.save(update_fields=['onboarding_completed', 'updated_at'])
        
        return is_complete
    
    @property
    def is_onboarding_complete(self):
        """
        Computed property as fallback - always accurate.
        Use this when you need guaranteed accuracy over performance.
        """
        return self._calculate_onboarding_completion()
    
    def is_studio_owner(self):
        """
        Check if this designer profile belongs to a studio owner.
        Returns True if the user created a studio, False otherwise.
        """
        return Studio.objects.filter(created_by=self.created_by).exists()
    
    def is_studio_member(self):
        """
        Check if this designer profile belongs to a studio member.
        Returns True if the user is a member of any studio, False otherwise.
        """
        return StudioMember.objects.filter(member=self.created_by, status='active').exists()
    
    def get_studio_membership(self):
        """
        Get the StudioMember relationship if this user is a member.
        Returns StudioMember object or None.
        """
        return StudioMember.objects.filter(member=self.created_by, status='active').first()
    
    def get_owned_studio(self):
        """
        Get the Studio owned by this user.
        Returns Studio object or None.
        """
        return Studio.objects.filter(created_by=self.created_by).first()
    
    @property
    def profile_type(self):
        """
        Get the profile type: 'owner', 'member', or 'individual'.
        """
        if self.is_studio_owner():
            return 'owner'
        elif self.is_studio_member():
            return 'member'
        else:
            return 'individual'
    
    @property
    def can_upload_designs(self):
        """
        Check if this profile can upload designs.
        Both owners and members can upload designs.
        """
        return self.is_studio_owner() or self.is_studio_member()
    
    @property
    def has_full_console_access(self):
        """
        Check if this profile has full console access.
        Only owners have full access, members have limited access.
        """
        return self.is_studio_owner()


class Studio(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('banned', 'Banned'),
    ]
    
    INDUSTRY_TYPE_CHOICES = [
        ('design_studio', 'Design Studio'),
        ('agency', 'Agency'),
        ('3d_studio', '3D Studio'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=100)
    wedesignz_auto_name = models.CharField(max_length=100, unique=True)
    studio_industry_type = models.CharField(max_length=20, choices=INDUSTRY_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    daily_design_generation_capacity = models.IntegerField(default=0)
    remarks = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_studios')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_studios', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'studio'
        verbose_name = 'Studio'
        verbose_name_plural = 'Studios'
    
    def __str__(self):
        return self.name
    
    def get_media(self):
        return get_related(self, 'Studio:Media', Media)
    
    def attach_media(self, media_obj, meta=None, created_by=None):
        return attach_relation('Studio:Media', self, media_obj, meta=meta, created_by=created_by)
    
    def detach_media(self, media_obj):
        return detach_relation('Studio:Media', self, media_obj)


class StudioBusinessDetails(models.Model):
    BUSINESS_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('partnership', 'Partnership'),
        ('company', 'Company'),
        ('llp', 'LLP'),
        ('other', 'Other'),
    ]
    BUSINESS_CATEGORY_CHOICES = [
        ('ecommerce', 'Ecommerce'),
        ('other', 'Other'),
    ]
    BUSINESS_SUB_CATEGORY_CHOICES = [
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('other', 'Other'),
    ]
    
    studio = models.OneToOneField(Studio, on_delete=models.CASCADE, related_name='business_details')
    studio_email = models.EmailField(blank=True, null=True)
    studio_mobile_number = models.CharField(max_length=15, blank=True, null=True)
    legal_business_name = models.CharField(max_length=200, blank=True, null=True)
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPE_CHOICES, blank=True, null=True)
    business_category = models.CharField(max_length=100, choices=BUSINESS_CATEGORY_CHOICES, blank=True, null=True)
    business_sub_category = models.CharField(max_length=100, choices=BUSINESS_SUB_CATEGORY_CHOICES, blank=True, null=True)
    business_model = models.CharField(max_length=100, blank=True, null=True)
    registered_addresses_json = models.JSONField(default=dict, blank=True, null=True)
    pan_number = models.CharField(max_length=20, blank=True, null=True)
    pan_card = models.URLField(blank=True, null=True)
    gst_number = models.CharField(max_length=20, blank=True, null=True)
    msme_udyam_number = models.CharField(max_length=50, blank=True, null=True)
    msme_certificate_annexure = models.URLField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_studio_business_details')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_studio_business_details', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'studio_business_details'
        verbose_name = 'Studio Business Details'
        verbose_name_plural = 'Studio Business Details'
    
    def __str__(self):
        return f"Business Details - {self.studio.name}"


class StudioMember(models.Model):
    ROLE_CHOICES = [
        ('design_lead', 'Design Lead'),
        ('designer', 'Designer'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name='members')
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='studio_memberships', null=True, blank=True, help_text='The user who is a member of this studio')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_studio_members', help_text='The user who added this member to the studio')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_studio_members', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'studio_member'
        verbose_name = 'Studio Member'
        verbose_name_plural = 'Studio Members'
    
    def __str__(self):
        return f"Studio Member {self.pk} - {self.studio.name} ({self.role})"
    


class Ratings(models.Model):
    RATING_TYPE_CHOICES = [
        ('studio', 'Studio'),
        ('member', 'Member'),
        ('product', 'Product'),
    ]
    
    STATUS_CHOICES = [
        ('show', 'Show'),
        ('hide', 'Hide'),
    ]
    
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE, related_name='ratings', null=True, blank=True)
    studio_member = models.ForeignKey(StudioMember, on_delete=models.CASCADE, related_name='ratings', null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ratings', null=True, blank=True)
    rating_type = models.CharField(max_length=20, choices=RATING_TYPE_CHOICES)
    rating_value = models.IntegerField()
    rating_title = models.CharField(max_length=200)
    rating_description = models.TextField()
    tags = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='show')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_ratings')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_ratings', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'ratings'
        verbose_name = 'Rating'
        verbose_name_plural = 'Ratings'
    
    def __str__(self):
        return f"Rating {self.pk} - {self.rating_type} ({self.rating_value}/5)"


# ==================== STUDIO AUTO NAME GENERATION ====================

@receiver(pre_save, sender=Studio)
def generate_studio_auto_name(sender, instance, **kwargs):
    """
    Automatically generate unique wedesignz_auto_name for Studio.
    This ensures every studio gets a unique auto-generated name.
    """
    if not instance.wedesignz_auto_name:
        # Generate unique studio name
        auto_name = generate_studio_name(strategy="hybrid")
        if auto_name:
            instance.wedesignz_auto_name = auto_name
        else:
            # Fallback to user ID based name if generation fails
            instance.wedesignz_auto_name = f"ST{instance.created_by.id:08d}" if instance.created_by else f"ST{instance.pk:08d}"