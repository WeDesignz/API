from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
import logging

from .email_service import EmailService
from .tasks import (
    send_order_confirmation_email_async,
    send_design_sale_notification_async,
    delete_cart_items_async
)
from Authentication.models import User as CustomUser, Email, MobileNumber, OTP
from Orders.models import Order, Cart
from Plans.models import Subscription
from Coupons.models import Coupon, CouponUsage
from CustomRequests.models import CustomOrderRequest
from Wallet.models import Wallet, WalletTransaction
from Profiles.models import Studio, StudioMember, DesignerProfile, StudioBusinessDetails
from Catalog.models import Product

logger = logging.getLogger(__name__)


# Authentication Signals
@receiver(post_save, sender=User)
def send_welcome_email_on_user_creation(sender, instance, created, **kwargs):
    """Send welcome email when a new user is created."""
    if created and instance.is_active:
        # Send email asynchronously to avoid blocking the request
        # Use threading to prevent timeout issues
        import threading
        def send_email_async():
            try:
                EmailService.send_welcome_email(instance)
            except Exception as e:
                logger.error(f"Failed to send welcome email to {instance.email}: {str(e)}")
        
        # Start email sending in background thread
        thread = threading.Thread(target=send_email_async, daemon=True)
        thread.start()


@receiver(post_save, sender=Email)
def send_email_verification_otp(sender, instance, created, **kwargs):
    """Send OTP when a new email is added for verification."""
    if created and not instance.is_verified:
        try:
            # Generate OTP (this would be handled in the view)
            # EmailService.send_otp_email(instance.created_by, otp_code, "email")
            pass
        except Exception as e:
            logger.error(f"Failed to send email verification OTP: {str(e)}")


@receiver(post_save, sender=MobileNumber)
def send_mobile_verification_otp(sender, instance, created, **kwargs):
    """Send OTP when a new mobile number is added for verification."""
    if created and not instance.is_verified:
        try:
            # Generate OTP (this would be handled in the view)
            # EmailService.send_otp_email(instance.created_by, otp_code, "mobile")
            pass
        except Exception as e:
            logger.error(f"Failed to send mobile verification OTP: {str(e)}")


# Order Signals
@receiver(post_save, sender=Order)
def send_order_confirmation_email(sender, instance, created, **kwargs):
    """Send order confirmation email when order status is success.
    NOTE: Disabled for cart orders as invoice emails are sent instead.
    """
    # Skip order confirmation email for cart orders - invoice emails are sent instead
    if instance.status == 'success' and instance.order_type != 'cart':
        try:
            # Send email asynchronously using Celery to avoid blocking the request
            send_order_confirmation_email_async.delay(instance.id)
        except Exception as e:
            logger.error(f"Failed to queue order confirmation email for order {instance.id}: {str(e)}")


# Custom Request Signals
@receiver(post_save, sender=CustomOrderRequest)
def send_custom_order_notification(sender, instance, created, **kwargs):
    """Send notifications for custom order status changes and schedule SLA check."""
    if created:
        # Send admin notification for new custom order
        try:
            send_mail(
                subject=f"New Custom Order Request #{instance.id}",
                message=f"A new custom order has been submitted by {instance.created_by.username}.\n\nTitle: {instance.title}\nDescription: {instance.description}\nBudget: ₹{instance.budget}\n\nPlease process this order within 1 hour.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send admin notification for custom order: {str(e)}")
        
        # Schedule SLA check task to run at the order's deadline
        try:
            from common.tasks import check_custom_order_sla
            
            # Schedule the task to run at the SLA deadline
            check_custom_order_sla.apply_async(
                args=[instance.id],
                eta=instance.sla_deadline
            )
            logger.info(f"Scheduled SLA check for custom order {instance.id} at {instance.sla_deadline}")
        except Exception as e:
            logger.error(f"Failed to schedule SLA check for custom order {instance.id}: {str(e)}", exc_info=True)
    
    elif instance.status == 'completed':
        # Send completion email to user
        try:
            delivery_time = int((timezone.now() - instance.created_at).total_seconds() / 60)
            EmailService.send_custom_order_completion_email(instance.created_by, instance, delivery_time)
        except Exception as e:
            logger.error(f"Failed to send custom order completion email: {str(e)}")


