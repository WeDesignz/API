from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from django.dispatch import receiver
from common.relations import attach_relation, get_related_ids, get_related, detach_relation
from MediaFiles.models import Media
from common.studio_name_generator import generate_design_numbers
from Plans.models import Plan


class Category(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_categories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_categories', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'category'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name


class Product(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('draft', 'Draft'),
        ('deleted', 'Deleted'),
    ]
    
    PRODUCT_PLAN_TYPE_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('prime', 'Prime'),
        ('premium', 'Premium'),
    ]
    
    PRODUCT_VISIBILITY_CHOICES = [
        ('show', 'Show'),
        ('hide', 'Hide'),
    ]
    
    product_metadata = models.JSONField(default=dict, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    # NOTE: product_plan_type is used for categorization (free vs paid designs) only.
    # It does NOT restrict design access based on subscription plans.
    # ALL paid designs are available to ALL subscription plans.
    # Subscription plans only provide benefits (discounts, free downloads, mock PDFs, custom design hours, etc.)
    # They do NOT restrict which designs users can access or purchase.
    product_plan_type = models.CharField(max_length=20, choices=PRODUCT_PLAN_TYPE_CHOICES)
    product_number = models.CharField(max_length=50, blank=True, null=True, unique=True)  # General design number (WDG00000001)
    studio_design_number = models.CharField(max_length=50, blank=True, null=True)  # Studio-wise design number (LR0000001)
    color = models.CharField(max_length=50, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    visibility_status = models.CharField(max_length=10, choices=PRODUCT_VISIBILITY_CHOICES, default='show')
    rejection_reason = models.TextField(blank=True, null=True, help_text="Reason for rejection if design is rejected")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_products')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_products', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'product'
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
    
    def __str__(self):
        return self.title
    
    def get_media(self):
        return get_related(self, 'Product:Media', Media)

    def attach_media(self, media_obj, meta=None, created_by=None):
        return attach_relation('Product:Media', self, media_obj, meta=meta, created_by=created_by)
    
    def detach_media(self, media_obj):
        return detach_relation('Product:Media', self, media_obj)
    
    
    def get_tags(self):
        return get_related(self, 'Product:Tag', Tags)
    
    def attach_tag(self, tag_obj, meta=None, created_by=None):
        return attach_relation('Product:Tag', self, tag_obj, meta=meta, created_by=created_by)
    
    def detach_tag(self, tag_obj):
        return detach_relation('Product:Tag', self, tag_obj)
    
    def get_plans(self):
        return get_related(self, 'Product:Plan', Plan)
    
    def attach_plan(self, plan_obj, meta=None, created_by=None):
        return attach_relation('Product:Plan', self, plan_obj, meta=meta, created_by=created_by)
    
    def detach_plan(self, plan_obj):
        return detach_relation('Product:Plan', self, plan_obj)
    
    def get_counters(self):
        return get_related(self, 'Product:Counter', ProductCounter)
    
    def attach_counter(self, counter_obj, meta=None, created_by=None):
        return attach_relation('Product:Counter', self, counter_obj, meta=meta, created_by=created_by)
    
    def detach_counter(self, counter_obj):
        return detach_relation('Product:Counter', self, counter_obj)
    
class ProductCounter(models.Model):
    TYPE_CHOICES = [
        ('opened', 'Opened'),
        ('purchased', 'Purchased'),
        ('downloaded', 'Downloaded'),
    ]
    
    product_counter_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_product_counters')
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'product_counter'
        verbose_name = 'Product Counter'
        verbose_name_plural = 'Product Counters'
    
    def __str__(self):
        return f"Counter {self.pk} - {self.product_counter_type}"


class CollectionBundle(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('available', 'Available'),
        ('unavailable', 'Unavailable'),
    ]
    
    name = models.CharField(max_length=200)
    product_ids = models.TextField(default='')
    plan = models.ForeignKey('Plans.Plan', on_delete=models.CASCADE, related_name='collection_bundles')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_collection_bundles')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_collection_bundles', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'collection_bundle'
        verbose_name = 'Collection Bundle'
        verbose_name_plural = 'Collection Bundles'
    
    def __str__(self):
        return self.name


class Tags(models.Model):
    TYPE_CHOICES = [
        ('ai_generated', 'AI Generated'),
        ('metadata', 'Metadata'),
        ('manually_added', 'Manually Added'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    tags_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='manually_added')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tags')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_tags', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'tags'
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
    
    def __str__(self):
        return self.name


class PDFDownload(models.Model):
    """
    Model to track PDF downloads for users.
    Each user gets one free download, then they need to pay for additional downloads.
    One user can have multiple PDF downloads (one free + unlimited paid).
    """
    DOWNLOAD_TYPE_CHOICES = [
        ('free', 'Free Download'),
        ('paid', 'Paid Download'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    SELECTION_TYPE_CHOICES = [
        ('specific', 'Specific Product Selection'),
        ('search_results', 'First N from Search Results'),
    ]
    
    # User relationship will be handled via relations system
    download_type = models.CharField(max_length=10, choices=DOWNLOAD_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # PDF configuration
    total_pages = models.PositiveIntegerField(help_text="Number of pages in PDF (50, 100, 200, 300, or 500)")
    selection_type = models.CharField(max_length=20, choices=SELECTION_TYPE_CHOICES, default='search_results')
    selected_products = models.JSONField(default=list, help_text="List of product IDs for specific selection")
    search_filters = models.JSONField(default=dict, help_text="Search filters applied when generating PDF")
    
    # Product information - merged from PDFDownloadProduct
    included_products = models.JSONField(default=list, help_text="List of products included in this PDF with page numbers")
    products_count = models.PositiveIntegerField(default=0, help_text="Number of products included in PDF")
    
    # Pricing information
    price_per_design = models.DecimalField(max_digits=10, decimal_places=2, default=2.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Customer information for mock PDF
    customer_name = models.CharField(max_length=255, blank=True, null=True, help_text="Customer name for mock PDF")
    customer_mobile = models.CharField(max_length=20, blank=True, null=True, help_text="Customer mobile number for mock PDF")
    
    # Payment information (for paid downloads)
    razorpay_payment = models.ForeignKey('Razorpay.RazorpayPayment', on_delete=models.SET_NULL, null=True, blank=True, related_name='pdf_downloads')
    payment_status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ], default='pending')
    
    # File information
    pdf_file_path = models.CharField(max_length=500, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True, help_text="File size in bytes")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'pdf_download'
        verbose_name = 'PDF Download'
        verbose_name_plural = 'PDF Downloads'
        ordering = ['-created_at']
    
    def __str__(self):
        user = self.get_user()
        username = user.username if user else "Unknown User"
        return f"PDF Download {self.pk} - {username} - {self.download_type}"
    
    def calculate_total_amount(self):
        """Calculate total amount based on pricing rules using configurable settings"""
        from django.conf import settings
        
        if self.download_type == 'free':
            return 0.00
        
        # Specific product selection: use configured price per design
        if self.selection_type == 'specific' and self.selected_products:
            return len(self.selected_products) * float(settings.PAID_PDF_PRICE_PER_DESIGN_SELECTED)
        # First N from search results: use configured price per design
        elif self.selection_type == 'search_results':
            return self.total_pages * float(settings.PAID_PDF_PRICE_PER_DESIGN_FIRSTN)
        else:
            return 0.00
    
    def can_user_download_free(self):
        """Check if user can still download for free"""
        if self.download_type == 'free':
            user = self.get_user()
            if not user:
                return False
            # Check if user has already used their free download
            free_downloads = PDFDownload.objects.filter(
                download_type='free',
                status='completed'
            ).filter(
                id__in=[pdf.id for pdf in PDFDownload.objects.all() if pdf.get_user() == user]
            ).count()
            return free_downloads == 0
        return False
    
    def get_available_page_options(self):
        """Get available page options for PDF"""
        return [50, 100, 200, 300, 500]
    
    def validate_page_count(self):
        """Validate that page count is in allowed options"""
        return self.total_pages in self.get_available_page_options()
    
    def add_product_to_pdf(self, product_id, page_number):
        """Add a product to the PDF with page number"""
        product_info = {
            'product_id': product_id,
            'page_number': page_number,
            'added_at': self.created_at.isoformat()
        }
        self.included_products.append(product_info)
        self.products_count = len(self.included_products)
        self.save()
    
    def get_included_products(self):
        """Get list of included products with their details"""
        return self.included_products
    
    def get_products_count(self):
        """Get count of products included in PDF"""
        return self.products_count
    
    def get_user(self):
        """Get the user associated with this PDF download"""
        from common.relations import get_related
        users = get_related(self, 'User:PDFDownload', User)
        return users.first() if users.exists() else None
    
    def attach_user(self, user_obj, meta=None, created_by=None):
        """Attach a user to this PDF download"""
        from common.relations import attach_relation
        return attach_relation('User:PDFDownload', self, user_obj, meta=meta, created_by=created_by)
    
    def detach_user(self, user_obj):
        """Detach a user from this PDF download"""
        from common.relations import detach_relation
        return detach_relation('User:PDFDownload', self, user_obj)


# ==================== DESIGN NUMBER GENERATION ====================

@receiver(pre_save, sender=Product)
def generate_design_numbers_signal(sender, instance, **kwargs):
    """
    Automatically generate both general and studio-wise design numbers for Product.
    """
    # Only generate if both numbers are missing
    if not instance.product_number and not instance.studio_design_number:
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Product pre_save signal: Generating design numbers for product by user {instance.created_by.id if instance.created_by else 'None'}")
            
            # Get the studio's auto name from the creator
            if instance.created_by:
                # Check if the creator has a studio
                from Profiles.models import Studio
                logger.info(f"Product pre_save signal: Querying Studio for user {instance.created_by.id}...")
                studio = Studio.objects.filter(created_by=instance.created_by).first()
                logger.info(f"Product pre_save signal: Studio query completed, studio={studio.id if studio else None}")
                
                if studio and studio.wedesignz_auto_name:
                    # Generate both design numbers
                    logger.info(f"Product pre_save signal: Generating design numbers with studio name {studio.wedesignz_auto_name}...")
                    design_numbers = generate_design_numbers(studio.wedesignz_auto_name)
                    instance.product_number = design_numbers['general_number']
                    instance.studio_design_number = design_numbers['studio_number']
                    logger.info(f"Product pre_save signal: Generated numbers - general={instance.product_number}, studio={instance.studio_design_number}")
                else:
                    # Fallback to general number only if no studio
                    logger.info(f"Product pre_save signal: No studio found, generating general number only...")
                    from common.studio_name_generator import design_number_generator
                    instance.product_number = design_number_generator.generate_general_design_number()
                    logger.info(f"Product pre_save signal: Generated general number={instance.product_number}")
        except Exception as e:
            # Log error but don't fail the save
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating design numbers: {str(e)}", exc_info=True)
            
            # Fallback to general number only
            from common.studio_name_generator import design_number_generator
            instance.product_number = design_number_generator.generate_general_design_number()
