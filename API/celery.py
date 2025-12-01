import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'API.settings')

app = Celery('WeDesignz')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Celery Beat configuration
app.conf.beat_schedule = {
    # OTP Cleanup - Every 5 minutes
    'cleanup-expired-otps': {
        'task': 'common.tasks.cleanup_expired_otps',
        'schedule': 300.0,  # 5 minutes
    },
    
    # Custom Order Timeouts - Every 5 minutes
    'process-custom-order-timeouts': {
        'task': 'common.tasks.process_custom_order_timeouts',
        'schedule': 300.0,  # 5 minutes
    },
    
    # Subscription Status Updates - Every hour
    'update-subscription-status': {
        'task': 'common.tasks.update_subscription_status',
        'schedule': 3600.0,  # 1 hour
    },
    
    # Auto-mandate Notifications - Every hour
    'send-auto-mandate-notifications': {
        'task': 'common.tasks.send_auto_mandate_notifications',
        'schedule': 3600.0,  # 1 hour
    },
    
    # Daily Backup - Every day at 2 AM
    'daily-database-backup': {
        'task': 'common.tasks.daily_database_backup',
        'schedule': 7200.0,  # 2 hours (2 AM)
    },
    
    # Expire Coupons - Every day at 2 AM
    'expire-coupons': {
        'task': 'common.tasks.expire_coupons',
        'schedule': 7200.0,  # 2 hours (2 AM)
    },
    
    # Mark Inactive Accounts - Every day at 2 AM
    'mark-inactive-accounts-for-deletion': {
        'task': 'common.tasks.mark_inactive_accounts_for_deletion',
        'schedule': 7200.0,  # 2 hours (2 AM)
    },
    
    # Weekly Backup - Every Sunday at 3 AM
    'weekly-database-backup': {
        'task': 'common.tasks.weekly_database_backup',
        'schedule': 604800.0,  # 1 week
    },
    
    # Subscription Expiry Reminders - Every Sunday at 3 AM
    'send-subscription-expiry-reminders': {
        'task': 'common.tasks.send_subscription_expiry_reminders',
        'schedule': 604800.0,  # 1 week
    },
    
    # Process Expired Subscriptions - Daily at 3:30 AM IST
    'process-expired-subscriptions': {
        'task': 'common.tasks.process_expired_subscriptions',
        'schedule': crontab(hour=3, minute=30),  # Daily at 3:30 AM IST
    },
    
    # Promotional Emails - Every 3 days at 10 AM
    'send-promotional-emails': {
        'task': 'common.tasks.send_promotional_emails',
        'schedule': 259200.0,  # 3 days
    },
}

# Timezone configuration
app.conf.timezone = 'Asia/Kolkata'

# Task result backend
app.conf.result_backend = 'django-db'

# Task serialization
app.conf.task_serializer = 'json'
app.conf.accept_content = ['json']
app.conf.result_serializer = 'json'

# Task routing
app.conf.task_routes = {
    'common.tasks.*': {'queue': 'default'},
    'common.tasks.send_*': {'queue': 'email'},
    'common.tasks.*_backup': {'queue': 'backup'},
    'Catalog.tasks.*': {'queue': 'default'},
    'Profiles.tasks.*': {'queue': 'default'},
}

# Task execution settings
app.conf.task_always_eager = False
app.conf.task_eager_propagates = True

# Worker settings
app.conf.worker_prefetch_multiplier = 1
app.conf.task_acks_late = True

# Monitoring
app.conf.worker_send_task_events = True
app.conf.task_send_sent_event = True

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
