from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count
from django.db import transaction
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import logging
import os
import shutil
from django.core.files.storage import default_storage

from .email_service import EmailService
from Authentication.models import OTP
from Plans.models import Subscription, Plan
from Coupons.models import Coupon, CouponUsage
from Orders.models import Order, Cart, Invoice
from CustomRequests.models import CustomOrderRequest
from Wallet.models import WalletWithdrawalRequest, SettlementRequest
from Profiles.models import Studio, StudioMember
from Catalog.models import Product
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


def calculate_period_end_balance(designer, period_end):
    """
    Calculate wallet balance as of the end of the settlement period.
    This includes ALL transactions from the beginning of time up to period_end.
    
    This ensures that:
    - Only transactions up to the end of previous month are included
    - Any credits on Day 1 of new month are excluded
    - The balance matches what the wallet should have been at period_end
    
    Args:
        designer: User object (designer)
        period_end: date object (last day of previous month)
    
    Returns:
        Decimal: Balance at period end (sum of all credits - debits up to period_end)
    """
    from datetime import datetime, time
    from decimal import Decimal
    import pytz
    from django.db.models import Sum
    from Wallet.models import WalletTransaction
    from Authentication.user_relations import get_user_wallets
    from common.relations import get_related
    
    # Create period end datetime (end of day in IST)
    kolkata_tz = pytz.timezone('Asia/Kolkata')
    period_end_datetime = kolkata_tz.localize(
        datetime.combine(period_end, time.max)  # 23:59:59.999999
    )
    
    # Collect all transaction IDs (from both created_by and wallet relations)
    all_transaction_ids = set()
    
    # Method 1: Transactions by created_by
    transactions_by_user = WalletTransaction.objects.filter(
        created_by=designer,
        created_at__lte=period_end_datetime
    )
    all_transaction_ids.update(transactions_by_user.values_list('id', flat=True))
    
    # Method 2: Transactions via wallet relations (more comprehensive)
    wallets = get_user_wallets(designer)
    for wallet in wallets:
        wallet_transactions = get_related(wallet, 'Wallet:WalletTransaction', WalletTransaction)
        wallet_transactions = wallet_transactions.filter(
            created_at__lte=period_end_datetime
        )
        all_transaction_ids.update(wallet_transactions.values_list('id', flat=True))
    
    if not all_transaction_ids:
        return Decimal('0')
    
    # Aggregate credits and debits using database aggregation (faster than looping)
    transactions = WalletTransaction.objects.filter(id__in=all_transaction_ids)
    
    credits = transactions.filter(
        wallet_transaction_type='credit'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    debits = transactions.filter(
        wallet_transaction_type='debit'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    period_end_balance = Decimal(str(credits)) - Decimal(str(debits))
    
    return period_end_balance


def calculate_unsettled_balance(designer, period_end):
    """
    Calculate wallet balance from only UNSETTLED transactions up to period_end.
    
    This ensures that:
    - Only transactions that haven't been settled yet are included
    - Previously settled transactions are excluded
    - Only transactions up to the end of previous month are included
    - Any credits on Day 1 of new month are excluded
    - The balance matches what should be available for settlement
    
    Args:
        designer: User object (designer)
        period_end: date object (last day of previous month)
    
    Returns:
        Decimal: Unsettled balance at period end (sum of unsettled credits - all debits up to period_end)
    """
    from datetime import datetime, time
    from decimal import Decimal
    import pytz
    from django.db.models import Sum
    from Wallet.models import WalletTransaction
    from Authentication.user_relations import get_user_wallets
    from common.relations import get_related
    
    # Create period end datetime (end of day in IST)
    kolkata_tz = pytz.timezone('Asia/Kolkata')
    period_end_datetime = kolkata_tz.localize(
        datetime.combine(period_end, time.max)  # 23:59:59.999999
    )
    
    # Collect all transaction IDs (from both created_by and wallet relations)
    all_transaction_ids = set()
    
    # Method 1: Transactions by created_by
    transactions_by_user = WalletTransaction.objects.filter(
        created_by=designer,
        created_at__lte=period_end_datetime
    )
    all_transaction_ids.update(transactions_by_user.values_list('id', flat=True))
    
    # Method 2: Transactions via wallet relations (more comprehensive)
    wallets = get_user_wallets(designer)
    for wallet in wallets:
        wallet_transactions = get_related(wallet, 'Wallet:WalletTransaction', WalletTransaction)
        wallet_transactions = wallet_transactions.filter(
            created_at__lte=period_end_datetime
        )
        all_transaction_ids.update(wallet_transactions.values_list('id', flat=True))
    
    if not all_transaction_ids:
        return Decimal('0')
    
    # Get all transactions
    transactions = WalletTransaction.objects.filter(id__in=all_transaction_ids)
    
    # Get only UNSETTLED credits (credits that haven't been included in any settlement)
    unsettled_credits = transactions.filter(
        wallet_transaction_type='credit',
        settlement_request__isnull=True  # Only unsettled transactions
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    # Get ALL debits (including settlement debits from previous months)
    all_debits = transactions.filter(
        wallet_transaction_type='debit'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    
    unsettled_balance = Decimal(str(unsettled_credits)) - Decimal(str(all_debits))
    
    return unsettled_balance


@shared_task(bind=True, name='common.tasks.send_promotional_emails')
def send_promotional_emails(self):
    """Send scheduled promotional emails to active users."""
    try:
        # Get active users who haven't received promotional emails recently
        cutoff_date = timezone.now() - timedelta(days=7)
        users = User.objects.filter(
            is_active=True,
            last_login__gte=cutoff_date
        ).exclude(
            email__in=[]  # Exclude users who opted out
        )[:1000]  # Limit to 1000 users per batch
        
        if users.exists():
            # Get promotional content (this would be dynamic based on your content management)
            promotional_content = {
                'subject': '🎨 New Design Collection Available!',
                'template': 'emails/promotional/design_collection.html',
                'context': {
                    'featured_designs': Product.objects.filter(status='active')[:5],
                    'discount_percentage': 20,
                    'expiry_date': timezone.now() + timedelta(days=3)
                }
            }
            
            success_count = EmailService.send_promotional_email(
                users, 
                promotional_content['subject'],
                promotional_content['template'],
                promotional_content['context']
            )
            
            logger.info(f"Promotional emails sent to {success_count} users")
            return f"Promotional emails sent to {success_count} users"
        else:
            logger.info("No eligible users for promotional emails")
            return "No eligible users for promotional emails"
            
    except Exception as e:
        logger.error(f"Failed to send promotional emails: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.update_subscription_status')
def update_subscription_status(self):
    """Update subscription status for recurring billing."""
    try:
        # Find subscriptions that need renewal
        renewal_date = timezone.now() + timedelta(days=1)
        subscriptions_to_renew = Subscription.objects.filter(
            status='active',
            auto_renew=True,
            created_at__lte=renewal_date - timedelta(days=30)  # Monthly subscriptions
        )
        
        renewed_count = 0
        for subscription in subscriptions_to_renew:
            try:
                # Check if payment method is available and process renewal
                # This would integrate with Razorpay for auto-renewal
                subscription.status = 'renewed'
                subscription.save()
                
                # Send renewal notification
                EmailService.send_subscription_renewal_email(subscription.created_by, subscription)
                renewed_count += 1
                
            except Exception as e:
                logger.error(f"Failed to renew subscription {subscription.id}: {str(e)}")
                # Mark subscription as failed if payment fails
                subscription.status = 'failed'
                subscription.save()
        
        logger.info(f"Updated {renewed_count} subscription statuses")
        return f"Updated {renewed_count} subscription statuses"
        
    except Exception as e:
        logger.error(f"Failed to update subscription status: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.send_auto_mandate_notifications')
def send_auto_mandate_notifications(self):
    """Send notifications for upcoming auto-mandate transactions."""
    try:
        # Find subscriptions that will be auto-renewed in the next 3 days
        notification_date = timezone.now() + timedelta(days=3)
        upcoming_renewals = Subscription.objects.filter(
            status='active',
            auto_renew=True,
            created_at__lte=notification_date - timedelta(days=30)
        )
        
        notified_count = 0
        for subscription in upcoming_renewals:
            try:
                send_mail(
                    subject="Upcoming Subscription Renewal - WeDesignz",
                    message=f"Your {subscription.plan.get_plan_name_display()} subscription will be automatically renewed on {notification_date.strftime('%B %d, %Y')}.\n\nAmount: ₹{subscription.plan.price}\n\nTo cancel auto-renewal, please visit your account settings.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[subscription.created_by.email],
                    fail_silently=False,
                )
                notified_count += 1
                
            except Exception as e:
                logger.error(f"Failed to send auto-mandate notification to {subscription.created_by.email}: {str(e)}")
        
        logger.info(f"Sent auto-mandate notifications to {notified_count} users")
        return f"Sent auto-mandate notifications to {notified_count} users"
        
    except Exception as e:
        logger.error(f"Failed to send auto-mandate notifications: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.cleanup_expired_otps')
def cleanup_expired_otps(self):
    """Clean up expired OTPs from the database."""
    try:
        expired_otps = OTP.objects.filter(expires_at__lt=timezone.now())
        count = expired_otps.count()
        expired_otps.delete()
        
        logger.info(f"Cleaned up {count} expired OTPs")
        return f"Cleaned up {count} expired OTPs"
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired OTPs: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.expire_coupons')
def expire_coupons(self):
    """Mark expired coupons as inactive."""
    try:
        expired_coupons = Coupon.objects.filter(
            status='active',
            end_date_time__lt=timezone.now()
        )
        
        count = expired_coupons.count()
        expired_coupons.update(status='expired')
        
        logger.info(f"Expired {count} coupons")
        return f"Expired {count} coupons"
        
    except Exception as e:
        logger.error(f"Failed to expire coupons: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)
@shared_task(bind=True, name='common.tasks.weekly_database_backup')
def weekly_database_backup(self):
    """Create weekly database backup with media files."""
    try:
        backup_dir = os.path.join(settings.BASE_DIR, 'backups', 'weekly')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create backup filename with timestamp
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"wedesignz_weekly_{timestamp}.tar.gz"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Database backup
        db_backup_path = os.path.join(backup_dir, f"database_{timestamp}.sql")
        db_settings = settings.DATABASES['default']
        if db_settings['ENGINE'] == 'django.db.backends.postgresql':
            import subprocess
            subprocess.run([
                'pg_dump',
                '-h', db_settings['HOST'],
                '-U', db_settings['USER'],
                '-d', db_settings['NAME'],
                '-f', db_backup_path
            ])
        
        # Media files backup
        media_backup_path = os.path.join(backup_dir, f"media_{timestamp}")
        if os.path.exists(settings.MEDIA_ROOT):
            shutil.copytree(settings.MEDIA_ROOT, media_backup_path)
        
        # Create compressed archive
        import tarfile
        with tarfile.open(backup_path, 'w:gz') as tar:
            tar.add(db_backup_path, arcname='database.sql')
            if os.path.exists(media_backup_path):
                tar.add(media_backup_path, arcname='media/')
        
        # Clean up temporary files
        if os.path.exists(db_backup_path):
            os.remove(db_backup_path)
        if os.path.exists(media_backup_path):
            shutil.rmtree(media_backup_path)
        
        # Clean up old weekly backups (keep only 2 weeks)
        old_backups = []
        for file in os.listdir(backup_dir):
            if file.startswith('wedesignz_weekly_'):
                file_path = os.path.join(backup_dir, file)
                file_time = os.path.getctime(file_path)
                if file_time < (timezone.now() - timedelta(weeks=2)).timestamp():
                    old_backups.append(file_path)
        
        for old_backup in old_backups:
            os.remove(old_backup)
        
        logger.info(f"Weekly backup created: {backup_filename}")
        return f"Weekly backup created: {backup_filename}"
        
    except Exception as e:
        logger.error(f"Failed to create weekly backup: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=2)


@shared_task(bind=True, name='common.tasks.mark_inactive_accounts_for_deletion')
def mark_inactive_accounts_for_deletion(self):
    """Mark deactivated accounts for deletion after 6 months."""
    try:
        # Find accounts that have been deactivated for 6 months
        deletion_date = timezone.now() - timedelta(days=180)
        inactive_users = User.objects.filter(
            is_active=False,
            last_login__lt=deletion_date
        )
        
        # Mark for deletion (you might want to add a field for this)
        count = inactive_users.count()
        # inactive_users.update(marked_for_deletion=True)  # Uncomment if you add this field
        
        logger.info(f"Marked {count} inactive accounts for deletion")
        return f"Marked {count} inactive accounts for deletion"
        
    except Exception as e:
        logger.error(f"Failed to mark inactive accounts for deletion: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.check_custom_order_sla')
def check_custom_order_sla(self, order_id):
    """
    Check if a specific custom order has exceeded its SLA deadline.
    This task is scheduled to run at the order's sla_deadline time.
    If the order is not completed by then, it will be marked as delayed.
    """
    try:
        order = CustomOrderRequest.objects.select_related('created_by').get(id=order_id)
        
        # Check if order is already completed or cancelled
        if order.status in ['completed', 'cancelled']:
            logger.info(f"Order {order_id} is already {order.status}, skipping SLA check")
            return f"Order {order_id} already {order.status}"
        
        # Check if SLA deadline has passed
        now = timezone.now()
        if now < order.sla_deadline:
            # This shouldn't happen, but if the task runs early, reschedule it
            logger.warning(f"Order {order_id} SLA check ran early. Rescheduling...")
            # Reschedule for the actual deadline
            check_custom_order_sla.apply_async(
                args=[order_id],
                eta=order.sla_deadline
            )
            return f"Rescheduled order {order_id} SLA check for {order.sla_deadline}"
        
        # Order has exceeded SLA deadline and is not completed
        # Mark as delayed
        order.status = 'delayed'
        order.save(update_fields=['status', 'updated_at'])
        
        logger.info(f"Order {order_id} marked as delayed - SLA deadline exceeded")
                
        # Send notification to customer
        if order.created_by and order.created_by.email:
            try:
                send_mail(
                    subject="Custom Order Delayed - WeDesignz",
                    message=f"Your custom order #{order_id} has exceeded the delivery time and has been marked as delayed. We apologize for the inconvenience and are working to complete it as soon as possible.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.created_by.email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f"Failed to send delay notification for order {order_id}: {str(e)}")
        
        return f"Order {order_id} marked as delayed"
        
    except CustomOrderRequest.DoesNotExist:
        logger.error(f"Order {order_id} not found for SLA check")
        return f"Order {order_id} not found"
    except Exception as e:
        logger.error(f"Failed to check SLA for order {order_id}: {str(e)}", exc_info=True)
        # Retry once after 5 minutes if there's an error
        raise self.retry(exc=e, countdown=300, max_retries=1)


@shared_task(bind=True, name='common.tasks.send_subscription_expiry_reminders')
def send_subscription_expiry_reminders(self):
    """Send reminders for subscriptions expiring soon."""
    try:
        # Find subscriptions expiring in 7 days
        expiry_date = timezone.now() + timedelta(days=7)
        expiring_subscriptions = Subscription.objects.filter(
            status='active',
            created_at__lte=expiry_date - timedelta(days=30)  # Assuming monthly subscriptions
        )
        
        reminded_count = 0
        for subscription in expiring_subscriptions:
            try:
                send_mail(
                    subject="Subscription Expiring Soon - WeDesignz",
                    message=f"Your {subscription.plan.get_plan_name_display()} subscription will expire in 7 days.\n\nTo continue enjoying premium features, please renew your subscription.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[subscription.created_by.email],
                    fail_silently=False,
                )
                reminded_count += 1
                
            except Exception as e:
                logger.error(f"Failed to send expiry reminder to {subscription.created_by.email}: {str(e)}")
        
        logger.info(f"Sent expiry reminders to {reminded_count} users")
        return f"Sent expiry reminders to {reminded_count} users"
        
    except Exception as e:
        logger.error(f"Failed to send subscription expiry reminders: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


# Additional utility tasks
@shared_task(bind=True, name='common.tasks.send_bulk_emails')
def send_bulk_emails(self, user_ids, subject, template, context):
    """Send bulk emails to specific users."""
    try:
        users = User.objects.filter(id__in=user_ids)
        success_count = 0
        
        for user in users:
            try:
                user_context = {**context, 'user': user, 'site_url': settings.SITE_URL}
                html_content = render_to_string(template, user_context)
                text_content = f"Check out our latest updates at {settings.SITE_URL}"
                
                msg = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [user.email])
                msg.attach_alternative(html_content, "text/html")
                msg.send()
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to send email to {user.email}: {str(e)}")
                continue
        
        logger.info(f"Bulk emails sent to {success_count}/{len(users)} users")
        return f"Bulk emails sent to {success_count}/{len(users)} users"
        
    except Exception as e:
        logger.error(f"Failed to send bulk emails: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.generate_reports')
def generate_reports(self, report_type, date_range):
    """Generate various reports."""
    try:
        # This would generate different types of reports
        # based on the report_type parameter
        logger.info(f"Generating {report_type} report for {date_range}")
        return f"Generated {report_type} report for {date_range}"
        
    except Exception as e:
        logger.error(f"Failed to generate reports: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


# ==================== DESIGNER CONSOLE TASKS ====================

@shared_task(bind=True, name='common.tasks.send_settlement_reminders')
def send_settlement_reminders(self):
    """Send daily settlement reminders during settlement window (days 5-10)."""
    try:
        from datetime import datetime
        import pytz
        
        # Get current date in Asia/Kolkata timezone
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        current_date = datetime.now(kolkata_tz)
        current_day = current_date.day
        
        # Check if we're in settlement window (days 5-10)
        if not (5 <= current_day <= 10):
            logger.info("Not in settlement window, skipping settlement reminders")
            return "Not in settlement window"
        
        # TODO: Get designers with pending settlements
        # pending_settlements = SettlementRequest.objects.filter(
        #     status='PENDING',
        #     created_at__date=current_date.date()
        # )
        
        # For now, get all active designers
        designers = User.objects.filter(
            is_active=True,
            created_designer_profiles__status='verified',
            created_designer_profiles__onboarding_completed=True
        ).distinct()
        
        reminded_count = 0
        for designer in designers:
            try:
                send_mail(
                    subject="Settlement Reminder - WeDesignz",
                    message=f"Hi {designer.first_name},\n\nThis is a reminder that your settlement window is open (days 5-10 of the month).\n\nPlease log in to your Designer Console to accept your settlement before the window closes.\n\nVisit {settings.SITE_URL}/designer-console to access your dashboard.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[designer.email],
                    fail_silently=False,
                )
                reminded_count += 1
                
            except Exception as e:
                logger.error(f"Failed to send settlement reminder to {designer.email}: {str(e)}")
        
        logger.info(f"Sent settlement reminders to {reminded_count} designers")
        return f"Sent settlement reminders to {reminded_count} designers"
        
    except Exception as e:
        logger.error(f"Failed to send settlement reminders: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.create_designer_payout_requests')
def create_designer_payout_requests(self):
    """Create settlement requests for designers on day 1 of each month."""
    try:
        from datetime import datetime, date, timedelta
        import pytz
        from decimal import Decimal
        from django.contrib.auth.models import User
        from Wallet.models import Wallet, SettlementRequest
        from Profiles.models import DesignerProfile
        from Authentication.user_relations import get_user_wallets
        
        # Get current date in Asia/Kolkata timezone
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        current_date = datetime.now(kolkata_tz).date()
        
        # Only run on day 1 of the month
        if current_date.day != 1:
            logger.info("Not the first day of the month, skipping settlement request creation")
            return "Not the first day of the month"
        
        # Calculate previous month period
        if current_date.month == 1:
            period_start = date(current_date.year - 1, 12, 1)
            # Get last day of December
            period_end = date(current_date.year - 1, 12, 31)
        else:
            period_start = date(current_date.year, current_date.month - 1, 1)
            # Get last day of previous month
            if current_date.month == 2:
                period_end = date(current_date.year, 1, 31)
            else:
                # Calculate last day of previous month
                first_day_current = date(current_date.year, current_date.month, 1)
                period_end = first_day_current - timedelta(days=1)
        
        # Get all active verified designers
        designers = User.objects.filter(
            is_active=True,
            created_designer_profiles__status='verified'
        ).distinct()
        
        created_count = 0
        skipped_count = 0
        
        for designer in designers:
            try:
                # Verify designer profile exists and is verified
                designer_profile = DesignerProfile.objects.filter(created_by=designer, status='verified').first()
                if not designer_profile:
                    skipped_count += 1
                    continue
                
                # Verify wallet exists
                wallets = get_user_wallets(designer)
                if not wallets.exists():
                    skipped_count += 1
                    continue
                
                # Calculate unsettled balance at period end from transactions (not current wallet balance)
                # This ensures we only include UNSETTLED transactions up to the end of previous month
                # and exclude any credits that happen on Day 1 of the new month
                # Previously settled transactions are excluded
                unsettled_balance = calculate_unsettled_balance(designer, period_end)
                
                if unsettled_balance <= 0:
                    skipped_count += 1
                    continue
                
                # Create settlement request (or get existing one)
                settlement_request, created = SettlementRequest.objects.get_or_create(
                    designer_id=designer.id,
                    settlement_period_start=period_start,
                    defaults={
                        'settlement_period_end': period_end,
                        'wallet_balance_at_period_end': unsettled_balance,
                        'settlement_amount': unsettled_balance,  # Settle full unsettled balance at period end
                        'status': 'pending'
                    }
                )
                
                if created:
                    # Link designer to settlement request
                    settlement_request.set_designer(designer)
                    created_count += 1
                    logger.info(f"Created settlement request for designer {designer.id}: ₹{unsettled_balance} (calculated from unsettled transactions up to {period_end})")
                    
                    # TODO: Send notification to designer about settlement window
                    # send_mail(
                    #     subject="Settlement Window Open - WeDesignz",
                    #     message=f"Hi {designer.first_name},\n\nYour settlement window is now open (Days 1-5 of the month).\n\nAvailable for settlement: ₹{unsettled_balance}\nPeriod: {period_start} to {period_end}\n\nPlease log in to accept your settlement.\n\nVisit {settings.SITE_URL}/designer-console to access your dashboard.",
                    #     from_email=settings.DEFAULT_FROM_EMAIL,
                    #     recipient_list=[designer.email],
                    #     fail_silently=False,
                    # )
                else:
                    # Update existing request if balance changed
                    if settlement_request.wallet_balance_at_period_end != unsettled_balance:
                        settlement_request.wallet_balance_at_period_end = unsettled_balance
                        settlement_request.settlement_amount = unsettled_balance
                        settlement_request.save()
                        logger.info(f"Updated settlement request for designer {designer.id}: ₹{unsettled_balance} (calculated from unsettled transactions up to {period_end})")
                    
            except Exception as e:
                logger.error(f"Failed to create settlement for designer {designer.id}: {str(e)}", exc_info=True)
                skipped_count += 1
        
        logger.info(f"Created {created_count} settlement requests, skipped {skipped_count} designers")
        return f"Created {created_count} settlement requests, skipped {skipped_count} designers"
        
    except Exception as e:
        logger.error(f"Failed to process monthly settlements: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.process_settlement_payouts')
def process_settlement_payouts(self):
    """
    Process all opted-in settlements on day 6 of each month.
    Deducts from wallet and marks settlements as 'processing' for manual payout.
    Admin will download settlement sheet and process payouts manually.
    """
    try:
        from datetime import datetime, date
        import pytz
        from decimal import Decimal
        from django.contrib.auth.models import User
        from Wallet.models import Wallet, SettlementRequest, WalletTransaction
        from Authentication.user_relations import get_user_wallets
        
        # Get current date in Asia/Kolkata timezone
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        current_date = datetime.now(kolkata_tz).date()
        
        # Only run on day 6
        if current_date.day != 6:
            logger.info("Not day 6, skipping settlement processing")
            return "Not day 6"
        
        # Get all opted-in settlement requests
        settlement_requests = SettlementRequest.objects.filter(
            status='opted_in',
            settlement_date__isnull=True  # Not yet processed
        )
        
        processed_count = 0
        failed_count = 0
        
        for settlement_request in settlement_requests:
            try:
                designer_id = settlement_request.designer_id
                
                # Get designer
                designer = User.objects.get(id=designer_id)
                
                # Get current wallet balance
                wallets = get_user_wallets(designer)
                wallet = wallets.first()
                
                if not wallet:
                    logger.error(f"No wallet found for designer {designer_id}")
                    settlement_request.status = 'failed'
                    settlement_request.failure_reason = 'Wallet not found'
                    settlement_request.save()
                    failed_count += 1
                    continue
                
                current_balance = Decimal(str(wallet.balance))
                settlement_amount = Decimal(str(settlement_request.settlement_amount))
                
                # Ensure we don't settle more than available
                if settlement_amount > current_balance:
                    settlement_amount = current_balance
                    logger.warning(f"Adjusting settlement amount for designer {designer_id}: {settlement_amount}")
                
                if settlement_amount <= 0:
                    logger.warning(f"Insufficient balance for designer {designer_id}")
                    settlement_request.status = 'failed'
                    settlement_request.failure_reason = 'Insufficient wallet balance'
                    settlement_request.save()
                    failed_count += 1
                    continue
                
                # Mark all unsettled credit transactions up to period_end as settled
                from datetime import time
                period_end_datetime = kolkata_tz.localize(
                    datetime.combine(settlement_request.settlement_period_end, time.max)
                )
                
                # Get all unsettled credit transactions up to period_end
                unsettled_credits = WalletTransaction.objects.filter(
                    created_by=designer,
                    wallet_transaction_type='credit',
                    created_at__lte=period_end_datetime,
                    settlement_request__isnull=True  # Only unsettled transactions
                )
                
                # Use database transaction to ensure atomicity
                # Only mark transactions as settled if all steps succeed
                try:
                    with transaction.atomic():
                        # Update settlement request to processing
                        settlement_request.status = 'processing'
                        settlement_request.settlement_date = current_date
                        settlement_request.save()
                        
                        # Mark all unsettled credit transactions up to period_end as settled
                        now = timezone.now()
                        unsettled_credits.update(
                            settlement_request=settlement_request,
                            settled_at=now
                        )
                        
                        # Deduct from wallet
                        wallet.balance = current_balance - settlement_amount
                        wallet.save()
                        
                        # Create debit transaction
                        debit_transaction = WalletTransaction.objects.create(
                            wallet_transaction_type='debit',
                            amount=settlement_amount,
                            description=f"Settlement for period {settlement_request.settlement_period_start} to {settlement_request.settlement_period_end}",
                            reference_id=f"settlement_{settlement_request.id}",
                            created_by=designer
                        )
                        wallet.attach_wallet_transaction(debit_transaction)
                    
                    # If we reach here, all operations succeeded
                    processed_count += 1
                    logger.info(f"Processed settlement for designer {designer_id}: ₹{settlement_amount} (marked for manual payout)")
                    
                except Exception as inner_e:
                    # If any step fails, transaction will rollback automatically
                    # But we need to mark settlement as failed
                    logger.error(f"Failed to process settlement {settlement_request.id} (transaction rolled back): {str(inner_e)}", exc_info=True)
                    settlement_request.status = 'failed'
                    settlement_request.failure_reason = f'Processing error: {str(inner_e)}'
                    settlement_request.save()
                    failed_count += 1
                    continue
                    
            except User.DoesNotExist:
                logger.error(f"Designer {settlement_request.designer_id} not found")
                settlement_request.status = 'failed'
                settlement_request.failure_reason = 'Designer not found'
                settlement_request.save()
                failed_count += 1
            except Exception as e:
                logger.error(f"Failed to process settlement {settlement_request.id}: {str(e)}", exc_info=True)
                # If settlement was marked as processing, unmark any transactions that were marked
                if settlement_request.status == 'processing':
                    try:
                        # Unmark transactions that were marked for this settlement
                        WalletTransaction.objects.filter(
                            settlement_request=settlement_request
                        ).update(
                            settlement_request=None,
                            settled_at=None
                        )
                        logger.info(f"Unmarked transactions for failed settlement {settlement_request.id}")
                    except Exception as unmark_error:
                        logger.error(f"Failed to unmark transactions for settlement {settlement_request.id}: {str(unmark_error)}")
                
                settlement_request.status = 'failed'
                settlement_request.failure_reason = f'Processing error: {str(e)}'
                settlement_request.save()
                failed_count += 1
        
        logger.info(f"Processed {processed_count} settlements, {failed_count} failed. Admin can download settlement sheet for manual payout.")
        return f"Processed {processed_count} settlements, {failed_count} failed"
        
    except Exception as e:
        logger.error(f"Failed to process settlement payouts: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.send_design_approval_reminders')
def send_design_approval_reminders(self):
    """Send reminders for designs pending approval for more than 24 hours."""
    try:
        from datetime import timedelta
        
        # Find designs pending approval for more than 24 hours
        cutoff_time = timezone.now() - timedelta(hours=24)
        pending_designs = Product.objects.filter(
            status='draft',
            created_at__lt=cutoff_time
        )
        
        reminded_count = 0
        for design in pending_designs:
            try:
                # Send reminder to admin
                send_mail(
                    subject=f"Design Approval Reminder #{design.id} - WeDesignz",
                    message=f"Design '{design.title}' by {design.created_by.username} has been pending approval for more than 24 hours.\n\nPlease review and process this design.\n\nPlatform ID: {design.product_number}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.ADMIN_EMAIL],
                    fail_silently=False,
                )
                reminded_count += 1
                
            except Exception as e:
                logger.error(f"Failed to send design approval reminder for design {design.id}: {str(e)}")
        
        logger.info(f"Sent design approval reminders for {reminded_count} designs")
        return f"Sent design approval reminders for {reminded_count} designs"
        
    except Exception as e:
        logger.error(f"Failed to send design approval reminders: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.send_designer_performance_reports')
def send_designer_performance_reports(self):
    """Send monthly performance reports to designers."""
    try:
        # Get all verified designers
        designers = User.objects.filter(
            is_active=True,
            created_designer_profiles__status='verified',
            created_designer_profiles__onboarding_completed=True
        ).distinct()
        
        reported_count = 0
        for designer in designers:
            try:
                # TODO: Calculate performance metrics
                # total_designs = Product.objects.filter(created_by=designer).count()
                # approved_designs = Product.objects.filter(created_by=designer, status='active').count()
                # total_earnings = WalletTransaction.objects.filter(created_by=designer, wallet_transaction_type='credit').aggregate(Sum('amount'))['total'] or 0
                
                send_mail(
                    subject="Monthly Performance Report - WeDesignz",
                    message=f"Hi {designer.first_name},\n\nHere's your monthly performance report:\n\n• Total Designs: 0\n• Approved Designs: 0\n• Total Earnings: ₹0\n• Performance Score: 0/100\n\nKeep up the great work!\n\nVisit {settings.SITE_URL}/designer-console for detailed analytics.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[designer.email],
                    fail_silently=False,
                )
                reported_count += 1
                
            except Exception as e:
                logger.error(f"Failed to send performance report to {designer.email}: {str(e)}")
        
        logger.info(f"Sent performance reports to {reported_count} designers")
        return f"Sent performance reports to {reported_count} designers"
        
    except Exception as e:
        logger.error(f"Failed to send designer performance reports: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.cleanup_expired_settlements')
def cleanup_expired_settlements(self):
    """Clean up expired settlement requests."""
    try:
        from datetime import datetime
        import pytz
        
        # Get current date in Asia/Kolkata timezone
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        current_date = datetime.now(kolkata_tz)
        
        # Only run on day 11 of the month (after settlement window closes)
        if current_date.day != 11:
            logger.info("Not day 11 of the month, skipping settlement cleanup")
            return "Not day 11 of the month"
        
        # TODO: Mark expired settlements as EXPIRED
        # expired_settlements = SettlementRequest.objects.filter(
        #     status='PENDING',
        #     created_at__date__lt=current_date.date()
        # )
        # 
        # count = expired_settlements.count()
        # expired_settlements.update(status='EXPIRED')
        
        logger.info("Expired settlements cleanup completed")
        return "Expired settlements cleanup completed"
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired settlements: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.expire_processing_settlements')
def expire_processing_settlements(self):
    """
    Mark settlements as expired if they've been in 'processing' status 
    for more than 7 days without being completed.
    
    This task:
    1. Finds settlements in 'processing' status for more than 7 days
    2. Unmarks transactions (makes them available for future settlements)
    3. Refunds wallet balance (reverses the debit transaction)
    4. Marks settlement as 'expired'
    
    Runs daily to ensure settlements don't stay in processing forever.
    """
    try:
        from datetime import timedelta
        from decimal import Decimal
        from django.contrib.auth.models import User
        from Wallet.models import SettlementRequest, WalletTransaction, Wallet
        from Authentication.user_relations import get_user_wallets
        
        # Get settlements in 'processing' status for more than 7 days
        cutoff_date = timezone.now() - timedelta(days=7)
        
        expired_settlements = SettlementRequest.objects.filter(
            status='processing',
            settlement_date__lte=cutoff_date.date()
        )
        
        expired_count = 0
        refunded_count = 0
        error_count = 0
        
        for settlement in expired_settlements:
            try:
                designer_id = settlement.designer_id
                
                # Get designer
                try:
                    designer = User.objects.get(id=designer_id)
                except User.DoesNotExist:
                    logger.error(f"Designer {designer_id} not found for settlement {settlement.id}")
                    settlement.status = 'expired'
                    settlement.failure_reason = 'Designer not found - settlement expired'
                    settlement.save()
                    error_count += 1
                    continue
                
                # Get wallet
                wallets = get_user_wallets(designer)
                wallet = wallets.first()
                
                if not wallet:
                    logger.error(f"No wallet found for designer {designer_id} in settlement {settlement.id}")
                    settlement.status = 'expired'
                    settlement.failure_reason = 'Wallet not found - settlement expired'
                    settlement.save()
                    error_count += 1
                    continue
                
                # Use database transaction to ensure atomicity
                with transaction.atomic():
                    # Get all transactions for this settlement
                    settlement_transactions = WalletTransaction.objects.filter(
                        settlement_request=settlement
                    )
                    
                    # Find the debit transaction (settlement deduction)
                    debit_transaction = settlement_transactions.filter(
                        wallet_transaction_type='debit',
                        reference_id=f"settlement_{settlement.id}"
                    ).first()
                    
                    # Refund the amount back to wallet if debit transaction exists
                    if debit_transaction:
                        refund_amount = Decimal(str(debit_transaction.amount))
                        current_balance = Decimal(str(wallet.balance))
                        wallet.balance = current_balance + refund_amount
                        wallet.save()
                        refunded_count += 1
                        logger.info(f"Refunded ₹{refund_amount} to wallet for expired settlement {settlement.id}")
                    
                    # Unmark credit transactions (make them available for future settlements)
                    credit_transactions = settlement_transactions.filter(
                        wallet_transaction_type='credit'
                    )
                    unmarked_count = credit_transactions.update(
                        settlement_request=None,
                        settled_at=None
                    )
                    
                    if unmarked_count > 0:
                        logger.info(f"Unmarked {unmarked_count} credit transactions for expired settlement {settlement.id}")
                    
                    # Mark settlement as expired
                    settlement.status = 'expired'
                    settlement.failure_reason = 'Settlement expired - not completed within 7 days of processing'
                    settlement.save()
                    
                    expired_count += 1
                    logger.info(f"Expired settlement {settlement.id} for designer {designer_id} (₹{settlement.settlement_amount})")
                    
            except Exception as e:
                logger.error(f"Failed to expire settlement {settlement.id}: {str(e)}", exc_info=True)
                error_count += 1
                # Mark as expired even if refund fails
                try:
                    settlement.status = 'expired'
                    settlement.failure_reason = f'Settlement expired - error during expiration: {str(e)}'
                    settlement.save()
                except:
                    pass
        
        logger.info(f"Expired {expired_count} settlements, refunded {refunded_count} wallets, {error_count} errors")
        return f"Expired {expired_count} settlements, refunded {refunded_count} wallets, {error_count} errors"
        
    except Exception as e:
        logger.error(f"Failed to expire processing settlements: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)


# ==================== ORDER TASKS ====================

@shared_task(bind=True, name='common.tasks.send_order_confirmation_email_async')
def send_order_confirmation_email_async(self, order_id):
    """Send order confirmation email asynchronously when order status is success."""
    try:
        order = Order.objects.select_related('created_by').get(id=order_id)
        
        if order.status != 'success':
            logger.warning(f"Order {order_id} is not in success status, skipping email")
            return f"Order {order_id} is not in success status"
        
        # Get order items from product_ids
        order_items = []
        if order.product_ids:
            try:
                product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
                products = Product.objects.filter(id__in=product_ids)
                order_items = [{'product': product} for product in products]
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse product_ids for order {order_id}: {str(e)}")
        
        # Send email
        EmailService.send_order_confirmation_email(order.created_by, order, order_items)
        logger.info(f"Order confirmation email sent for order {order_id}")
        return f"Order confirmation email sent for order {order_id}"
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
        return f"Order {order_id} not found"
    except Exception as e:
        logger.error(f"Failed to send order confirmation email for order {order_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.send_customer_invoice_email_async')
def send_customer_invoice_email_async(self, invoice_id, order_id):
    """Send customer invoice email asynchronously."""
    try:
        invoice = Invoice.objects.select_related('user', 'order').get(id=invoice_id)
        order = Order.objects.select_related('created_by').get(id=order_id)
        
        # Get products for invoice items
        products = []
        if order.product_ids:
            try:
                product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
                products = Product.objects.filter(id__in=product_ids)
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse product_ids for order {order_id}: {str(e)}")
        
        # Send email
        EmailService.send_customer_invoice_email(invoice, order, products)
        logger.info(f"Customer invoice email sent for invoice {invoice_id}")
        return f"Customer invoice email sent for invoice {invoice_id}"
        
    except Invoice.DoesNotExist:
        logger.error(f"Invoice {invoice_id} not found")
        return f"Invoice {invoice_id} not found"
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
        return f"Order {order_id} not found"
    except Exception as e:
        logger.error(f"Failed to send customer invoice email for invoice {invoice_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.send_settlement_receipt_email_async')
def send_settlement_receipt_email_async(self, settlement_id):
    """Send settlement receipt email asynchronously."""
    try:
        from Wallet.models import SettlementRequest
        from Orders.invoice_service import create_settlement_receipt
        
        settlement = SettlementRequest.objects.select_related().get(id=settlement_id)
        
        # Create receipt
        invoice = create_settlement_receipt(settlement)
        
        # Send email
        EmailService.send_settlement_receipt_email(invoice, settlement)
        logger.info(f"Settlement receipt email sent for settlement {settlement_id}")
        return f"Settlement receipt email sent for settlement {settlement_id}"
        
    except SettlementRequest.DoesNotExist:
        logger.error(f"Settlement {settlement_id} not found")
        return f"Settlement {settlement_id} not found"
    except Exception as e:
        logger.error(f"Failed to send settlement receipt email for settlement {settlement_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.process_subscription_billing')
def process_subscription_billing(self):
    """
    Process subscription billing cycles:
    - Monthly subscriptions: When 30-day period ends
    - Annual subscriptions: Monthly based on purchase date (purchase_date + 30*N days)
      Example: Purchased March 14 → Settles April 14, May 14, June 14, etc.
    Creates designer invoices based on subscription downloads.
    Runs daily to check for subscriptions that need billing processing.
    """
    from datetime import timedelta, date
    from Orders.invoice_service import process_subscription_settlement, process_monthly_subscription_settlement
    
    try:
        now = timezone.now()
        today = now.date()
        
        processed_count = 0
        
        # ========== MONTHLY SUBSCRIPTIONS ==========
        # Process monthly subscriptions when their 30-day period ends
        monthly_subscriptions = Subscription.objects.filter(
            status='active',
            plan__plan_duration='monthly',
            settlement_processed=False
        )
        
        for subscription in monthly_subscriptions:
            # Calculate period end date (30 days from creation)
            period_end = subscription.created_at + timedelta(days=30)
            period_end_date = period_end.date()
            
            # Check if subscription period has ended
            if today >= period_end_date:
                try:
                    # Process settlement
                    result = process_subscription_settlement(subscription)
                    # Note: process_subscription_settlement already marks as expired and settlement_processed
                    
                    processed_count += 1
                    logger.info(f"Processed monthly subscription settlement for subscription {subscription.id}: {result.get('total_downloads', 0)} downloads, {result.get('price_per_download', 0):.2f} per download. Designer invoices will be created when designers opt-in.")
                    
                except Exception as e:
                    logger.error(f"Failed to process monthly subscription {subscription.id}: {str(e)}", exc_info=True)
        
        # ========== ANNUAL SUBSCRIPTIONS ==========
        # Process annual subscriptions monthly based on purchase date + 30 days
        # Example: Purchased March 14 → Settles April 14, May 14, June 14, etc.
        annual_subscriptions = Subscription.objects.filter(
            status='active',
            plan__plan_duration='annually'
        )
        
        for subscription in annual_subscriptions:
            subscription_start = subscription.created_at.date()
            subscription_end = subscription_start + timedelta(days=365)
            
            # Skip if subscription hasn't started or has expired
            if today < subscription_start or today >= subscription_end:
                continue
            
            # Calculate next settlement date
            if subscription.last_settled_month:
                # Next settlement is 30 days after last settlement
                next_settlement_date = subscription.last_settled_month + timedelta(days=30)
            else:
                # First settlement is 30 days after purchase
                next_settlement_date = subscription_start + timedelta(days=30)
            
            # Check if it's time to settle (today >= next_settlement_date)
            if today >= next_settlement_date:
                # Calculate settlement period
                if subscription.last_settled_month:
                    # Period starts from day after last settlement
                    period_start = subscription.last_settled_month + timedelta(days=1)
                else:
                    # First period starts from subscription start
                    period_start = subscription_start
                
                # Period ends on settlement date (or today if today is before next_settlement_date)
                period_end = min(next_settlement_date, today)
                
                # Ensure period doesn't exceed subscription end
                if period_end > subscription_end:
                    period_end = subscription_end
                
                # Ensure period_start doesn't exceed period_end after adjustments
                if period_start >= period_end:
                    # Skip this period if it's invalid
                    continue
                
                # Only process if period is valid
                if period_start < period_end:
                    try:
                        # Process monthly settlement for this period
                        result = process_monthly_subscription_settlement(
                            subscription, 
                            period_start, 
                            period_end
                        )
                        
                        # Check if no downloads were used (no settlement)
                        if result.get('total_downloads_used', 0) == 0:
                            # Still update last_settled_month to skip this period
                            subscription.last_settled_month = period_end
                            subscription.save()
                            logger.info(f"Skipped settlement for subscription {subscription.id} - {period_start} to {period_end}: No downloads used")
                        else:
                            processed_count += 1
                            logger.info(f"Processed monthly settlement for annual subscription {subscription.id} - {period_start} to {period_end}: {result.get('total_downloads_used', 0)} used, {result.get('total_downloads_settled', 0)} settled")
                    
                    except Exception as e:
                        logger.error(f"Failed to process monthly settlement for annual subscription {subscription.id} - {period_start} to {period_end}: {str(e)}", exc_info=True)
        
        # Check if annual subscriptions have fully expired (365 days passed)
        annual_expired = Subscription.objects.filter(
            status='active',
            plan__plan_duration='annually',
            created_at__lte=now - timedelta(days=365)
        )
        
        for subscription in annual_expired:
            expiry_date = subscription.created_at + timedelta(days=365)
            if expiry_date.date() <= today:
                subscription.status = 'expired'
                subscription.save()
                logger.info(f"Marked annual subscription {subscription.id} as expired")
        
        logger.info(f"Processed {processed_count} subscription settlements")
        return f"Processed {processed_count} subscription settlements"
        
    except Exception as e:
        logger.error(f"Failed to process expired subscriptions: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.send_design_rejection_email_async')
def send_design_rejection_email_async(self, product_id, rejection_reason=None):
    """Send email notification to designer when their design is rejected, asynchronously."""
    try:
        from Catalog.models import Product
        from django.contrib.auth.models import User
        
        # Get the product with related user
        try:
            product = Product.objects.select_related('created_by', 'category').get(id=product_id)
        except Product.DoesNotExist:
            logger.error(f"Product {product_id} not found for rejection email")
            return f"Product {product_id} not found"
        
        # Get the designer (user who created the design)
        designer = product.created_by
        if not designer or not designer.email:
            logger.warning(f"Designer or email not found for product {product_id}")
            return f"Designer or email not found for product {product_id}"
        
        # Send rejection email using EmailService
        try:
            EmailService.send_design_rejected_email(
                user=designer,
                design=product,
                feedback_message=rejection_reason
            )
            logger.info(f"Design rejection email sent successfully to {designer.email} for product {product_id}")
            return f"Rejection email sent to {designer.email}"
        except Exception as e:
            logger.error(f"Failed to send design rejection email to {designer.email} for product {product_id}: {str(e)}", exc_info=True)
            raise self.retry(exc=e, countdown=60, max_retries=3)
            
    except Exception as e:
        logger.error(f"Error in send_design_rejection_email_async for product {product_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.send_design_sale_notification_async')
def send_design_sale_notification_async(self, order_id):
    """Send notification to designer when their design is sold, asynchronously."""
    try:
        order = Order.objects.select_related('created_by').get(id=order_id)
        
        if order.status != 'success':
            logger.warning(f"Order {order_id} is not in success status, skipping notification")
            return f"Order {order_id} is not in success status"
        
        # Get designers who have products in this order
        designers_to_notify = set()
        if order.product_ids:
            try:
                product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
                products = Product.objects.select_related('created_by').filter(id__in=product_ids)
                for product in products:
                    if product.created_by and product.created_by != order.created_by:
                        designers_to_notify.add(product.created_by)
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to parse product_ids for order {order_id}: {str(e)}")
        
        # Send notification to each designer
        notified_count = 0
        for designer in designers_to_notify:
            try:
                from django.core.mail import send_mail
                send_mail(
                    subject="Design Sale Notification - WeDesignz",
                    message=f"Congratulations! Your design has been purchased.\n\nOrder ID: #{order.id}\nAmount: ₹{order.total_amount}\n\nKeep creating amazing designs!",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[designer.email],
                    fail_silently=False,
                )
                notified_count += 1
            except Exception as e:
                logger.error(f"Failed to send design sale notification to {designer.email} for order {order_id}: {str(e)}")
        
        logger.info(f"Design sale notifications sent for order {order_id} to {notified_count} designers")
        return f"Design sale notifications sent for order {order_id} to {notified_count} designers"
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
        return f"Order {order_id} not found"
    except Exception as e:
        logger.error(f"Failed to send design sale notification for order {order_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.delete_cart_items_async')
def delete_cart_items_async(self, order_id, user_id):
    """Delete cart items for products in the order after successful payment, asynchronously."""
    try:
        order = Order.objects.get(id=order_id)
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id)
        
        if not order or not order.product_ids:
            logger.info(f"No product_ids for order {order_id}, skipping cart deletion")
            return f"No product_ids for order {order_id}"
        
        # Parse product_ids from comma-separated string
        product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
        
        if product_ids:
            # Delete cart items for these products
            deleted_count = Cart.objects.filter(
                created_by=user,
                cart_type='cart',
                product_id__in=product_ids
            ).delete()[0]
            logger.info(f"Deleted {deleted_count} cart items for order {order_id}")
            return f"Deleted {deleted_count} cart items for order {order_id}"
        else:
            logger.info(f"No valid product_ids for order {order_id}")
            return f"No valid product_ids for order {order_id}"
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for cart deletion")
        return f"Order {order_id} not found"
    except Exception as e:
        logger.error(f"Failed to delete cart items for order {order_id}: {str(e)}")
        # Don't retry cart deletion failures as they're not critical
        return f"Failed to delete cart items for order {order_id}: {str(e)}"


# ==================== NOTIFICATION TASKS ====================

@shared_task(bind=True, name='common.tasks.send_scheduled_notification')
def send_scheduled_notification(self, campaign_id, title, message, priority, send_to_designers, send_to_customers, delivery_method='both'):
    """
    Send scheduled notification to recipients.
    
    Note: In-app notifications are ALWAYS created regardless of delivery_method.
    delivery_method only controls whether emails are sent:
    - 'in_app': Create notifications only (no email)
    - 'email': Create notifications + send email
    - 'both': Create notifications + send email (same as 'email')
    """
    try:
        import logging
        from django.utils import timezone
        logger = logging.getLogger(__name__)
        logger.info(f"📬 Scheduled notification - Campaign ID: {campaign_id}, Delivery method: {delivery_method}, Send to designers: {send_to_designers}, Send to customers: {send_to_customers}")
        from django.contrib.auth.models import User
        from CoreAdmin.models import DesignerNotification, CustomerNotification, AdminNotificationCampaign
        from django.db import transaction
        
        notification_ids = []
        designers_count = 0
        customers_count = 0
        
        with transaction.atomic():
            # Send to designers
            if send_to_designers:
                # Get verified designers who have completed onboarding
                designers = User.objects.filter(
                    created_designer_profiles__status='verified',
                    created_designer_profiles__onboarding_completed=True,
                    is_active=True
                ).distinct()
                
                for designer in designers:
                    notification = DesignerNotification.objects.create(
                        designer_id=designer.id,
                        notification_type='system_update',
                        title=title,
                        message=message,
                        priority=priority
                    )
                    notification.set_designer(designer)
                    notification_ids.append(notification.id)
                    designers_count += 1
                    
                    # Send email only if deliveryMethod is 'email' or 'both'
                    if delivery_method in ['email', 'both']:
                        send_notification_email.delay(
                            'designer',
                            designer.id,
                            notification.id
                        )
            
            # Send to customers
            if send_to_customers:
                # Get ALL active users as customers (including verified designers)
                # Users who are both designers and customers will receive notifications in both dashboards
                customers = User.objects.filter(
                    is_active=True
                ).distinct()
                
                for customer in customers:
                    notification = CustomerNotification.objects.create(
                        customer_id=customer.id,
                        notification_type='system_update',
                        title=title,
                        message=message,
                        priority=priority
                    )
                    notification.set_customer(customer)
                    notification_ids.append(notification.id)
                    customers_count += 1
                    
                    # Send email only if deliveryMethod is 'email' or 'both'
                    if delivery_method in ['email', 'both']:
                        send_notification_email.delay(
                            'customer',
                            customer.id,
                            notification.id
                        )
            
            # Update campaign status
            try:
                campaign = AdminNotificationCampaign.objects.get(id=campaign_id)
                campaign.mark_as_sent(
                    total_recipients=len(notification_ids),
                    designers_count=designers_count,
                    customers_count=customers_count
                )
            except AdminNotificationCampaign.DoesNotExist:
                logger.warning(f"Campaign {campaign_id} not found when updating status")
        
        # Log the result with delivery method details
        emails_will_be_sent = delivery_method in ['email', 'both']
        logger.info(f"✅ Scheduled notification completed: Created {len(notification_ids)} in-app notifications | Delivery method: {delivery_method} | Emails will be sent: {emails_will_be_sent}")
        return f"Notification sent to {len(notification_ids)} recipients"
        
    except Exception as e:
        logger.error(f"Failed to send scheduled notification: {str(e)}", exc_info=True)
        # Mark campaign as failed if it exists
        try:
            from CoreAdmin.models import AdminNotificationCampaign
            campaign = AdminNotificationCampaign.objects.get(id=campaign_id)
            campaign.status = 'failed'
            campaign.save()
        except:
            pass
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.send_notification_email')
def send_notification_email(self, user_type, user_id, notification_id):
    """Send email for a notification."""
    try:
        from django.contrib.auth.models import User
        from CoreAdmin.models import DesignerNotification, CustomerNotification
        from django.core.mail import send_mail
        
        user = User.objects.get(id=user_id)
        
        if user_type == 'designer':
            notification = DesignerNotification.objects.get(id=notification_id)
        else:
            notification = CustomerNotification.objects.get(id=notification_id)
        
        # Send email
        send_mail(
            subject=notification.title,
            message=notification.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        # Update email sent status
        notification.email_sent = True
        notification.email_sent_at = timezone.now()
        notification.save()
        
        logger.info(f"Email sent to {user.email} for notification {notification_id}")
        return f"Email sent to {user.email}"
        
    except Exception as e:
        logger.error(f"Failed to send notification email to user {user_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)


# ==================== INSTAGRAM TASKS ====================

@shared_task(
    bind=True, 
    max_retries=3,
    name='common.tasks.post_to_instagram'
)
def post_to_instagram(self, instagram_post_id):
    """
    Post to Instagram asynchronously.
    Updates InstagramPost record with result.
    """
    import logging
    import os
    import requests
    logger = logging.getLogger(__name__)
    
    logger.info(f"=== TASK STARTED: Instagram post task for post ID: {instagram_post_id} ===")
    logger.info(f"Task ID: {self.request.id}, Retry: {self.request.retries}/{self.max_retries}")
    
    try:
        from django.conf import settings
        from .models import InstagramPost, InstagramIntegration
        from Catalog.models import Product
        
        # Get the InstagramPost record
        try:
            instagram_post = InstagramPost.objects.get(id=instagram_post_id)
            logger.info(f"Found InstagramPost {instagram_post_id}: status={instagram_post.status}, type={instagram_post.post_type}, media_type={instagram_post.media_type}")
        except InstagramPost.DoesNotExist:
            logger.error(f"InstagramPost {instagram_post_id} not found in database")
            return
        
        # Check if already successfully processed
        if instagram_post.status == 'success':
            logger.info(f"Post {instagram_post_id} already successful. Skipping.")
            return
        
        # Mark as processing immediately
        try:
            instagram_post.mark_processing()
            logger.info(f"Post {instagram_post_id} marked as processing")
        except Exception as e:
            logger.error(f"Failed to mark post {instagram_post_id} as processing: {str(e)}", exc_info=True)
            # Continue anyway - don't fail the task just because status update failed
        
        # Check if Instagram is enabled
        integration = InstagramIntegration.get_instance()
        if not integration.is_enabled:
            logger.warning(f"Instagram integration is disabled for post {instagram_post_id}")
            instagram_post.mark_failed("Instagram integration is disabled")
            return
        
        if not integration.access_token:
            logger.warning(f"Instagram access token not configured for post {instagram_post_id}")
            instagram_post.mark_failed("Instagram access token not configured")
            return
        
        if not integration.is_token_valid():
            logger.warning(f"Instagram access token expired for post {instagram_post_id}")
            instagram_post.mark_failed("Instagram access token expired")
            return
        
        # Get the product
        try:
            product = instagram_post.product
        except Product.DoesNotExist:
            logger.error(f"Product not found for InstagramPost {instagram_post_id}")
            instagram_post.mark_failed("Product not found")
            return
        
        logger.info(f"Processing post {instagram_post_id} for product {product.id} ({product.title})")
        
        # Initialize Instagram service
        try:
            from .instagram_service import InstagramService
            instagram_service = InstagramService()
        except Exception as e:
            error_msg = f"Instagram service initialization failed: {str(e)}"
            logger.error(f"Post {instagram_post_id}: {error_msg}", exc_info=True)
            instagram_post.mark_failed(error_msg)
            return
        
        # Get all image media files for the product
        media_files = product.get_media().filter(media_type='image')
        
        if not media_files.exists():
            logger.warning(f"No image media found for product {product.id}")
            instagram_post.mark_failed("No image media found for product")
            return
        
        # Find the appropriate image based on media_type preference
        # Priority: mockup > requested type (png/jpg) > any available image
        image_media = None
        requested_type = instagram_post.media_type.lower()
        
        # First pass: collect all valid images (exclude CDR/EPS)
        mockup_media = None
        png_media = None
        jpg_media = None
        
        for media in media_files:
            if not media.file:
                continue
            
            try:
                file_name = media.file.name.lower()
            except (AttributeError, ValueError):
                continue
            
            # Skip CDR and EPS files
            if file_name.endswith(('.cdr', '.eps')):
                continue
            
            # Only process image files
            if not file_name.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                continue
            
            # Check if it's a mockup
            base_name = os.path.splitext(os.path.basename(file_name))[0]
            is_mockup = base_name == 'mockup'
            
            # Also check metadata
            if not is_mockup:
                try:
                    from MediaFiles.models import Relation
                    relation = Relation.objects.filter(
                        relation_type='Product:Media',
                        id_1=product.pk,
                        id_2=media.pk
                    ).first()
                    if relation and relation.meta and 'mockup' in str(relation.meta).lower():
                        is_mockup = True
                except Exception:
                    pass
            
            # Categorize
            if is_mockup and not mockup_media:
                mockup_media = media
            elif file_name.endswith('.png') and not png_media:
                png_media = media
            elif file_name.endswith(('.jpg', '.jpeg')) and not jpg_media:
                jpg_media = media
        
        # Select image based on priority
        # First, respect the user's requested type
        if requested_type == 'jpg' and jpg_media:
            image_media = jpg_media
            logger.info(f"Selected JPG image for product {product.id} (as requested)")
        elif requested_type == 'png' and png_media:
            image_media = png_media
            logger.info(f"Selected PNG image for product {product.id} (as requested)")
        elif requested_type == 'mockup' and mockup_media:
            image_media = mockup_media
            logger.info(f"Selected mockup image for product {product.id} (as requested)")
        # Fallback: use whatever is available (mockup > png > jpg)
        elif mockup_media:
            image_media = mockup_media
            logger.info(f"Selected mockup image for product {product.id} (fallback)")
        elif png_media:
            image_media = png_media
            logger.info(f"Selected PNG image for product {product.id} (fallback)")
        elif jpg_media:
            image_media = jpg_media
            logger.info(f"Selected JPG image for product {product.id} (fallback)")
        
        if not image_media:
            error_msg = "No valid image found. Product must have at least one mockup, PNG, or JPG image file."
            logger.warning(f"Post {instagram_post_id}: {error_msg}")
            instagram_post.mark_failed(error_msg)
            return
        
        logger.info(f"Selected image media ID: {image_media.id} for post {instagram_post_id}")
        
        # Get image URL
        try:
            image_url = image_media.file.url
        except Exception as e:
            error_msg = f"Error getting image URL: {str(e)}"
            logger.error(f"Post {instagram_post_id}: {error_msg}", exc_info=True)
            instagram_post.mark_failed(error_msg)
            return
        
        if not image_url:
            error_msg = "Image URL not available"
            logger.warning(f"Post {instagram_post_id}: {error_msg}")
            instagram_post.mark_failed(error_msg)
            return
        
        # Normalize URL to absolute HTTPS
        image_url = str(image_url).strip()
        
        if image_url.startswith('/'):
            media_domain = getattr(settings, 'MEDIA_DOMAIN', 'devapi.wedesignz.com').rstrip('/')
            image_url = f"https://{media_domain}/{image_url.lstrip('/')}"
        elif not image_url.startswith(('http://', 'https://')):
            media_domain = getattr(settings, 'MEDIA_DOMAIN', 'devapi.wedesignz.com').rstrip('/')
            image_url = f"https://{media_domain}/{image_url.lstrip('/')}"
        elif image_url.startswith('http://'):
            image_url = image_url.replace('http://', 'https://', 1)
        
        if not image_url.startswith('https://'):
            error_msg = f"Invalid image URL format (must be HTTPS): {image_url[:100]}"
            logger.error(f"Post {instagram_post_id}: {error_msg}")
            instagram_post.mark_failed(error_msg)
            return
        
        logger.info(f"Using image URL: {image_url[:100]}...")
        
        # Validate URL is accessible
        try:
            logger.info(f"Validating image URL accessibility...")
            validation_response = requests.head(image_url, timeout=10, allow_redirects=True)
            validation_response.raise_for_status()
            
            content_type = validation_response.headers.get('Content-Type', '').lower()
            if not content_type.startswith('image/'):
                error_msg = f"URL does not point to an image. Content-Type: {content_type}"
                logger.error(f"Post {instagram_post_id}: {error_msg}")
                instagram_post.mark_failed(error_msg)
                return
            
            logger.info(f"Image URL validated. Content-Type: {content_type}, Status: {validation_response.status_code}")
        except requests.exceptions.RequestException as e:
            error_msg = f"Image URL is not accessible: {str(e)}"
            logger.error(f"Post {instagram_post_id}: {error_msg}")
            instagram_post.mark_failed(error_msg)
            return
        
        # Post to Instagram
        is_story = instagram_post.post_type == 'story'
        logger.info(f"Posting to Instagram (type: {'story' if is_story else 'post'})...")
        
        result = instagram_service.create_and_publish_post(
            image_url=image_url,
            caption=instagram_post.caption or '',
            is_story=is_story
        )
        
        # Handle result
        if result and result.get('success') and result.get('data') and result['data'].get('id'):
            post_data = result['data']
            instagram_post.mark_success(
                media_id=post_data.get('media_id'),
                post_id=post_data.get('id'),
                post_url=post_data.get('url')
            )
            logger.info(f"=== SUCCESS: Post {instagram_post_id} published. Instagram Post ID: {post_data.get('id')} ===")
        else:
            error_msg = result.get('error', 'Unknown error') if result else 'Instagram service returned no result'
            if result and result.get('step'):
                error_msg = f"Failed at {result.get('step')} step: {error_msg}"
            logger.error(f"=== FAILED: Post {instagram_post_id}: {error_msg} ===")
            instagram_post.mark_failed(error_msg)
            
    except Exception as e:
        logger.error(f"=== ERROR: Post {instagram_post_id} exception: {str(e)} ===", exc_info=True)
        try:
            instagram_post = InstagramPost.objects.get(id=instagram_post_id)
            instagram_post.mark_failed(f"Error: {str(e)}")
        except Exception:
            pass
        
        # Retry if not exceeded max retries
        if self.request.retries < self.max_retries:
            retry_countdown = 60 * (self.request.retries + 1)
            logger.info(f"Retrying post {instagram_post_id} in {retry_countdown} seconds (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=retry_countdown)


# ==================== PINTEREST TASKS ====================

@shared_task(bind=True, max_retries=3)
def post_design_to_pinterest(self, pinterest_post_id, base_url=None):
    """
    Post a design to Pinterest after approval.
    Posts both mockup.avif and design_JPG.avif as separate pins.
    This runs asynchronously so it doesn't block the approval process.
    Updates PinterestPost record with result.
    """
    import logging
    import os
    logger = logging.getLogger(__name__)
    
    try:
        from django.conf import settings
        from .models import PinterestPost, PinterestIntegration
        from Catalog.models import Product
        
        # Check if Pinterest is enabled
        integration = PinterestIntegration.get_instance()
        if not integration.is_enabled:
            logger.debug("Pinterest integration is disabled")
            pinterest_post = PinterestPost.objects.get(id=pinterest_post_id)
            pinterest_post.mark_failed("Pinterest integration is disabled")
            return
        
        # Get the PinterestPost record
        try:
            pinterest_post = PinterestPost.objects.get(id=pinterest_post_id)
        except PinterestPost.DoesNotExist:
            logger.error(f"PinterestPost {pinterest_post_id} not found")
            return
        
        # Get the product
        try:
            product = pinterest_post.product
        except Product.DoesNotExist:
            logger.error(f"Product not found for PinterestPost {pinterest_post_id}")
            pinterest_post.mark_failed("Product not found")
            return
        
        # Check if Pinterest is configured
        try:
            from .pinterest_service import PinterestService
            pinterest_service = PinterestService()
        except Exception as e:
            error_msg = f"Pinterest not configured: {str(e)}"
            logger.warning(error_msg)
            pinterest_post.mark_failed(error_msg)
            return
        
        # Get media files (images)
        media_files = product.get_media().filter(media_type='image')
        
        if not media_files.exists():
            logger.warning(f"No image media found for product {product.id}")
            pinterest_post.mark_failed("No image media found for product")
            return
        
        # Find mockup.avif and design_JPG.avif
        mockup_avif = None
        design_jpg_avif = None
        
        for media in media_files:
            if not media.file:
                continue
            
            file_name = media.file.name.lower()
            base_name = os.path.splitext(os.path.basename(file_name))[0]
            
            # Check for AVIF files
            if file_name.endswith('.avif'):
                # Check for mockup.avif (could be mockup.avif or {product_number}_MOCKUP.avif)
                if 'mockup' in base_name.lower() or base_name.endswith('_mockup'):
                    mockup_avif = media
                    logger.debug(f"Found mockup AVIF: {file_name}")
                # Check for design_JPG.avif (could be design_JPG.avif or {product_number}_JPG.avif)
                elif '_jpg' in base_name.lower() or base_name.endswith('_jpg'):
                    design_jpg_avif = media
                    logger.debug(f"Found design JPG AVIF: {file_name}")
        
        # Need at least one image to post
        if not mockup_avif and not design_jpg_avif:
            logger.warning(f"No AVIF images found for product {product.id} (need mockup.avif or design_JPG.avif)")
            pinterest_post.mark_failed("No AVIF images (mockup.avif or design_JPG.avif) found")
            return
        
        # Build base URL for media files
        # Pinterest requires HTTPS and publicly accessible URLs (no localhost)
        # Always use MEDIA_DOMAIN from settings (where media files are actually hosted)
        media_domain = getattr(settings, 'MEDIA_DOMAIN', 'devapi.wedesignz.com')
        if not media_domain.startswith('http'):
            media_domain = f"https://{media_domain}"
        
        # Validate media domain - must be HTTPS and not localhost
        if not (media_domain.startswith('https://') and 'localhost' not in media_domain.lower() and '127.0.0.1' not in media_domain):
            error_msg = f"Invalid media domain for Pinterest: {media_domain}. Pinterest requires publicly accessible HTTPS URLs."
            logger.error(error_msg)
            pinterest_post.mark_failed(error_msg)
            return
        
        # Prepare pin details
        base_title = product.title[:100] if product.title else "Design"  # Pinterest limit
        description = product.description[:800] if product.description else ""
        
        # Add design number if available
        if product.product_number:
            description = f"Design #{product.product_number}\n\n{description}"
        
        # Prepare link to design page
        # Pinterest requires HTTPS and publicly accessible URLs (no localhost)
        # Always use production domain for Pinterest links (Pinterest doesn't accept localhost)
        link = None
        domain = getattr(settings, 'SITE_DOMAIN', 'wedesignz.com')
        if not domain.startswith('http'):
            domain = f"https://{domain}"
        
        # Validate domain - must be HTTPS and not localhost
        if domain.startswith('https://') and 'localhost' not in domain.lower() and '127.0.0.1' not in domain:
            # Link to customer dashboard with product ID to auto-open product modal
            link = f"{domain}/customer-dashboard?product={product.id}"
            logger.info(f"Using Pinterest link: {link}")
        else:
            # Invalid domain (localhost), skip link - Pinterest allows pins without links
            logger.warning(f"Invalid domain for Pinterest link: {domain}, skipping link (Pinterest allows pins without links)")
            link = None
        
        # Mark as retrying
        pinterest_post.mark_retrying()
        
        # Post pins - create separate pins for mockup and design
        pins_data = {}
        errors = []  # Track errors for each pin attempt
        
        # Post mockup.avif (convert to JPEG for Pinterest compatibility)
        if mockup_avif:
            try:
                # Pinterest doesn't support AVIF, so convert to JPEG
                mockup_url = f"{media_domain}{mockup_avif.file.url}"
                
                # If it's an AVIF file, convert to JPEG
                if mockup_avif.file.name.lower().endswith('.avif'):
                    from .avif_converter import convert_avif_to_jpeg
                    logger.info(f"Converting AVIF mockup to JPEG for Pinterest: {mockup_avif.file.name}")
                    jpeg_path, jpeg_url = convert_avif_to_jpeg(mockup_avif.file.name, quality=85)
                    
                    if jpeg_url:
                        mockup_url = jpeg_url
                        logger.info(f"Using converted JPEG for mockup: {jpeg_url}")
                    else:
                        logger.warning(f"AVIF to JPEG conversion failed, trying original URL (may fail): {mockup_url}")
                
                mockup_title = f"{base_title} - Mockup"
                
                pin_params = {
                    'image_url': mockup_url,
                    'title': mockup_title[:100],  # Pinterest limit
                    'description': description,
                }
                if link:
                    pin_params['link'] = link
                
                logger.info(f"Attempting to post mockup pin for product {product.id}: {mockup_url}")
                result = pinterest_service.create_pin(**pin_params)
                
                if result and 'id' in result:
                    pins_data['mockup'] = {
                        'id': result.get('id'),
                        'url': result.get('url', '')
                    }
                    logger.info(f"✅ Posted mockup pin for product {product.id}: {result.get('id')}")
                elif result and 'error' in result:
                    # Detailed error from create_pin
                    error_info = result.get('error', 'Unknown error')
                    error_type = result.get('type', 'unknown')
                    status_code = result.get('status_code')
                    
                    error_msg = f"Mockup pin failed: {error_info}"
                    if status_code:
                        error_msg += f" (HTTP {status_code})"
                    
                    errors.append(error_msg)
                    logger.error(f"❌ Failed to post mockup pin for product {product.id}: {error_msg}")
                else:
                    # Fallback: check integration for error
                    integration.refresh_from_db()
                    error_detail = integration.last_error if integration.last_error else "Unknown error (no error details available)"
                    error_msg = f"Mockup pin failed: {error_detail}"
                    errors.append(error_msg)
                    logger.error(f"❌ Failed to post mockup pin for product {product.id}: {error_msg}")
            except Exception as e:
                error_msg = f"Exception posting mockup pin: {str(e)}"
                errors.append(error_msg)
                logger.error(f"❌ Exception posting mockup pin for product {product.id}: {error_msg}", exc_info=True)
        
        # Post design_JPG.avif (convert to JPEG for Pinterest compatibility)
        if design_jpg_avif:
            try:
                # Pinterest doesn't support AVIF, so convert to JPEG
                design_url = f"{media_domain}{design_jpg_avif.file.url}"
                
                # If it's an AVIF file, convert to JPEG
                if design_jpg_avif.file.name.lower().endswith('.avif'):
                    from .avif_converter import convert_avif_to_jpeg
                    logger.info(f"Converting AVIF design to JPEG for Pinterest: {design_jpg_avif.file.name}")
                    jpeg_path, jpeg_url = convert_avif_to_jpeg(design_jpg_avif.file.name, quality=85)
                    
                    if jpeg_url:
                        design_url = jpeg_url
                        logger.info(f"Using converted JPEG for design: {jpeg_url}")
                    else:
                        logger.warning(f"AVIF to JPEG conversion failed, trying original URL (may fail): {design_url}")
                
                design_title = f"{base_title} - Design"
                
                pin_params = {
                    'image_url': design_url,
                    'title': design_title[:100],  # Pinterest limit
                    'description': description,
                }
                if link:
                    pin_params['link'] = link
                
                logger.info(f"Attempting to post design pin for product {product.id}: {design_url}")
                result = pinterest_service.create_pin(**pin_params)
                
                if result and 'id' in result:
                    pins_data['design'] = {
                        'id': result.get('id'),
                        'url': result.get('url', '')
                    }
                    logger.info(f"✅ Posted design pin for product {product.id}: {result.get('id')}")
                elif result and 'error' in result:
                    # Detailed error from create_pin
                    error_info = result.get('error', 'Unknown error')
                    error_type = result.get('type', 'unknown')
                    status_code = result.get('status_code')
                    
                    error_msg = f"Design pin failed: {error_info}"
                    if status_code:
                        error_msg += f" (HTTP {status_code})"
                    
                    errors.append(error_msg)
                    logger.error(f"❌ Failed to post design pin for product {product.id}: {error_msg}")
                else:
                    # Fallback: check integration for error
                    integration.refresh_from_db()
                    error_detail = integration.last_error if integration.last_error else "Unknown error (no error details available)"
                    error_msg = f"Design pin failed: {error_detail}"
                    errors.append(error_msg)
                    logger.error(f"❌ Failed to post design pin for product {product.id}: {error_msg}")
            except Exception as e:
                error_msg = f"Exception posting design pin: {str(e)}"
                errors.append(error_msg)
                logger.error(f"❌ Exception posting design pin for product {product.id}: {error_msg}", exc_info=True)
        
        # Mark success if at least one pin was posted
        if pins_data:
            pinterest_post.mark_success(pins_data=pins_data)
            logger.info(f"✅ Successfully posted {len(pins_data)} pin(s) for product {product.id}")
            
            # If there were partial failures, log them but don't fail the task
            if errors:
                logger.warning(f"⚠️ Partial success for product {product.id}: {len(pins_data)} succeeded, {len(errors)} failed. Errors: {'; '.join(errors)}")
        else:
            # All pins failed - build comprehensive error message
            error_msg_parts = ["Failed to post any pins"]
            
            if errors:
                error_msg_parts.append("Errors:")
                for i, err in enumerate(errors, 1):
                    error_msg_parts.append(f"{i}. {err}")
            else:
                # Fallback: check integration for last error
                integration.refresh_from_db()
                if integration.last_error:
                    error_msg_parts.append(f"Last Pinterest API error: {integration.last_error}")
                else:
                    error_msg_parts.append("No specific error details available. Check Pinterest integration status.")
            
            # Add context information
            error_msg_parts.append(f"Product ID: {product.id}")
            error_msg_parts.append(f"Board ID: {integration.board_id}")
            error_msg_parts.append(f"Media domain: {media_domain}")
            
            full_error_msg = " | ".join(error_msg_parts)
            
            pinterest_post.mark_failed(full_error_msg)
            logger.error(f"❌ Failed to post any pins for product {product.id}: {full_error_msg}")
            
            # Retry the task with detailed error
            raise Exception(f"Pinterest API call failed: {full_error_msg}")
            
    except Exception as e:
        error_message = str(e)
        logger.error(f"❌ Error posting to Pinterest: {error_message}", exc_info=True)
        
        # Update PinterestPost record with detailed error
        try:
            pinterest_post = PinterestPost.objects.get(id=pinterest_post_id)
            
            # Try to get more context from integration
            try:
                integration = PinterestIntegration.get_instance()
                integration.refresh_from_db()
                
                # Enhance error message with integration status if available
                if integration.last_error and integration.last_error not in error_message:
                    error_message = f"{error_message} | Integration error: {integration.last_error}"
                
                # Add token validity check
                if not integration.is_token_valid():
                    error_message = f"{error_message} | Token is expired or invalid (expires at: {integration.token_expires_at})"
                
                # Add integration status
                error_message = f"{error_message} | Integration enabled: {integration.is_enabled}, Board ID: {integration.board_id}"
            except Exception as integration_error:
                logger.warning(f"Could not fetch integration details: {str(integration_error)}")
            
            pinterest_post.mark_failed(error_message)
            logger.info(f"📝 Updated PinterestPost {pinterest_post_id} with error: {error_message[:200]}...")
        except Exception as update_error:
            logger.error(f"Failed to update PinterestPost with error: {str(update_error)}", exc_info=True)
        
        # Check if we should retry
        retry_count = self.request.retries
        max_retries = self.max_retries
        
        if retry_count >= max_retries:
            logger.error(f"❌ Max retries ({max_retries}) reached for PinterestPost {pinterest_post_id}. Giving up.")
        else:
            # Exponential backoff: 60s, 120s, 240s
            countdown = 60 * (2 ** retry_count)
            logger.info(f"🔄 Retrying Pinterest post (attempt {retry_count + 1}/{max_retries + 1}) in {countdown}s...")
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task
def retry_failed_pinterest_posts():
    """
    Retry all failed Pinterest posts.
    Called when Pinterest is reconnected or manually triggered.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from .models import PinterestPost, PinterestIntegration
        from django.conf import settings
        
        # Check if Pinterest is enabled and configured
        integration = PinterestIntegration.get_instance()
        if not integration.is_enabled or not integration.is_token_valid():
            logger.warning("Pinterest is not enabled or token is invalid. Cannot retry posts.")
            return
        
        # Find all failed posts
        failed_posts = PinterestPost.objects.filter(status='failed')
        count = failed_posts.count()
        
        if count == 0:
            logger.info("No failed Pinterest posts to retry")
            return
        
        logger.info(f"Retrying {count} failed Pinterest posts...")
        
        # Get base URL for image links
        base_url = getattr(settings, 'SITE_DOMAIN', 'https://wedesignz.com')
        if not base_url.startswith('http'):
            base_url = f"https://{base_url}"
        
        retried_count = 0
        for post in failed_posts:
            try:
                # Queue the post task
                post_design_to_pinterest.delay(post.id, base_url)
                retried_count += 1
            except Exception as e:
                logger.error(f"Failed to queue retry for PinterestPost {post.id}: {str(e)}")
        
        logger.info(f"Queued {retried_count} Pinterest posts for retry")
        return f"Retried {retried_count} failed Pinterest posts"
        
    except Exception as e:
        logger.error(f"Error retrying failed Pinterest posts: {str(e)}", exc_info=True)
        raise
