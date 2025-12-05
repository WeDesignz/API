# Celery Flower - Real-Time Monitoring Guide

## Quick Start

### Start Flower

```bash
# Simple start
python manage.py start_celery --flower

# With authentication (recommended)
python manage.py start_celery --flower --flower-auth=admin:yourpassword

# Custom port
python manage.py start_celery --flower --flower-port=5556
```

### Access Flower

Open your browser and navigate to: **http://localhost:5555**

## Real-Time Monitoring of Task States

Flower provides real-time monitoring of all three task states:

### 1. Scheduled Tasks (PENDING)
- **What**: Tasks waiting in the queue to be executed
- **Where to see**: 
  - Dashboard → "Scheduled" count
  - Tasks page → Filter by "Scheduled" state
- **Meaning**: Tasks have been sent to the broker but not yet picked up by workers

### 2. Reserved Tasks (RESERVED)
- **What**: Tasks assigned to workers but not yet started
- **Where to see**:
  - Dashboard → "Reserved" count
  - Tasks page → Filter by "Reserved" state
- **Meaning**: Tasks are in the worker's prefetch queue, waiting to start execution

### 3. Active Tasks (ACTIVE)
- **What**: Tasks currently being executed by workers
- **Where to see**:
  - Dashboard → "Active" count
  - Tasks page → Filter by "Active" state
  - Workers page → Click on a worker to see its active tasks
- **Meaning**: Tasks are currently running

## Key Features

### Dashboard Overview
- **Workers**: Number of online/offline workers
- **Tasks**: Total tasks processed, active, scheduled, reserved
- **System**: CPU and memory usage
- **Task Rate**: Tasks per second

### Task Management
- **View Tasks**: All tasks with filters by name, state, worker
- **Task Details**: 
  - Arguments and keyword arguments
  - Result and traceback (if failed)
  - Retry information
  - Execution time
- **Task Actions**:
  - Revoke tasks
  - Retry failed tasks
  - View task results

### Worker Management
- **Worker Status**: Online/offline, active tasks count
- **Worker Stats**: 
  - Total tasks processed
  - Task success/failure rate
  - Average task execution time
- **Worker Actions**:
  - Shutdown workers
  - Restart workers
  - View worker logs

### Monitoring & Analytics
- **Task Rate Graph**: Real-time tasks per second
- **Task Execution Time**: Average execution time over time
- **Success/Failure Rate**: Task success percentage
- **Worker Performance**: Individual worker statistics

## Common Use Cases

### Monitor All Task States
1. Open Flower dashboard
2. Check the "Tasks" section for counts:
   - **Scheduled**: Tasks waiting
   - **Reserved**: Tasks assigned but not started
   - **Active**: Tasks currently running

### Find Stuck Tasks
1. Go to Tasks page
2. Filter by "Active" state
3. Check execution time - if unusually long, task may be stuck
4. Click on task to see details
5. Revoke if necessary

### Monitor Worker Health
1. Go to Workers page
2. Check worker status (should be "Online")
3. Review processed tasks count
4. Check success/failure rate
5. View active tasks per worker

### Debug Failed Tasks
1. Go to Tasks page
2. Filter by "Failed" state
3. Click on failed task
4. View traceback to see error
5. Retry task if appropriate

### Monitor Queue Backlog
1. Check Dashboard "Scheduled" count
2. If high, workers may be overloaded
3. Consider:
   - Increasing worker concurrency
   - Adding more workers
   - Optimizing slow tasks

## Production Setup

### Recommended: Run Services Separately

```bash
# Terminal 1: Worker
python manage.py start_celery --worker --concurrency=8

# Terminal 2: Beat Scheduler
python manage.py start_celery --beat

# Terminal 3: Flower (with auth)
python manage.py start_celery --flower --flower-auth=admin:securepassword
```

### Using Supervisor (Production)

Create `/etc/supervisor/conf.d/flower.conf`:

```ini
[program:flower]
command=/path/to/venv/bin/celery -A API flower --port=5555 --basic_auth=admin:securepassword
directory=/path/to/project
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/flower.log
```

Then:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start flower
```

### Using Systemd (Production)

Create `/etc/systemd/system/flower.service`:

```ini
[Unit]
Description=Celery Flower
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/project
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A API flower --port=5555 --basic_auth=admin:securepassword
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable flower
sudo systemctl start flower
```

## API Endpoints

Flower provides a REST API for programmatic access:

```bash
# Get all workers
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

# Get worker stats
curl http://localhost:5555/api/worker/stats/<worker-name>
```

## Troubleshooting

### Flower Not Starting
- Check if port 5555 is already in use: `lsof -i :5555`
- Verify Redis is running: `redis-cli ping`
- Check Celery configuration in settings.py

### No Tasks Showing
- Ensure `CELERY_WORKER_SEND_TASK_EVENTS = True` in settings
- Ensure `CELERY_TASK_SEND_SENT_EVENT = True` in settings
- Restart workers after changing settings

### Authentication Not Working
- Use format: `username:password` (no spaces)
- For API access, use HTTP Basic Auth:
  ```bash
  curl -u username:password http://localhost:5555/api/workers
  ```

### High Memory Usage
- Flower stores task history in memory
- Limit task history: `celery -A API flower --max_tasks=1000`
- Or use persistent storage (requires additional configuration)

## Best Practices

1. **Always use authentication in production**
2. **Run Flower on a separate process/terminal** for better stability
3. **Monitor regularly** to catch issues early
4. **Set up alerts** for high failure rates or stuck tasks
5. **Review task history** periodically to identify slow tasks
6. **Use Flower API** for integration with monitoring systems (Prometheus, Grafana, etc.)

## Additional Resources

- [Flower Documentation](https://flower.readthedocs.io/)
- [Celery Monitoring Guide](https://docs.celeryproject.org/en/stable/userguide/monitoring.html)
- See `celery.md` for complete Celery configuration guide