# Coupon Signals
@receiver(post_save, sender=CouponUsage)
def check_coupon_usage_limit(sender, instance, created, **kwargs):
    """Check if coupon has reached its usage limit."""
    if created:
        try:
            coupon = instance.coupon
            total_usages = CouponUsage.objects.filter(coupon=coupon).count()
            
            if coupon.max_usage > 0 and total_usages >= coupon.max_usage:
                coupon.status = 'expired'
                coupon.save()
                logger.info(f"Coupon {coupon.code} has reached its usage limit and is now expired")
        except Exception as e:
            logger.error(f"Failed to check coupon usage limit: {str(e)}")


@receiver(pre_delete, sender=Coupon)
def cleanup_coupon_related_data(sender, instance, **kwargs):
    """Clean up related data when coupon is deleted."""
    try:
        # Delete related coupon usages
        CouponUsage.objects.filter(coupon=instance).delete()
        logger.info(f"Cleaned up data for deleted coupon {instance.code}")
    except Exception as e:
        logger.error(f"Failed to cleanup coupon data: {str(e)}")


# Wallet Signals
@receiver(post_save, sender=Wallet)
def auto_link_wallet_to_user(sender, instance, created, **kwargs):
    """Automatically link wallet to user via relation system when wallet is created."""
    if created and instance.created_by:
        try:
            from Authentication.user_relations import get_user_wallets, attach_user_wallet
            
            # Check if wallet is already linked via relation system
            wallets = get_user_wallets(instance.created_by)
            if not wallets.filter(id=instance.id).exists():
                # Link wallet to user via relation system
                attach_user_wallet(instance.created_by, instance)
                logger.info(f"Automatically linked wallet {instance.id} to user {instance.created_by.id} via relation system")
        except Exception as e:
            logger.error(f"Failed to auto-link wallet {instance.id} to user: {str(e)}", exc_info=True)


@receiver(post_save, sender=WalletTransaction)
def send_wallet_transaction_notification(sender, instance, created, **kwargs):
    """Send notification for wallet transactions."""
    if created:
        try:
            EmailService.send_wallet_transaction_email(instance.created_by, instance)
        except Exception as e:
            logger.error(f"Failed to send wallet transaction notification: {str(e)}")


# Studio Signals
@receiver(post_save, sender=Studio)
def send_studio_approval_notification(sender, instance, created, **kwargs):
    """Send notification when studio status changes."""
    if not created and instance.status == 'active':
        try:
            send_mail(
                subject="Studio Approved - WeDesignz",
                message=f"Congratulations! Your studio '{instance.name}' has been approved and is now active.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.created_by.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send studio approval notification: {str(e)}")


@receiver(post_save, sender=StudioMember)
def send_studio_member_notification(sender, instance, created, **kwargs):
    """Send notification when studio member is added."""
    if created and instance.member:
        try:
            # Get the member's email (they might have multiple emails, get primary)
            from Authentication.models import Email
            member_email_obj = Email.objects.filter(created_by=instance.member, is_primary=True).first()
            member_email = member_email_obj.email if member_email_obj else instance.member.email
            
            send_mail(
                subject="Added to Studio - WeDesignz",
                message=f"You have been added to the studio '{instance.studio.name}' as a {instance.get_role_display()}.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member_email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send studio member notification: {str(e)}")


# Product Signals
@receiver(pre_delete, sender=Product)
def handle_product_deletion(sender, instance, **kwargs):
    """Handle product deletion by studio members - transfer ownership to WeDesignz."""
    try:
        # Check if product is being deleted by a studio member
        if hasattr(instance, 'created_by') and instance.created_by.groups.filter(name='Studio Members').exists():
            # Transfer ownership to WeDesignz admin
            admin_user = User.objects.filter(is_superuser=True).first()
            if admin_user:
                # Update the product ownership
                instance.created_by = admin_user
                instance.save()
                logger.info(f"Product {instance.name} ownership transferred to WeDesignz admin")
    except Exception as e:
        logger.error(f"Failed to handle product deletion: {str(e)}")


