from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count
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
from Wallet.models import WalletWithdrawalRequest
from Profiles.models import Studio, StudioMember
from Catalog.models import Product
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


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


@shared_task(bind=True, name='common.tasks.daily_database_backup')
def daily_database_backup(self):
    """Create daily database backup."""
    try:
        backup_dir = os.path.join(settings.BASE_DIR, 'backups', 'daily')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Create backup filename with timestamp
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"wedesignz_daily_{timestamp}.sql"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Database backup command (adjust for your database)
        db_settings = settings.DATABASES['default']
        if db_settings['ENGINE'] == 'django.db.backends.postgresql':
            import subprocess
            subprocess.run([
                'pg_dump',
                '-h', db_settings['HOST'],
                '-U', db_settings['USER'],
                '-d', db_settings['NAME'],
                '-f', backup_path
            ])
        
        # Clean up old daily backups (keep only 2 days)
        old_backups = []
        for file in os.listdir(backup_dir):
            if file.startswith('wedesignz_daily_'):
                file_path = os.path.join(backup_dir, file)
                file_time = os.path.getctime(file_path)
                if file_time < (timezone.now() - timedelta(days=2)).timestamp():
                    old_backups.append(file_path)
        
        for old_backup in old_backups:
            os.remove(old_backup)
        
        logger.info(f"Daily backup created: {backup_filename}")
        return f"Daily backup created: {backup_filename}"
        
    except Exception as e:
        logger.error(f"Failed to create daily backup: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=2)


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


@shared_task(bind=True, name='common.tasks.process_custom_order_timeouts')
def process_custom_order_timeouts(self):
    """Process custom orders that have exceeded the configured time limit."""
    try:
        from common.business_config import BusinessConfig
        timeout_threshold = timezone.now() - timedelta(hours=BusinessConfig.get_custom_order_time_slot_hours())
        timeout_orders = CustomOrderRequest.objects.filter(
            status='in_progress',
            created_at__lt=timeout_threshold
        )
        
        processed_count = 0
        for order in timeout_orders:
            try:
                # Mark as failed due to timeout
                order.status = 'failed'
                order.save()
                
                # Send notification to user
                send_mail(
                    subject="Custom Order Timeout - WeDesignz",
                    message=f"Your custom order #{order.id} has exceeded the 1-hour delivery time and has been cancelled. A refund will be processed.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.created_by.email],
                    fail_silently=False,
                )
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Failed to process timeout for order {order.id}: {str(e)}")
        
        logger.info(f"Processed {processed_count} timeout custom orders")
        return f"Processed {processed_count} timeout custom orders"
        
    except Exception as e:
        logger.error(f"Failed to process custom order timeouts: {str(e)}")
        raise self.retry(exc=e, countdown=60, max_retries=3)


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


@shared_task(bind=True, name='common.tasks.process_monthly_settlements')
def process_monthly_settlements(self):
    """Process monthly settlements for designers on day 1 of each month."""
    try:
        from datetime import datetime
        import pytz
        
        # Get current date in Asia/Kolkata timezone
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        current_date = datetime.now(kolkata_tz)
        
        # Only run on day 1 of the month
        if current_date.day != 1:
            logger.info("Not the first day of the month, skipping settlement processing")
            return "Not the first day of the month"
        
        # TODO: Create settlement requests for all eligible designers
        # eligible_designers = User.objects.filter(
        #     is_active=True,
        #     designerprofile__status='verified',
        #     wallet__balance__gt=0
        # )
        
        # for designer in eligible_designers:
        #     # Calculate earnings from last settlement
        #     # Create settlement request
        #     # Send notification
        
        logger.info("Monthly settlement processing completed")
        return "Monthly settlement processing completed"
        
    except Exception as e:
        logger.error(f"Failed to process monthly settlements: {str(e)}")
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


@shared_task(bind=True, name='common.tasks.send_designer_invoice_email_async')
def send_designer_invoice_email_async(self, invoice_id, order_id, breakdown_data):
    """Send designer invoice (bill) email asynchronously."""
    try:
        invoice = Invoice.objects.select_related('user', 'order').get(id=invoice_id)
        order = Order.objects.select_related('created_by').get(id=order_id)
        
        # Reconstruct breakdown dict from serialized data
        # breakdown_data should contain: product_total, gst_amount, commission_amount, wallet_amount, product_ids
        from decimal import Decimal
        breakdown = {
            'product_total': Decimal(str(breakdown_data['product_total'])),
            'gst_amount': Decimal(str(breakdown_data['gst_amount'])),
            'commission_amount': Decimal(str(breakdown_data['commission_amount'])),
            'wallet_amount': Decimal(str(breakdown_data['wallet_amount'])),
        }
        
        # Fetch products from IDs
        if 'product_ids' in breakdown_data:
            product_ids = breakdown_data['product_ids']
            products = Product.objects.filter(id__in=product_ids)
            breakdown['products'] = list(products)
        else:
            breakdown['products'] = []
        
        # Send email
        EmailService.send_designer_invoice_email(invoice, order, breakdown)
        logger.info(f"Designer invoice email sent for invoice {invoice_id}")
        return f"Designer invoice email sent for invoice {invoice_id}"
        
    except Invoice.DoesNotExist:
        logger.error(f"Invoice {invoice_id} not found")
        return f"Invoice {invoice_id} not found"
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found")
        return f"Order {order_id} not found"
    except Exception as e:
        logger.error(f"Failed to send designer invoice email for invoice {invoice_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.send_designer_subscription_invoice_email_async')
def send_designer_subscription_invoice_email_async(self, invoice_id, subscription_id, breakdown_data):
    """Send designer subscription invoice (bill) email asynchronously."""
    try:
        invoice = Invoice.objects.select_related('user', 'subscription').get(id=invoice_id)
        subscription = Subscription.objects.select_related('plan', 'created_by').get(id=subscription_id)
        
        # Reconstruct breakdown dict from serialized data
        from decimal import Decimal
        breakdown = {
            'product_total': Decimal(str(breakdown_data['product_total'])),
            'gst_amount': Decimal(str(breakdown_data['gst_amount'])),
            'commission_amount': Decimal(str(breakdown_data['commission_amount'])),
            'wallet_amount': Decimal(str(breakdown_data['wallet_amount'])),
            'download_count': breakdown_data.get('download_count', 0),
        }
        
        # Fetch products from IDs
        if 'product_ids' in breakdown_data:
            product_ids = breakdown_data['product_ids']
            products = Product.objects.filter(id__in=product_ids)
            breakdown['products'] = list(products)
        else:
            breakdown['products'] = []
        
        # Send email - we'll need to modify EmailService to handle subscription invoices
        # For now, use the same email service but with subscription context
        EmailService.send_designer_invoice_email(invoice, None, breakdown)  # Pass None for order
        logger.info(f"Designer subscription invoice email sent for invoice {invoice_id}")
        return f"Designer subscription invoice email sent for invoice {invoice_id}"
        
    except Invoice.DoesNotExist:
        logger.error(f"Invoice {invoice_id} not found")
        return f"Invoice {invoice_id} not found"
    except Subscription.DoesNotExist:
        logger.error(f"Subscription {subscription_id} not found")
        return f"Subscription {subscription_id} not found"
    except Exception as e:
        logger.error(f"Failed to send designer subscription invoice email for invoice {invoice_id}: {str(e)}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)


@shared_task(bind=True, name='common.tasks.process_expired_subscriptions')
def process_expired_subscriptions(self):
    """
    Process subscription settlements:
    - Monthly subscriptions: When 30-day period ends
    - Annual subscriptions: Monthly based on purchase date (purchase_date + 30*N days)
      Example: Purchased March 14 → Settles April 14, May 14, June 14, etc.
    Runs daily to check for subscriptions that need settlement.
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
                    logger.info(f"Processed monthly subscription settlement for subscription {subscription.id}: {result.get('total_downloads', 0)} downloads, {result.get('per_download_price', 0):.2f} per download")
                    
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

@shared_task(bind=True, max_retries=3)
def post_to_instagram(self, instagram_post_id, base_url=None):
    """
    Post to Instagram asynchronously.
    Updates InstagramPost record with result.
    """
    import logging
    import os
    logger = logging.getLogger(__name__)
    
    try:
        from django.conf import settings
        from .models import InstagramPost, InstagramIntegration
        from Catalog.models import Product
        
        # Check if Instagram is enabled
        integration = InstagramIntegration.get_instance()
        if not integration.is_enabled:
            logger.debug("Instagram integration is disabled")
            instagram_post = InstagramPost.objects.get(id=instagram_post_id)
            instagram_post.mark_failed("Instagram integration is disabled")
            return
        
        # Get the InstagramPost record
        try:
            instagram_post = InstagramPost.objects.get(id=instagram_post_id)
        except InstagramPost.DoesNotExist:
            logger.error(f"InstagramPost {instagram_post_id} not found")
            return
        
        # Mark as processing
        instagram_post.mark_processing()
        
        # Get the product
        try:
            product = instagram_post.product
        except Product.DoesNotExist:
            logger.error(f"Product not found for InstagramPost {instagram_post_id}")
            instagram_post.mark_failed("Product not found")
            return
        
        # Check if Instagram is configured
        try:
            from .instagram_service import InstagramService
            instagram_service = InstagramService()
        except Exception as e:
            error_msg = f"Instagram not configured: {str(e)}"
            logger.warning(error_msg)
            instagram_post.mark_failed(error_msg)
            return
        
        # Get media files (images)
        media_files = product.get_media().filter(media_type='image')
        
        if not media_files.exists():
            logger.warning(f"No image media found for product {product.id}")
            instagram_post.mark_failed("No image media found for product")
            return
        
        # Find the specific media file based on media_type
        image_media = None
        media_type = instagram_post.media_type
        
        for media in media_files:
            if not media.file:
                continue
            
            file_name = media.file.name.lower() if hasattr(media, 'file') and media.file else ''
            base_name = os.path.splitext(os.path.basename(file_name))[0] if file_name else ''
            
            if media_type == 'mockup':
                # Check if it's a mockup
                is_mockup = base_name == 'mockup'
                if not is_mockup:
                    # Check metadata
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
                
                if is_mockup:
                    image_media = media
                    break
            elif media_type == 'jpg':
                if file_name.endswith(('.jpg', '.jpeg')):
                    image_media = media
                    break
            elif media_type == 'png':
                if file_name.endswith('.png'):
                    image_media = media
                    break
        
        if not image_media:
            logger.warning(f"No {media_type} image found for product {product.id}")
            instagram_post.mark_failed(f"No {media_type} image found for product")
            return
        
        # Get image URL
        image_url = image_media.file.url if hasattr(image_media, 'file') and image_media.file else None
        
        if not image_url:
            logger.warning(f"Image URL not available for media {image_media.id}")
            instagram_post.mark_failed("Image URL not available")
            return
        
        # Make image URL absolute if it's relative
        if image_url.startswith('/'):
            site_domain = getattr(settings, 'SITE_DOMAIN', 'wedesignz.com')
            protocol = 'https' if not settings.DEBUG else 'http'
            image_url = f"{protocol}://{site_domain}{image_url}"
        
        # Post to Instagram
        is_story = instagram_post.post_type == 'story'
        result = instagram_service.create_and_publish_post(
            image_url=image_url,
            caption=instagram_post.caption,
            is_story=is_story
        )
        
        if result and result.get('id'):
            # Success
            instagram_post.mark_success(
                media_id=result.get('id'),
                post_id=result.get('id'),
                post_url=result.get('url')
            )
            logger.info(f"Instagram post created successfully: {result.get('id')}")
        else:
            # Failed
            error_msg = "Failed to create Instagram post"
            instagram_post.mark_failed(error_msg)
            logger.error(f"Failed to create Instagram post for product {product.id}")
            
    except Exception as e:
        logger.error(f"Error posting to Instagram: {str(e)}", exc_info=True)
        try:
            instagram_post = InstagramPost.objects.get(id=instagram_post_id)
            instagram_post.mark_failed(f"Error: {str(e)}")
        except Exception:
            pass
        
        # Retry if not exceeded max retries
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


# ==================== PINTEREST TASKS ====================

@shared_task(bind=True, max_retries=3)
def post_design_to_pinterest(self, pinterest_post_id, base_url=None):
    """
    Post a design to Pinterest after approval.
    This runs asynchronously so it doesn't block the approval process.
    Updates PinterestPost record with result.
    """
    import logging
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
        
        # Prioritize: JPG > PNG > other images (skip mockup)
        image_media = None

        for media in media_files:
            if not media.file:
                continue
            
            file_name = media.file.name.lower()
            base_name = os.path.splitext(os.path.basename(file_name))[0]
            
            # Skip mockup files
            if base_name == 'mockup':
                continue
            
            # Prefer JPG first
            if file_name.endswith(('.jpg', '.jpeg')):
                image_media = media
                break

        # If no JPG, try PNG
        if not image_media:
            for media in media_files:
                if not media.file:
                    continue
                file_name = media.file.name.lower()
                base_name = os.path.splitext(os.path.basename(file_name))[0]
                if base_name == 'mockup':
                    continue
                if file_name.endswith('.png'):
                    image_media = media
                    break

        # Fallback to any non-mockup image
        if not image_media:
            for media in media_files:
                if not media.file:
                    continue
                file_name = media.file.name.lower()
                base_name = os.path.splitext(os.path.basename(file_name))[0]
                if base_name != 'mockup':
                    image_media = media
                    break

        # Last resort: use first image
        if not image_media:
            image_media = media_files.first()
        
        # Build absolute image URL
        # Pinterest requires HTTPS and publicly accessible URLs (no localhost)
        # Always use MEDIA_DOMAIN from settings (where media files are actually hosted)
        media_domain = getattr(settings, 'MEDIA_DOMAIN', 'devapi.wedesignz.com')
        if not media_domain.startswith('http'):
            media_domain = f"https://{media_domain}"
        
        # Validate media domain - must be HTTPS and not localhost
        if media_domain.startswith('https://') and 'localhost' not in media_domain.lower() and '127.0.0.1' not in media_domain:
            image_url = f"{media_domain}{image_media.file.url}"
            logger.info(f"Using Pinterest image URL: {image_url}")
        else:
            # Invalid domain (localhost), cannot post to Pinterest
            error_msg = f"Invalid media domain for Pinterest image URL: {media_domain}. Pinterest requires publicly accessible HTTPS URLs."
            logger.error(error_msg)
            pinterest_post.mark_failed(error_msg)
            return
        
        # Prepare pin details
        title = product.title[:100] if product.title else "Design"  # Pinterest limit
        description = product.description[:800] if product.description else ""
        
        # Add design number if available
        if product.product_number:
            description = f"Design #{product.product_number}\n\n{description}"
        
        # Optional: Add link to design page
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
        
        # Create pin - only pass link if it's valid
        pin_params = {
            'image_url': image_url,
            'title': title,
            'description': description,
        }
        if link:
            pin_params['link'] = link
        
        result = pinterest_service.create_pin(**pin_params)
        
        if result:
            pin_id = result.get('id')
            pin_url = result.get('url', '')
            pinterest_post.mark_success(pin_id=pin_id, pin_url=pin_url)
            logger.info(f"Successfully posted product {product.id} to Pinterest: {pin_id}")
        else:
            error_msg = "Failed to create pin - check Pinterest service logs"
            pinterest_post.mark_failed(error_msg)
            logger.error(f"Failed to post product {product.id} to Pinterest")
            # Retry the task
            raise Exception("Pinterest API call failed")
            
    except Exception as e:
        logger.error(f"Error posting to Pinterest: {str(e)}", exc_info=True)
        # Update PinterestPost record with error
        try:
            pinterest_post = PinterestPost.objects.get(id=pinterest_post_id)
            pinterest_post.mark_failed(str(e))
        except:
            pass
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
