from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask
from API.celery import app
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Remove invalid/non-using periodic tasks from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show which tasks would be deleted without actually deleting them',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information about each task',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']

        # Get valid periodic task names from celery.py beat_schedule
        valid_schedule_names = set(app.conf.beat_schedule.keys())

        # Get all registered task names from Celery
        registered_tasks = set(app.tasks.keys())
        # Filter out internal Celery tasks (they start with 'celery.')
        registered_tasks = {name for name in registered_tasks if not name.startswith('celery.')}

        # Get all periodic tasks from database
        all_periodic_tasks = PeriodicTask.objects.all()

        invalid_tasks = []
        valid_tasks = []

        for task in all_periodic_tasks:
            task_name = task.name
            task_path = task.task

            # Check if task is in valid beat_schedule
            in_schedule = task_name in valid_schedule_names

            # Check if task path exists in registered tasks
            task_exists = task_path in registered_tasks

            # Task is invalid if:
            # 1. It's not in the beat_schedule (not defined in celery.py)
            # 2. AND the task path doesn't exist in registered tasks (the task function doesn't exist)
            is_invalid = not in_schedule and not task_exists

            if is_invalid:
                invalid_tasks.append({
                    'task': task,
                    'reason': 'Not in beat_schedule and task does not exist',
                    'task_name': task_name,
                    'task_path': task_path,
                })
            else:
                valid_tasks.append({
                    'task': task,
                    'task_name': task_name,
                    'task_path': task_path,
                    'in_schedule': in_schedule,
                    'task_exists': task_exists,
                })

        # Display results
        self.stdout.write(self.style.SUCCESS(f'\n{"=" * 80}'))
        self.stdout.write(self.style.SUCCESS(f'Periodic Task Cleanup Report'))
        self.stdout.write(self.style.SUCCESS(f'{"=" * 80}\n'))

        self.stdout.write(f'Total periodic tasks in database: {all_periodic_tasks.count()}')
        self.stdout.write(f'Valid tasks (in beat_schedule or task exists): {len(valid_tasks)}')
        self.stdout.write(self.style.WARNING(f'Invalid tasks found: {len(invalid_tasks)}\n'))

        if invalid_tasks:
            self.stdout.write(self.style.ERROR('Invalid Tasks to be removed:\n'))
            for idx, invalid in enumerate(invalid_tasks, 1):
                task = invalid['task']
                self.stdout.write(
                    f"  {idx}. Name: {self.style.ERROR(invalid['task_name'])}\n"
                    f"     Task Path: {invalid['task_path']}\n"
                    f"     Reason: {invalid['reason']}\n"
                    f"     Enabled: {task.enabled}\n"
                    f"     Last Run: {task.last_run_at or 'Never'}\n"
                    f"     Total Runs: {task.total_run_count}\n"
                )
        else:
            self.stdout.write(self.style.SUCCESS('No invalid tasks found! All periodic tasks are valid.\n'))

        if verbose and valid_tasks:
            self.stdout.write(self.style.SUCCESS('Valid Tasks:\n'))
            for idx, valid in enumerate(valid_tasks, 1):
                task = valid['task']
                self.stdout.write(
                    f"  {idx}. Name: {valid['task_name']}\n"
                    f"     Task Path: {valid['task_path']}\n"
                    f"     In beat_schedule: {valid['in_schedule']}\n"
                    f"     Task exists: {valid['task_exists']}\n"
                    f"     Enabled: {task.enabled}\n"
                )
            self.stdout.write('')

        # Delete invalid tasks
        if invalid_tasks:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    '\nDRY RUN MODE: No tasks were actually deleted.\n'
                    'Run without --dry-run to delete the invalid tasks.'
                ))
            else:
                deleted_count = 0
                for invalid in invalid_tasks:
                    task = invalid['task']
                    task_name = invalid['task_name']
                    try:
                        task.delete()
                        deleted_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'✓ Deleted: {task_name}')
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'✗ Failed to delete {task_name}: {str(e)}')
                        )

                self.stdout.write(self.style.SUCCESS(
                    f'\nSuccessfully deleted {deleted_count} invalid periodic task(s).'
                ))
        else:
            self.stdout.write(self.style.SUCCESS('\nNo invalid tasks to delete.'))

        self.stdout.write('')