# Subscription Signals
@receiver(pre_save, sender=Subscription)
def store_subscription_old_status(sender, instance, **kwargs):
    """Store old subscription status before save to detect changes."""
    if instance.pk:
        try:
            old_instance = Subscription.objects.get(pk=instance.pk)
            # Store old status as instance attribute (thread-safe)
            instance._old_status = old_instance.status
        except Subscription.DoesNotExist:
            instance._old_status = None

@receiver(post_save, sender=Subscription)
def send_subscription_notification(sender, instance, created, **kwargs):
    """Send subscription notifications and initialize period tracking for annual plans."""
    # Only send activation email when status changes to 'active' (not on creation with 'pending' status)
    if not created:
        old_status = getattr(instance, '_old_status', None)
        # Only send activation email if status changed from something else to 'active'
        if old_status and old_status != 'active' and instance.status == 'active':
            try:
                from common.email_service import EmailService
                EmailService.send_subscription_purchase_email(instance.created_by, instance)
                logger.info(f"Subscription activation email sent to {instance.created_by.email} for subscription {instance.id}")
            except Exception as e:
                logger.error(f"Failed to send subscription notification: {str(e)}")
            
            # Initialize current_period_start for annual plans when subscription becomes active
            if instance.plan.plan_duration == 'annually' and not instance.current_period_start:
                instance.current_period_start = instance.created_at.date()
                instance.save(update_fields=['current_period_start'])
                logger.info(f"Initialized current_period_start for annual subscription {instance.id}")
    
    elif instance.status == 'cancelled':
        try:
            send_mail(
                subject="Subscription Cancelled - WeDesignz",
                message=f"Your {instance.plan.get_plan_name_display()} subscription has been cancelled. You can reactivate it anytime.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.created_by.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send subscription cancellation notification: {str(e)}")


# OTP Cleanup Signal
@receiver(post_save, sender=OTP)
def cleanup_expired_otps(sender, instance, **kwargs):
    """Clean up expired OTPs when a new one is created."""
    try:
        # Delete expired OTPs for the same user and type
        expired_otps = OTP.objects.filter(
            created_by=instance.created_by,
            otp_for=instance.otp_for,
            expires_at__lt=timezone.now()
        ).exclude(id=instance.id)
        
        expired_otps.delete()
        logger.info(f"Cleaned up {expired_otps.count()} expired OTPs for user {instance.created_by.username}")
    except Exception as e:
        logger.error(f"Failed to cleanup expired OTPs: {str(e)}")


# ==================== DESIGNER CONSOLE SIGNALS ====================

# Designer Profile Signals
@receiver(post_save, sender=DesignerProfile)
def send_designer_profile_verification_notification(sender, instance, created, **kwargs):
    """Send notification when designer profile status changes."""
    if not created and instance.status == 'verified':
        try:
            send_mail(
                subject="Designer Profile Verified - WeDesignz",
                message=f"Congratulations! Your designer profile has been verified and you can now start uploading designs.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.created_by.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send designer profile verification notification: {str(e)}")
    
    elif not created and instance.status == 'suspended':
        try:
            send_mail(
                subject="Designer Profile Suspended - WeDesignz",
                message=f"Your designer profile has been suspended. Please contact support for more information.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.created_by.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send designer profile suspension notification: {str(e)}")


