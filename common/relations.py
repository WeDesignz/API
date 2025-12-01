"""
Common relation helper functions for managing relationships via the Relation table.

This module provides typed helper functions to manage the 22 specific relationship types
that are stored in the Relation table instead of direct ForeignKey fields.
"""

from typing import List, Optional, Dict, Any
from django.db.models import QuerySet
from django.contrib.auth import get_user_model


def attach_relation(relation_type: str, left_obj, right_obj, meta: Optional[Dict[str, Any]] = None, created_by=None):
    """
    Create a relation between two objects using the Relation table.
    
    Args:
        relation_type: The type of relation (e.g., 'Product:Media')
        left_obj: The left object (id_1)
        right_obj: The right object (id_2)
        meta: Optional metadata dictionary
        created_by: User who created the relation
        
    Returns:
        The created Relation instance
    """
    from MediaFiles.models import Relation
    
    creator = created_by

    if creator is None and hasattr(left_obj, 'created_by'):
        creator = left_obj.created_by

    if creator is None and hasattr(right_obj, 'created_by'):
        creator = right_obj.created_by

    if creator is None:
        User = get_user_model()
        creator = User.objects.filter(is_superuser=True).first()

    if creator is None:
        raise ValueError('attach_relation requires a created_by user to satisfy relation constraints.')

    return Relation.objects.create(
        relation_type=relation_type,
        id_1=left_obj.pk,
        id_2=right_obj.pk,
        created_by=creator,
        meta=meta or {}
    )


def get_related_ids(left_obj, relation_type: str) -> List[int]:
    """
    Get the IDs of objects related to the left object via the specified relation type.
    
    Args:
        left_obj: The left object
        relation_type: The type of relation
        
    Returns:
        List of related object IDs
    """
    from MediaFiles.models import Relation
    
    return list(
        Relation.objects.filter(
            relation_type=relation_type,
            id_1=left_obj.pk
        ).values_list('id_2', flat=True)
    )


def get_related(left_obj, relation_type: str, model_cls) -> QuerySet:
    """
    Get the related objects for the left object via the specified relation type.
    
    Args:
        left_obj: The left object
        relation_type: The type of relation
        model_cls: The model class to query
        
    Returns:
        QuerySet of related objects
    """
    ids = get_related_ids(left_obj, relation_type)
    return model_cls.objects.filter(pk__in=ids)


def detach_relation(relation_type: str, left_obj, right_obj) -> bool:
    """
    Remove a relation between two objects.
    
    Args:
        relation_type: The type of relation
        left_obj: The left object
        right_obj: The right object
        
    Returns:
        True if relation was deleted, False if not found
    """
    from MediaFiles.models import Relation
    
    deleted_count, _ = Relation.objects.filter(
        relation_type=relation_type,
        id_1=left_obj.pk,
        id_2=right_obj.pk
    ).delete()
    
    return deleted_count > 0


def get_relations_for_left(left_obj, relation_type: str) -> QuerySet:
    """
    Get all Relation instances for the left object and relation type.
    
    Args:
        left_obj: The left object
        relation_type: The type of relation
        
    Returns:
        QuerySet of Relation instances
    """
    from MediaFiles.models import Relation
    
    return Relation.objects.filter(
        relation_type=relation_type,
        id_1=left_obj.pk
    )


def get_relations_for_right(right_obj, relation_type: str) -> QuerySet:
    """
    Get all Relation instances for the right object and relation type.
    
    Args:
        right_obj: The right object
        relation_type: The type of relation
        
    Returns:
        QuerySet of Relation instances
    """
    from MediaFiles.models import Relation
    
    return Relation.objects.filter(
        relation_type=relation_type,
        id_2=right_obj.pk
    )


def get_related_ids_for_right(right_obj, relation_type: str) -> List[int]:
    """
    Get the IDs of objects related to the right object via the specified relation type.
    
    Args:
        right_obj: The right object
        relation_type: The type of relation
        
    Returns:
        List of related object IDs
    """
    from MediaFiles.models import Relation
    
    return list(
        Relation.objects.filter(
            relation_type=relation_type,
            id_2=right_obj.pk
        ).values_list('id_1', flat=True)
    )


def get_related_for_right(right_obj, relation_type: str, model_cls) -> QuerySet:
    """
    Get the related objects for the right object via the specified relation type.
    
    Args:
        right_obj: The right object
        relation_type: The type of relation
        model_cls: The model class to query
        
    Returns:
        QuerySet of related objects
    """
    ids = get_related_ids_for_right(right_obj, relation_type)
    return model_cls.objects.filter(pk__in=ids)


# Relation type constants for type safety - sorted alphabetically
RELATION_TYPES = {
    # Core Relations
    'Category:Product',
    'CollectionBundle:Product',
    'Coupon:Usage',
    'CustomOrderRequest:User',
    'CustomRequest:Media',
    'DesignerProfile:Media',
    'Order:OrderTransaction',
    'Order:Refund',
    'Order:RazorpayPayment',
    'OrderTransaction:Media',
    'OrderTransaction:WalletTransaction',
    'Product:Counter',
    'Product:DesignAnalytics',
    'Product:DesignApproval',
    'Product:Media',
    'Product:Plan',
    'Product:Tag',
    'Refund:RefundLog',
    'ReportIssue:Media',
    'RazorpayPayment:Order',
    'Studio:Media',
    'Tags:Product',
    'TopDesignsReport:Product',
    'TopDesignersReport:User',
    'User:Address',
    'User:AdminActivityLog',
    'User:AdminSession',
    'User:Cart',
    'User:CustomerAccountStatus',
    'User:CustomerDownloadHistory',
    'User:CustomerNotification',
    'User:CustomerViewHistory',
    'User:CustomOrderRequest',
    'User:DesignerAccountSuspension',
    'User:DesignerNotification',
    'User:DesignerOnboardingStatus',
    'User:DesignerPayoutRequest',
    'User:DesignerProfile',
    'User:Email',
    'User:FeedbackReview',
    'User:Media',
    'User:MobileNumber',
    'User:Notification',
    'User:Order',
    'User:OTP',
    'User:PDFDownload',
    'User:PromotionUsage',
    'User:RazorpayPayment',
    'User:StudioMember',
    'User:Subscription',
    'User:Wallet',
    'Wallet:User',
    'Wallet:WalletTransaction',
    'Wallet:WithdrawalRequest',
    'WithdrawalRequest:WalletTransaction',
}
