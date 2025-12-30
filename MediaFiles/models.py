from django.db import models
from django.contrib.auth.models import User
import logging
import threading

# Thread-local storage for passing context during Media creation
_thread_local = threading.local()


def get_media_upload_path(instance, filename):
    """
    Callable upload_to function for Media model.
    
    File organization:
    - Design uploads (Product:Media): {user_id}/designs/{product_id}/{filename}
    - Profile photos: {user_id}/profile/{filename}
    - Business documents (PAN, MSME): {user_id}/documents/{filename}
    - Custom order deliverables: {user_id}/orders/{order_id}/deliverables/{filename}
    - Other uploads: {user_id}/media/{filename} (fallback)
    
    Context is passed via thread-local storage when creating Media objects.
    """
    # Get context from thread-local storage
    product_id = getattr(_thread_local, 'product_id', None)
    order_id = getattr(_thread_local, 'order_id', None)
    file_type = getattr(_thread_local, 'file_type', None)  # 'profile', 'document', 'deliverable'
    
    # Check if created_by is set and has an id
    if not (hasattr(instance, 'created_by') and instance.created_by and hasattr(instance.created_by, 'id')):
        # Fallback: use media/ directory if no user context
        return f'media/{filename}'
    
    user_id = instance.created_by.id
    
    # Custom order deliverables: {user_id}/orders/{order_id}/deliverables/
    if order_id and file_type == 'deliverable':
        return f'{user_id}/orders/{order_id}/deliverables/{filename}'
    
    # Design uploads: {user_id}/designs/{product_id}/
    if product_id:
        return f'{user_id}/designs/{product_id}/{filename}'
    
    # Profile photos: {user_id}/profile/
    if file_type == 'profile':
        return f'{user_id}/profile/{filename}'
    
    # Business documents: {user_id}/documents/
    if file_type == 'document':
        return f'{user_id}/documents/{filename}'
    
    # Default fallback: {user_id}/media/ (for other non-product uploads)
    return f'{user_id}/media/{filename}'


class Media(models.Model):
    MEDIA_TYPE_CHOICES = [
        ('video', 'Video'),
        ('image', 'Image'),
        ('cdr', 'CDR'),
        ('eps', 'EPS'),
        ('pdf', 'PDF'),
        ('doc', 'DOC'),
        ('docx', 'DOCX'),
        ('xls', 'XLS'),
        ('xlsx', 'XLSX'),
        ('other', 'Other'),
    ]
    
    file = models.FileField(upload_to=get_media_upload_path)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_media')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_media', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'media'
        verbose_name = 'Media'
        verbose_name_plural = 'Media'
    
    def __str__(self):
        return f"Media {self.pk} - {self.media_type}"
    
    @classmethod
    def set_product_context(cls, product_id):
        """
        Set product_id in thread-local storage for the current thread.
        This allows the upload_to callable to use the product_id when creating Media objects.
        
        Usage:
            Media.set_product_context(product_id)
            try:
                media = Media.objects.create(...)
            finally:
                Media.clear_product_context()
        """
        _thread_local.product_id = product_id
    
    @classmethod
    def clear_product_context(cls):
        """
        Clear product_id from thread-local storage.
        Should be called in a finally block after Media creation.
        """
        if hasattr(_thread_local, 'product_id'):
            delattr(_thread_local, 'product_id')
    
    @classmethod
    def set_order_context(cls, order_id):
        """
        Set order_id in thread-local storage for custom order deliverables.
        
        Usage:
            Media.set_order_context(order_id)
            try:
                media = Media.objects.create(...)
            finally:
                Media.clear_order_context()
        """
        _thread_local.order_id = order_id
        _thread_local.file_type = 'deliverable'
    
    @classmethod
    def clear_order_context(cls):
        """
        Clear order_id from thread-local storage.
        Should be called in a finally block after Media creation.
        """
        if hasattr(_thread_local, 'order_id'):
            delattr(_thread_local, 'order_id')
        if hasattr(_thread_local, 'file_type'):
            delattr(_thread_local, 'file_type')
    
    @classmethod
    def set_profile_context(cls):
        """
        Set profile photo context in thread-local storage.
        
        Usage:
            Media.set_profile_context()
            try:
                media = Media.objects.create(...)
            finally:
                Media.clear_profile_context()
        """
        _thread_local.file_type = 'profile'
    
    @classmethod
    def clear_profile_context(cls):
        """
        Clear profile photo context from thread-local storage.
        Should be called in a finally block after Media creation.
        """
        if hasattr(_thread_local, 'file_type'):
            delattr(_thread_local, 'file_type')
    
    @classmethod
    def set_document_context(cls):
        """
        Set business document context in thread-local storage.
        
        Usage:
            Media.set_document_context()
            try:
                media = Media.objects.create(...)
            finally:
                Media.clear_document_context()
        """
        _thread_local.file_type = 'document'
    
    @classmethod
    def clear_document_context(cls):
        """
        Clear business document context from thread-local storage.
        Should be called in a finally block after Media creation.
        """
        if hasattr(_thread_local, 'file_type'):
            delattr(_thread_local, 'file_type')
    
    def delete(self, *args, **kwargs):
        """
        Override delete to ensure the physical file is deleted from storage
        when the Media instance is deleted.
        """
        # Delete the file from storage before deleting the model instance
        if self.file:
            try:
                self.file.delete(save=False)
            except Exception as e:
                # Log the error but continue with model deletion
                # This prevents file deletion errors from blocking model deletion
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to delete media file {self.file.name}: {str(e)}")
        
        # Call the parent delete method to delete the model instance
        super().delete(*args, **kwargs)


