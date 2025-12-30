# Celery Configuration and Usage Guide

This document provides comprehensive information about Celery configuration, tasks, and usage in the WeDesignz API project.

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Setup and Installation](#setup-and-installation)
4. [Running Celery](#running-celery)
5. [Tasks](#tasks)
6. [Periodic Tasks (Celery Beat)](#periodic-tasks-celery-beat)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

## Overview

Celery is used for asynchronous task processing in the WeDesignz API. It handles:
- Background job processing (e.g., design upload processing)
- Periodic scheduled tasks (e.g., cleanup, backups, notifications)
- Email sending
- Report generation
- Database maintenance

## Configuration

### Settings (`API/settings.py`)

```python
# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='django-db')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_ENABLE_UTC = True

# Celery Beat Configuration
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Celery Task Settings
CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

# Celery Monitoring
CELERY_FLOWER_URL = config('CELERY_FLOWER_URL', default='http://localhost:5555')
```

### Environment Variables

- `ENVIRONMENT`: Environment type - `production` or `development` (default: `production`)
  - **Production**: Tasks are routed to `production` queue
  - **Development**: Tasks are routed to `development` queue
  - This ensures production and development tasks are processed separately
- `CELERY_BROKER_URL`: Redis broker URL (default: `redis://localhost:6379/0`)
- `CELERY_RESULT_BACKEND`: Result backend (default: `django-db`)
- `CELERY_TASK_ALWAYS_EAGER`: Run tasks synchronously for testing (default: `False`)
- `CELERY_FLOWER_URL`: Flower monitoring URL (default: `http://localhost:5555`)

### Queue Separation (Production vs Development)

The system automatically routes tasks to different queues based on the `ENVIRONMENT` variable:

- **Production** (`ENVIRONMENT=production`):
  - All tasks go to `production` queue
  - Workers listen to `production` queue
  - Default if `ENVIRONMENT` is not set

- **Development/DevAPI** (`ENVIRONMENT=development`):
  - All tasks go to `development` queue
  - Workers listen to `development` queue

**Important**: Always set the `ENVIRONMENT` variable to ensure tasks are routed correctly:
```bash
# Production
export ENVIRONMENT=production

# Development
export ENVIRONMENT=development
```

### Celery App (`API/celery.py`)

The Celery app is configured with:
- **App Name**: `WeDesignz`
- **Timezone**: `Asia/Kolkata`
- **Result Backend**: `django-db`
- **Serialization**: JSON
- **Task Routing**: Queues for different task types (default, email, backup)

## Setup and Installation

### Prerequisites

1. **Redis** (Message Broker)
   ```bash
   # Install Redis
   sudo apt-get install redis-server  # Ubuntu/Debian
   brew install redis  # macOS
   
   # Start Redis
   redis-server
   ```

2. **Python Packages**
   ```bash
   pip install celery django-celery-beat django-celery-results redis
   ```

3. **Database Migrations**
   ```bash
   python manage.py migrate django_celery_beat
   python manage.py migrate django_celery_results
   ```

## Running Celery

### Using Management Command (Recommended)

The project includes a custom management command to start Celery services:

```bash
# Start all services (worker, beat, flower)
python manage.py start_celery --all

# Start only worker
python manage.py start_celery --worker

# Start only beat scheduler
python manage.py start_celery --beat

# Start only Flower monitoring
python manage.py start_celery --flower

# Custom options
python manage.py start_celery --all --loglevel=debug --concurrency=8
```

### Manual Commands

#### Start Celery Worker

**Production:**
```bash
export ENVIRONMENT=production
celery -A API worker --loglevel=info --concurrency=4 --pool=prefork --queues=production -n worker-prod@%h
```

**Development/DevAPI:**
```bash
export ENVIRONMENT=development
celery -A API worker --loglevel=info --concurrency=1 --pool=prefork --queues=development -n worker-dev@%h
```

**Note**: The queue name is automatically determined by the `ENVIRONMENT` variable. Workers must listen to the correct queue matching their environment.

#### Start Celery Beat (Scheduler)
```bash
celery -A API beat --loglevel=info --scheduler=django_celery_beat.schedulers:DatabaseScheduler
```

#### Start Flower (Monitoring)
```bash
celery -A API flower --port=5555
```

### Production Deployment

For production, use a process manager like **supervisor** or **systemd**:

#### Supervisor Example (`/etc/supervisor/conf.d/celery.conf`)
```ini
[program:celery-worker]
command=/path/to/venv/bin/celery -A API worker --loglevel=info --concurrency=4
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/worker.log

[program:celery-beat]
command=/path/to/venv/bin/celery -A API beat --loglevel=info --scheduler=django_celery_beat.schedulers:DatabaseScheduler
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/beat.log
```

## Tasks

### Task Locations

Tasks are defined in:
- `Profiles/tasks.py` - Design upload processing
- `common/tasks.py` - General background tasks

### Available Tasks

#### Design Processing (`Profiles/tasks.py`)

- **`process_design_upload_task`**
  - **Queue**: `default`
  - **Description**: Processes bulk design uploads from zip files
  - **Parameters**:
    - `task_id`: ID of the DesignProcessingTask record
    - `zip_file_path`: Path to the stored zip file
  - **Usage**:
    ```python
    from Profiles.tasks import process_design_upload_task
    process_design_upload_task.delay(task_id, zip_file_path)
    ```

#### MediaFiles Tasks (`MediaFiles/tasks.py`)

- **`rename_design_files_task`**
  - **Queue**: `default` (follows environment routing)
  - **Description**: Renames design files to use product_number format
  - **Parameters**:
    - `user_id` (int, optional): Process only files for a specific user ID
    - `product_id` (int, optional): Process only files for a specific product ID
    - `dry_run` (bool): Show what would be renamed without actually renaming files
    - `verbose` (bool): Show detailed information for each file
  - **Usage**:
    ```python
    from MediaFiles.tasks import rename_design_files_task
    rename_design_files_task.delay(user_id=4, product_id=60, dry_run=False, verbose=True)
    ```

#### Common Tasks (`common/tasks.py`)

- **`send_promotional_emails`** - Send promotional emails to active users
- **`update_subscription_status`** - Update subscription status for recurring billing
- **`send_auto_mandate_notifications`** - Send notifications for upcoming auto-mandate transactions
- **`cleanup_expired_otps`** - Clean up expired OTPs from the database
- **`expire_coupons`** - Mark expired coupons as inactive
- **`weekly_database_backup`** - Create weekly database backup with media files
- **`mark_inactive_accounts_for_deletion`** - Mark deactivated accounts for deletion after 6 months
- **`send_subscription_expiry_reminders`** - Send reminders for subscriptions expiring soon
- **`send_bulk_emails`** - Send bulk emails to specific users
- **`generate_reports`** - Generate various reports
- **`send_settlement_reminders`** - Send daily settlement reminders during settlement window
- **`process_monthly_settlements`** - Process monthly settlements for designers
- **`send_design_approval_reminders`** - Send reminders for designs pending approval
- **`send_designer_performance_reports`** - Send monthly performance reports to designers
- **`cleanup_expired_settlements`** - Clean up expired settlement requests

### Calling Tasks

#### Asynchronous Execution
```python
from Profiles.tasks import process_design_upload_task

# Delay execution
result = process_design_upload_task.delay(task_id, zip_file_path)

# Get task ID
task_id = result.id

# Check task status
result.ready()  # True if task completed
result.successful()  # True if task succeeded
result.get()  # Get result (blocks until complete)
```

#### Synchronous Execution (Testing)
```python
# Set in settings.py for testing
CELERY_TASK_ALWAYS_EAGER = True

# Or call directly
from Profiles.tasks import process_design_upload_task
result = process_design_upload_task(task_id, zip_file_path)
```

## Periodic Tasks (Celery Beat)

Periodic tasks are scheduled using Celery Beat and stored in the database via `django-celery-beat`.

### Scheduled Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| `cleanup-expired-otps` | Every 5 minutes | Clean up expired OTPs |
| `update-subscription-status` | Every hour | Update subscription status |
| `send-auto-mandate-notifications` | Every hour | Send auto-mandate notifications |
| `daily-database-backup` | Every day at 2 AM | Create daily database backup |
| `expire-coupons` | Every day at 2 AM | Expire coupons |
| `mark-inactive-accounts-for-deletion` | Every day at 2 AM | Mark inactive accounts |
| `weekly-database-backup` | Every Sunday at 3 AM | Create weekly backup |
| `send-subscription-expiry-reminders` | Every Sunday at 3 AM | Send subscription reminders |
| `send-promotional-emails` | Every 3 days at 10 AM | Send promotional emails |

### Managing Periodic Tasks

#### Via Django Admin
1. Go to Django Admin
2. Navigate to **Periodic Tasks** under **Django Celery Beat**
3. Create/edit periodic tasks

#### Via Code (`API/celery.py`)
Periodic tasks are defined in `app.conf.beat_schedule`:

```python
app.conf.beat_schedule = {
    'cleanup-expired-otps': {
        'task': 'common.tasks.cleanup_expired_otps',
        'schedule': 300.0,  # 5 minutes
    },
    # ... more tasks
}
```

## Monitoring

### Celery Flower (Best + Real-Time GUI Monitoring)

Flower is a web-based tool for real-time monitoring of Celery clusters. It provides a comprehensive GUI to monitor all three task states: **scheduled**, **reserved**, and **active** tasks.

**Access**: http://localhost:5555

#### Features

Flower provides real-time monitoring of:

1. **Scheduled Tasks** - Tasks waiting in the queue to be executed
2. **Reserved Tasks** - Tasks that have been picked up by workers but haven't started executing yet
3. **Active Tasks** - Tasks currently being executed by workers
4. **Task History** - Complete history of all executed tasks with results
5. **Worker Status** - Real-time status of all workers (online/offline, active tasks, processed tasks)
6. **Performance Metrics** - Task execution times, success/failure rates, throughput
7. **Task Details** - Full task information including arguments, results, tracebacks, and retries
8. **Worker Management** - Shutdown, restart, and rate limit workers
9. **Task Management** - Revoke tasks, retry failed tasks, view task results

#### Starting Flower

**Using Management Command (Recommended)**:
```bash
# Start Flower only
python manage.py start_celery --flower

# Start Flower on custom port
python manage.py start_celery --flower --flower-port=5556

# Start Flower with authentication (recommended for production)
python manage.py start_celery --flower --flower-auth=admin:securepassword

# Start all services (worker, beat, flower)
python manage.py start_celery --all
```

**Manual Command**:
```bash
# Basic
celery -A API flower --port=5555

# With authentication
celery -A API flower --port=5555 --basic_auth=admin:securepassword

# With broker URL
celery -A API flower --port=5555 --broker=redis://localhost:6379/0
```

**For Production (Recommended)**:
```bash
# Use separate terminal/process for each service
# Terminal 1: Worker
python manage.py start_celery --worker

# Terminal 2: Beat
python manage.py start_celery --beat

# Terminal 3: Flower
python manage.py start_celery --flower --flower-auth=admin:securepassword
```

#### Using Flower Web Interface

1. **Dashboard** (`/`)
   - Overview of all workers
   - Total tasks processed
   - Active, scheduled, and reserved tasks count
   - System resources (CPU, memory)

2. **Tasks** (`/tasks`)
   - View all tasks (scheduled, reserved, active, completed, failed)
   - Filter by task name, state, worker
   - View task details: arguments, results, tracebacks, retries
   - Revoke or retry tasks

3. **Workers** (`/workers`)
   - List all workers with status
   - View worker details: active tasks, processed tasks, stats
   - Shutdown or restart workers
   - View worker logs

4. **Monitor** (`/monitor`)
   - Real-time task rate graphs
   - Task execution time graphs
   - Success/failure rate graphs

5. **Broker** (`/broker`)
   - View broker connection status
   - Queue information
   - Exchange and routing information

#### Monitoring Task States in Real-Time

**Scheduled Tasks**:
- Tasks waiting in the queue
- View in Flower: Dashboard → "Scheduled" count, or Tasks page → Filter by "Scheduled"
- These are tasks that have been sent to the broker but not yet picked up by workers

**Reserved Tasks**:
- Tasks assigned to workers but not yet started
- View in Flower: Dashboard → "Reserved" count, or Tasks page → Filter by "Reserved"
- These tasks are in the worker's prefetch queue

**Active Tasks**:
- Tasks currently being executed
- View in Flower: Dashboard → "Active" count, or Tasks page → Filter by "Active"
- Click on a task to see detailed execution information

#### Flower API

Flower also provides a REST API for programmatic access:

```bash
# Get worker list
curl http://localhost:5555/api/workers

# Get active tasks
curl http://localhost:5555/api/tasks?state=ACTIVE

# Get scheduled tasks
curl http://localhost:5555/api/tasks?state=PENDING

# Get reserved tasks
curl http://localhost:5555/api/tasks?state=RESERVED

# Get task details
curl http://localhost:5555/api/task/<task-id>

# Revoke a task
curl -X POST http://localhost:5555/api/task/revoke/<task-id>
```

#### Security Considerations

For production environments, always enable authentication:

```bash
celery -A API flower --basic_auth=username:password
```

Or use environment variables:
```bash
export FLOWER_BASIC_AUTH=username:password
celery -A API flower
```

For additional security, consider:
- Running Flower behind a reverse proxy (nginx) with SSL
- Restricting access by IP address
- Using OAuth or other authentication methods

### Celery Inspect Commands

Use `celery inspect` to check the status of workers and tasks:

```bash
# Check active tasks (currently executing)
celery -A API inspect active

# Check reserved tasks (picked up but not executing yet)
celery -A API inspect reserved

# Check scheduled tasks (waiting to be executed)
celery -A API inspect scheduled

# Check which queues workers are listening to
celery -A API inspect active_queues

# Check registered tasks and their routing
celery -A API inspect registered
```

### Django Admin

Task results are stored in the database and can be viewed in Django Admin:
- **Task Results** under **Django Celery Results**
- **Periodic Tasks** under **Django Celery Beat**

### Logs

Celery logs are output to the console by default. For production, configure logging:

```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'celery': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/celery.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
        },
    },
    'loggers': {
        'celery': {
            'handlers': ['celery'],
            'level': 'INFO',
        },
    },
}
```

## Troubleshooting

### Common Issues

#### 1. Tasks Not Executing

**Check**:
- Redis is running: `redis-cli ping` (should return `PONG`)
- Celery worker is running: `celery -A API inspect active`
- Task is registered: `celery -A API inspect registered`

#### 2. Tasks Stuck in PENDING

**Possible Causes**:
- Worker not running
- Wrong queue name
- Broker connection issue

**Solution**:
```bash
# Check worker status
celery -A API inspect active

# Check registered tasks
celery -A API inspect registered

# Purge all tasks (use with caution)
celery -A API purge
```

#### 3. Import Errors

**Solution**: Ensure all task modules are in `INSTALLED_APPS` and tasks are properly decorated with `@shared_task`.

#### 4. Database Connection Issues

**Solution**: Ensure database migrations are run:
```bash
python manage.py migrate django_celery_beat
python manage.py migrate django_celery_results
```

#### 5. Timezone Issues

**Solution**: Ensure timezone is set correctly:
```python
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_ENABLE_UTC = True
```

### Debugging

#### Enable Debug Logging
```bash
celery -A API worker --loglevel=debug
```

#### Test Task Execution
```python
# In Django shell
from Profiles.tasks import process_design_upload_task
result = process_design_upload_task.delay(task_id, zip_file_path)
print(result.id)
print(result.status)
```

#### Check Task Results
```python
from django_celery_results.models import TaskResult
task = TaskResult.objects.get(task_id='your-task-id')
print(task.status)
print(task.result)
```

## Best Practices

1. **Use Appropriate Queues**: Route tasks to appropriate queues (default, email, backup)
2. **Set Task Timeouts**: Configure task time limits to prevent hanging tasks
3. **Handle Exceptions**: Always wrap task logic in try/except blocks
4. **Use Transactions**: Wrap database operations in transactions
5. **Monitor Tasks**: Use Flower or Django Admin to monitor task execution
6. **Log Everything**: Log task start, progress, and completion
7. **Test Locally**: Use `CELERY_TASK_ALWAYS_EAGER = True` for testing
8. **Retry Logic**: Implement retry logic for transient failures
9. **Idempotency**: Design tasks to be idempotent (safe to retry)
10. **Resource Limits**: Set appropriate concurrency and memory limits

## Additional Resources

- [Celery Documentation](https://docs.celeryproject.org/)
- [Django Celery Beat](https://django-celery-beat.readthedocs.io/)
- [Django Celery Results](https://django-celery-results.readthedocs.io/)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Redis Documentation](https://redis.io/documentation)

