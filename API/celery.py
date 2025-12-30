import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings
from decouple import config

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
    # OTP Cleanup - Every week at 2:00 AM (Sunday)
    'cleanup-expired-otps': {
        'task': 'common.tasks.cleanup_expired_otps',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Every Sunday at 2:00 AM IST
    },
    
    # Expire Coupons - Every day at 4 AM
    'expire-coupons': {
        'task': 'common.tasks.expire_coupons',
        'schedule': crontab(hour=4, minute=0),  # Daily at 4:00 AM IST
    },
    
    # Subscription Expiry Reminders - Every Sunday at 3:30 AM
    'send-subscription-expiry-reminders': {
        'task': 'common.tasks.send_subscription_expiry_reminders',
        'schedule': crontab(hour=3, minute=30, day_of_week=0),  # Every Sunday at 3:30 AM IST
    },
    
    # Process Subscription Billing - Daily at 3:00 AM IST
    'process-subscription-billing': {
        'task': 'common.tasks.process_subscription_billing',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3:00 AM IST
    },
    
    # Create Designer Payout Requests - Day 1 of every month at 1:00 AM IST
    'create-designer-payout-requests': {
        'task': 'common.tasks.create_designer_payout_requests',
        'schedule': crontab(day_of_month=1, hour=1, minute=0),  # Day 1 at 1:00 AM IST
    },
    
    # Process Settlement Payouts - Day 6 of every month at 1:00 AM IST
    'process-settlement-payouts': {
        'task': 'common.tasks.process_settlement_payouts',
        'schedule': crontab(day_of_month=6, hour=1, minute=0),  # Day 6 at 1:00 AM IST
    },
    
    # Expire Processing Settlements - Daily at 2:00 AM IST
    # Marks settlements as expired if they've been in 'processing' status for more than 7 days
    'expire-processing-settlements': {
        'task': 'common.tasks.expire_processing_settlements',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM IST
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

# Task routing - Environment-based queue separation
# Determine environment (production or development)
# Use decouple.config() to read from .env file (same as Django settings)
# Default to 'production' if not set
ENVIRONMENT = config('ENVIRONMENT', default='production').lower()

# Configure task routing based on environment
if ENVIRONMENT == 'production':
    # Production environment - use 'production' queue
    app.conf.task_default_queue = 'production'
    app.conf.task_routes = {
        'Profiles.tasks.*': {'queue': 'production'},
        'Catalog.tasks.*': {'queue': 'production'},
        'common.tasks.*': {'queue': 'production'},
        'MediaFiles.tasks.*': {'queue': 'production'},
    }
    print(f"[Celery] Environment: PRODUCTION - Tasks will be routed to 'production' queue")
else:
    # Development/DevAPI environment - use 'development' queue
    app.conf.task_default_queue = 'development'
    app.conf.task_routes = {
        'Profiles.tasks.*': {'queue': 'development'},
        'Catalog.tasks.*': {'queue': 'development'},
        'common.tasks.*': {'queue': 'development'},
        'MediaFiles.tasks.*': {'queue': 'development'},
    }
    print(f"[Celery] Environment: DEVELOPMENT - Tasks will be routed to 'development' queue")

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
