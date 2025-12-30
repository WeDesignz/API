# Queue Separation Setup Guide

This guide explains how to set up separate queues for Production and DevAPI environments.

## What Changed

1. **Environment-based Queue Routing**: Tasks are now automatically routed to different queues based on the `ENVIRONMENT` variable
2. **Production Queue**: `production` - for production API tasks
3. **DevAPI Queue**: `devapi` - for development API tasks

## Setup Instructions

### Step 1: Set Environment Variables

#### For Production API (`/var/www/API/`)

Add to your production environment (`.env` file, systemd service, or supervisor config):

```bash
export ENVIRONMENT=production
```

#### For DevAPI (`/var/www/DevAPI/`)

Add to your development environment:

```bash
export ENVIRONMENT=development
```

### Step 2: Restart Workers

#### Stop Existing Workers

```bash
# Stop all Celery workers
pkill -f "celery.*worker"

# Verify they're stopped
ps aux | grep "celery.*worker" | grep -v grep
```

#### Start Production Worker

```bash
cd /var/www/API
export ENVIRONMENT=production
source venv/bin/activate

# Using management command
python manage.py start_celery --worker --concurrency=4

# OR manually
celery -A API worker \
    --loglevel=info \
    --concurrency=4 \
    --pool=prefork \
    --queues=production \
    -n worker-prod@%h
```

#### Start DevAPI Worker (if needed)

```bash
cd /var/www/DevAPI
export ENVIRONMENT=development
source venv/bin/activate

# Using management command
python manage.py start_celery --worker --concurrency=1

# OR manually
celery -A API worker \
    --loglevel=info \
    --concurrency=1 \
    --pool=prefork \
    --queues=devapi \
    -n worker-dev@%h
```

### Step 3: Verify Setup

#### Check Queue Configuration

```python
# In Django shell
from celery import current_app
import os

print(f"Environment: {os.environ.get('ENVIRONMENT', 'not set')}")
print(f"Default Queue: {current_app.conf.task_default_queue}")
print(f"Task Routes: {current_app.conf.task_routes}")
```

#### Check Worker Queues

```bash
# Check which queues workers are listening to
celery -A API inspect active_queues

# Should show:
# - Production worker: listening to 'production' queue
# - DevAPI worker: listening to 'devapi' queue
```

#### Check Redis Queues

```bash
redis-cli

# Check production queue
LLEN production

# Check devapi queue
LLEN devapi

exit
```

### Step 4: Test the Setup

#### Test Production Queue

```python
# In Production API Django shell
from Profiles.tasks import process_design_upload_task
from Profiles.models import DesignProcessingTask

task = DesignProcessingTask.objects.get(id=3)
result = process_design_upload_task.delay(task.id, task.zip_file_path)

print(f"Task ID: {result.id}")
# Check which queue it went to (should be 'production')
```

#### Test DevAPI Queue

```python
# In DevAPI Django shell
# Same test, should go to 'devapi' queue
```

## Using Supervisor (Production)

If using Supervisor, update your config:

```ini
[program:celery-worker-prod]
command=/var/www/API/venv/bin/celery -A API worker --loglevel=info --concurrency=4 --queues=production -n worker-prod@%%h
directory=/var/www/API
user=www-data
environment=ENVIRONMENT="production"
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/worker-prod.log
```

## Using Systemd (Production)

If using systemd, update your service file:

```ini
[Unit]
Description=Celery Worker (Production)
After=network.target

[Service]
Type=forking
User=www-data
Group=www-data
Environment="ENVIRONMENT=production"
WorkingDirectory=/var/www/API
ExecStart=/var/www/API/venv/bin/celery -A API worker --loglevel=info --concurrency=4 --queues=production -n worker-prod@%%h --detach
ExecStop=/bin/kill -s TERM $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

## Troubleshooting

### Tasks Not Being Picked Up

1. **Check Environment Variable**:
   ```bash
   echo $ENVIRONMENT
   ```

2. **Check Worker Queue**:
   ```bash
   celery -A API inspect active_queues
   ```

3. **Check Task Queue**:
   ```python
   from celery import current_app
   print(current_app.conf.task_default_queue)
   ```

### Tasks Going to Wrong Queue

- Verify `ENVIRONMENT` variable is set correctly
- Restart workers after setting environment variable
- Check Celery configuration logs on startup

### Both Workers Processing Same Tasks

- Ensure workers are listening to different queues
- Verify `ENVIRONMENT` variable is different for each
- Check that tasks are being routed correctly

## Benefits

1. **Isolation**: Production and development tasks are completely separated
2. **Safety**: Development tasks won't interfere with production
3. **Debugging**: Easier to identify which environment a task belongs to
4. **Scalability**: Can scale workers independently per environment

## Notes

- The default environment is `production` if `ENVIRONMENT` is not set
- Always set `ENVIRONMENT` explicitly to avoid confusion
- Workers must be restarted after changing the environment variable
- Both environments can share the same Redis instance (different queue names)