class Relation(models.Model):
    RELATION_TYPE_CHOICES = [
        # Core Relations - sorted alphabetically
        ('Category:Product', 'Category and Product'),
        ('CollectionBundle:Product', 'Collection Bundle and Product'),
        ('Coupon:Usage', 'Coupon and Usage'),
        ('CustomOrderRequest:User', 'Custom Order Request and User'),
        ('CustomRequest:Media', 'Custom Request and Media'),
        ('DesignerProfile:Media', 'Designer Profile and Media'),
        ('Order:OrderTransaction', 'Order and Order Transaction'),
        ('Order:Refund', 'Order and Refund'),
        ('Order:RazorpayPayment', 'Order and Razorpay Payment'),
        ('OrderTransaction:Media', 'Order Transaction and Media'),
        ('OrderTransaction:WalletTransaction', 'Order Transaction and Wallet Transaction'),
        ('Product:Counter', 'Product and Counter'),
        ('Product:DesignAnalytics', 'Product and Design Analytics'),
        ('Product:DesignApproval', 'Product and Design Approval'),
        ('Product:Media', 'Product and Media'),
        ('Product:Plan', 'Product and Plan'),
        ('Product:Tag', 'Product and Tag'),
        ('Refund:RefundLog', 'Refund and Refund Log'),
        ('ReportIssue:Media', 'Report Issue and Media'),
        ('RazorpayPayment:Order', 'Razorpay Payment and Order'),
        ('Studio:Media', 'Studio and Media'),
        ('Tags:Product', 'Tags and Product'),
        ('TopDesignsReport:Product', 'Top Designs Report and Product'),
        ('TopDesignersReport:User', 'Top Designers Report and User'),
        ('User:Address', 'User and Address'),
        ('User:AdminActivityLog', 'User and Admin Activity Log'),
        ('User:AdminSession', 'User and Admin Session'),
        ('User:Cart', 'User and Cart'),
        ('User:CustomerAccountStatus', 'User and Customer Account Status'),
        ('User:CustomerDownloadHistory', 'User and Customer Download History'),
        ('User:CustomerNotification', 'User and Customer Notification'),
        ('User:CustomerViewHistory', 'User and Customer View History'),
        ('User:CustomOrderRequest', 'User and Custom Order Request'),
        ('User:DesignerAccountSuspension', 'User and Designer Account Suspension'),
        ('User:DesignerNotification', 'User and Designer Notification'),
        ('User:DesignerProfile', 'User and Designer Profile'),
        ('User:Email', 'User and Email'),
        ('User:FeedbackReview', 'User and Feedback Review'),
        ('User:Media', 'User and Media'),
        ('User:MobileNumber', 'User and Mobile Number'),
        ('User:Notification', 'User and Notification'),
        ('User:Order', 'User and Order'),
        ('User:OTP', 'User and OTP'),
        ('User:PDFDownload', 'User and PDF Download'),
        ('User:PromotionUsage', 'User and Promotion Usage'),
        ('User:RazorpayPayment', 'User and Razorpay Payment'),
        ('User:StudioMember', 'User and Studio Member'),
        ('User:Subscription', 'User and Subscription'),
        ('User:Wallet', 'User and Wallet'),
        ('Wallet:User', 'Wallet and User'),
        ('Wallet:WalletTransaction', 'Wallet and Wallet Transaction'),
        ('Wallet:WithdrawalRequest', 'Wallet and Withdrawal Request'),
        ('WithdrawalRequest:WalletTransaction', 'Withdrawal Request and Wallet Transaction'),
    ]
    
    id_1 = models.IntegerField()
    id_2 = models.IntegerField()
    relation_type = models.CharField(max_length=50, choices=RELATION_TYPE_CHOICES)
    meta = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_relations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_relations', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'relation'
        verbose_name = 'Relation'
        verbose_name_plural = 'Relations'
        unique_together = ['id_1', 'id_2', 'relation_type']
    
    def __str__(self):
        return f"Relation {self.pk} - {self.relation_type}"
    
    @classmethod
    def create_relation(cls, relation_type: str, id_1: int, id_2: int, meta: dict = None, created_by=None):
        return cls.objects.create(
            relation_type=relation_type,
            id_1=id_1,
            id_2=id_2,
            meta=meta or {},
            created_by=created_by
        )
    
    @classmethod
    def get_related_ids_for_left(cls, relation_type: str, left_id: int):
        return cls.objects.filter(
            relation_type=relation_type,
            id_1=left_id
        ).values_list('id_2', flat=True)
    
    @classmethod
    def get_related_ids_for_right(cls, relation_type: str, right_id: int):
        return cls.objects.filter(
            relation_type=relation_type,
            id_2=right_id
        ).values_list('id_1', flat=True)
    
    @classmethod
    def get_relations_for_left(cls, relation_type: str, left_id: int):
        return cls.objects.filter(
            relation_type=relation_type,
            id_1=left_id
        )
    
    @classmethod
    def get_relations_for_right(cls, relation_type: str, right_id: int):
        return cls.objects.filter(
            relation_type=relation_type,
            id_2=right_id
        )