# Design Upload Signals
@receiver(post_save, sender=Product)
def send_design_submission_notification(sender, instance, created, **kwargs):
    """Send notification when a new design is submitted for review."""
    if created and instance.status == 'draft':
        try:
            # Check if this is a bulk upload by checking product metadata
            # Bulk uploads typically have metadata indicating they're from bulk upload
            is_bulk_upload = False
            if hasattr(instance, 'product_metadata') and instance.product_metadata:
                is_bulk_upload = instance.product_metadata.get('source') == 'bulk_upload'
            
            # Skip email notifications for bulk uploads to avoid blocking
            # Bulk uploads can have hundreds of products, sending emails would be too slow
            if is_bulk_upload:
                logger.info(f"Product post_save signal: Skipping email notification for bulk upload product {instance.id}")
                return
            
            logger.info(f"Product post_save signal: Sending design submission notification for product {instance.id}...")
            # Send notification to admin asynchronously to avoid blocking the request
            import threading
            def send_email_async():
                try:
                    send_mail(
                        subject=f"New Design Submission #{instance.id} - WeDesignz",
                        message=f"A new design has been submitted by {instance.created_by.username}.\n\nTitle: {instance.title}\nCategory: {instance.category.name}\nPlatform ID: {instance.product_number}\n\nPlease review and approve/reject within 24 hours.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[settings.ADMIN_EMAIL],
                        fail_silently=True,
                    )
                    logger.info(f"Product post_save signal: Design submission notification sent for product {instance.id}")
                except Exception as e:
                    logger.error(f"Failed to send design submission notification: {str(e)}", exc_info=True)
            
            # Start email sending in background thread to avoid blocking
            thread = threading.Thread(target=send_email_async, daemon=True)
            thread.start()
        except Exception as e:
            logger.error(f"Failed to send design submission notification: {str(e)}", exc_info=True)
    
    elif not created and instance.status == 'active':
        # Design approved
        try:
            send_mail(
                subject="Design Approved - WeDesignz",
                message=f"Your design '{instance.title}' has been approved and is now live on the platform!",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.created_by.email],
                fail_silently=True,  # Changed to True to avoid blocking response
            )
        except Exception as e:
            logger.error(f"Failed to send design approval notification: {str(e)}")
    
    elif not created and instance.status == 'inactive':
        # Design rejected
        try:
            send_mail(
                subject="Design Rejected - WeDesignz",
                message=f"Your design '{instance.title}' has been rejected. Please check the feedback and resubmit with improvements.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.created_by.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send design rejection notification: {str(e)}")


# Settlement Signals
@receiver(post_save, sender=WalletTransaction)
def send_settlement_notification(sender, instance, created, **kwargs):
    """Send notification for settlement-related wallet transactions."""
    if created and 'settlement' in (instance.description or '').lower():
        try:
            send_mail(
                subject="Settlement Processed - WeDesignz",
                message=f"Your settlement has been processed.\n\nAmount: ₹{instance.amount}\nType: {instance.wallet_transaction_type}\nDescription: {instance.description}\n\nThank you for being a part of WeDesignz!",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.created_by.email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Failed to send settlement notification: {str(e)}")


# Design Sale Signals
# DISABLED: Design sale notification email is no longer sent.
# Designers receive wallet transaction emails which include design sale information.
# @receiver(post_save, sender=Order)
# def send_design_sale_notification(sender, instance, created, **kwargs):
#     """Send notification to designer when their design is sold."""
#     if instance.status == 'success':
#         try:
#             # Send notification asynchronously using Celery to avoid blocking the request
#             send_design_sale_notification_async.delay(instance.id)
#         except Exception as e:
#             logger.error(f"Failed to queue design sale notification for order {instance.id}: {str(e)}")


# Custom order comments now use OrderComment model - signals handled in Orders app


# ==================== ONBOARDING STATUS UPDATE SIGNALS ====================
# DISABLED: Onboarding status should only be set manually, not automatically via signals
# This prevents signals from overriding manual onboarding_completed settings

# @receiver(post_save, sender=Email)
# @receiver(post_save, sender=MobileNumber)
# @receiver(post_save, sender=Product)
# @receiver(post_delete, sender=Product)
# def update_onboarding_status_on_verification_or_product(sender, instance, **kwargs):
#     """Update onboarding_completed flag when email/mobile verification or product changes."""
#     try:
#         if hasattr(instance, 'created_by') and instance.created_by:
#             designer_profile = DesignerProfile.objects.filter(
#                 created_by=instance.created_by
#             ).first()
#             if designer_profile:
#                 designer_profile.check_and_update_onboarding_status()
#     except Exception as e:
#         logger.error(f"Failed to update onboarding status for {sender.__name__}: {str(e)}")


# @receiver(post_save, sender=StudioBusinessDetails)
# def update_onboarding_status_on_business_details(sender, instance, **kwargs):
#     """Update onboarding_completed flag when business details (PAN card) changes."""
#     try:
#         if instance.studio and instance.studio.created_by:
#             designer_profile = DesignerProfile.objects.filter(
#                 created_by=instance.studio.created_by
#             ).first()
#             if designer_profile:
#                 designer_profile.check_and_update_onboarding_status()
#     except Exception as e:
#         logger.error(f"Failed to update onboarding status for StudioBusinessDetails: {str(e)}")
