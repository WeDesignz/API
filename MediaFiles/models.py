from django.db import models
from django.contrib.auth.models import User


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
    
    file = models.FileField(upload_to='media/')
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
        ('User:DesignerOnboardingStatus', 'User and Designer Onboarding Status'),
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