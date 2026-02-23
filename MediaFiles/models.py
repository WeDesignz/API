from django.db import models
from django.contrib.auth.models import User
import logging
import threading

# Thread-local storage for passing context during Media creation
_thread_local = threading.local()

# Global context store as fallback (keyed by thread_id + user_id + filename pattern)
# This is more reliable than thread-local in some cases (e.g., Celery tasks)
_context_store = {}
_context_lock = threading.Lock()

# Keep default storage - no custom storage needed

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
    # #region agent log
    import json
    import os
    log_path = os.getenv('DEBUG_LOG_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', 'debug.log'))
    try:
        product_id = getattr(_thread_local, 'product_id', None)
        order_id = getattr(_thread_local, 'order_id', None)
        file_type = getattr(_thread_local, 'file_type', None)
        user_id = instance.created_by.id if (hasattr(instance, 'created_by') and instance.created_by and hasattr(instance.created_by, 'id')) else None
        with open(log_path, 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"MediaFiles/models.py:get_media_upload_path","message":"get_media_upload_path called","data":{"filename":filename,"product_id":product_id,"order_id":order_id,"file_type":file_type,"user_id":user_id,"has_created_by":hasattr(instance,'created_by')},"timestamp":int(__import__('time').time()*1000)})+'\n')
    except: pass
    # #endregion
    
    # Get context from thread-local storage
    product_id = getattr(_thread_local, 'product_id', None)
    order_id = getattr(_thread_local, 'order_id', None)
    file_type = getattr(_thread_local, 'file_type', None)  # 'profile', 'document', 'deliverable'
    
    # FALLBACK 1: If product_id not in thread-local, try global context store
    if not product_id:
        thread_id = threading.get_ident()
        with _context_lock:
            if thread_id in _context_store:
                product_id = _context_store[thread_id].get('product_id')
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"MediaFiles/models.py:get_media_upload_path","message":"Using global context store fallback","data":{"product_id":product_id,"thread_id":thread_id},"timestamp":int(__import__('time').time()*1000)})+'\n')
                except: pass
                # #endregion
    
    # FALLBACK 2: If still not found, try instance-level storage
    if not product_id and hasattr(instance, '_temp_product_id') and instance._temp_product_id:
        product_id = instance._temp_product_id
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"MediaFiles/models.py:get_media_upload_path","message":"Using instance-level product_id fallback","data":{"product_id":product_id},"timestamp":int(__import__('time').time()*1000)})+'\n')
        except: pass
        # #endregion
    
    # Check if created_by is set and has an id
    if not (hasattr(instance, 'created_by') and instance.created_by and hasattr(instance.created_by, 'id')):
        # Fallback: use root directory if no user context (Django will prepend MEDIA_URL)
        result = filename
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"MediaFiles/models.py:get_media_upload_path","message":"No user context, using media/ fallback","data":{"result_path":result},"timestamp":int(__import__('time').time()*1000)})+'\n')
        except: pass
        # #endregion
        return result
    
    user_id = instance.created_by.id
    
    # Custom order deliverables: {user_id}/orders/{order_id}/deliverables/
    if order_id and file_type == 'deliverable':
        result = f'{user_id}/orders/{order_id}/deliverables/{filename}'
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"MediaFiles/models.py:get_media_upload_path","message":"Order deliverable path","data":{"result_path":result},"timestamp":int(__import__('time').time()*1000)})+'\n')
        except: pass
        # #endregion
        return result
    
    # Design uploads: {user_id}/designs/{product_id}/
    if product_id:
        result = f'{user_id}/designs/{product_id}/{filename}'
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"MediaFiles/models.py:get_media_upload_path","message":"Product design path (CORRECT)","data":{"result_path":result,"product_id":product_id},"timestamp":int(__import__('time').time()*1000)})+'\n')
        except: pass
        # #endregion
        return result
    
    # FALLBACK: Try to infer product_id from filename pattern (WDG00000001.png, etc.)
    # This handles cases where thread-local storage might not work (e.g., Celery tasks)
    # Only use this for files that look like product design files (WDG prefix)
    import re
    product_number_match = re.match(r'^WDG(\d+)', filename, re.IGNORECASE)
    if product_number_match and not file_type:  # Only for design files, not profile/documents
        try:
            from Catalog.models import Product
            # Extract product number from filename (handle cases like WDG00000001_PNG.avif or WDG00000001_MOCKUP.jpg)
            base_name = filename.split('_')[0] if '_' in filename else filename.split('.')[0]
            # Try to find product by product_number for this user (most recent first)
            product = Product.objects.filter(
                created_by_id=user_id,
                product_number__iexact=base_name
            ).order_by('-id').first()
            if product:
                result = f'{user_id}/designs/{product.id}/{filename}'
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"MediaFiles/models.py:get_media_upload_path","message":"Product design path (FALLBACK from filename DB lookup)","data":{"result_path":result,"product_id":product.id,"filename":filename,"base_name":base_name},"timestamp":int(__import__('time').time()*1000)})+'\n')
                except: pass
                # #endregion
                return result
        except Exception as e:
            # #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"MediaFiles/models.py:get_media_upload_path","message":"Fallback product lookup failed","data":{"error":str(e),"filename":filename},"timestamp":int(__import__('time').time()*1000)})+'\n')
            except: pass
            # #endregion
            pass
    
    # Profile photos: {user_id}/profile/
    if file_type == 'profile':
        result = f'{user_id}/profile/{filename}'
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"MediaFiles/models.py:get_media_upload_path","message":"Profile photo path","data":{"result_path":result},"timestamp":int(__import__('time').time()*1000)})+'\n')
        except: pass
        # #endregion
        return result
    
    # Business documents: {user_id}/documents/
    if file_type == 'document':
        result = f'{user_id}/documents/{filename}'
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"MediaFiles/models.py:get_media_upload_path","message":"Document path","data":{"result_path":result},"timestamp":int(__import__('time').time()*1000)})+'\n')
        except: pass
        # #endregion
        return result
    
    # Default fallback: {user_id}/media/ (for other non-product uploads)
    result = f'{user_id}/media/{filename}'
    # #region agent log
    try:
        with open(log_path, 'a') as f:
            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"MediaFiles/models.py:get_media_upload_path","message":"FALLBACK to media/ folder (PROBLEM)","data":{"result_path":result,"product_id":product_id,"reason":"No product_id in thread-local"},"timestamp":int(__import__('time').time()*1000)})+'\n')
    except: pass
    # #endregion
    return result

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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store product_id temporarily on instance for upload_to function
        # This is a fallback if thread-local storage doesn't work
        self._temp_product_id = None
    
    @classmethod
    def set_product_context(cls, product_id):
        """
        Set product_id in thread-local storage for the current thread.
        This allows the upload_to callable to use the product_id when creating Media objects.
        
        Also stores in global context store as fallback for reliability.
        
        Usage:
            Media.set_product_context(product_id)
            try:
                media = Media.objects.create(...)
            finally:
                Media.clear_product_context()
        """
        _thread_local.product_id = product_id
        # Also store in global context store as fallback
        thread_id = threading.get_ident()
        with _context_lock:
            _context_store[thread_id] = {'product_id': product_id}
    
    def set_temp_product_id(self, product_id):
        """
        Set product_id temporarily on this instance.
        This is used as a fallback if thread-local storage doesn't work.
        """
        self._temp_product_id = product_id
    
    @classmethod
    def clear_product_context(cls):
        """
        Clear product_id from thread-local storage and global context store.
        Should be called in a finally block after Media creation.
        """
        if hasattr(_thread_local, 'product_id'):
            delattr(_thread_local, 'product_id')
        # Also clear from global context store
        thread_id = threading.get_ident()
        with _context_lock:
            if thread_id in _context_store:
                del _context_store[thread_id]
    
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