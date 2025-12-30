from django.core.management.base import BaseCommand
import subprocess
import os
import sys
import threading
import time
from django.conf import settings


class Command(BaseCommand):
    help = 'Start Celery worker, beat scheduler, and Flower monitoring'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--worker',
            action='store_true',
            help='Start only the Celery worker',
        )
        parser.add_argument(
            '--beat',
            action='store_true',
            help='Start only the Celery beat scheduler',
        )
        parser.add_argument(
            '--flower',
            action='store_true',
            help='Start only the Flower monitoring tool',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Start all Celery services (worker, beat, flower)',
        )
        parser.add_argument(
            '--loglevel',
            type=str,
            default='info',
            help='Set the log level (debug, info, warning, error)',
        )
        parser.add_argument(
            '--concurrency',
            type=int,
            default=4,
            help='Number of worker processes',
        )
        parser.add_argument(
            '--flower-port',
            type=int,
            default=5555,
            help='Port for Flower web interface (default: 5555)',
        )
        parser.add_argument(
            '--flower-auth',
            type=str,
            help='Flower basic auth (format: username:password)',
        )
    
    def handle(self, *args, **options):
        loglevel = options['loglevel']
        concurrency = options['concurrency']
        flower_port = options['flower_port']
        flower_auth = options.get('flower_auth')
        
        # Get the project directory
        project_dir = settings.BASE_DIR
        
        if options['all'] or (not options['worker'] and not options['beat'] and not options['flower']):
            self.stdout.write(self.style.SUCCESS("Starting all Celery services..."))
            self.stdout.write(self.style.WARNING(
                "Note: For production, run each service separately or use a process manager like supervisor/systemd"
            ))
            
            # Start Flower in background thread
            flower_thread = threading.Thread(
                target=self.start_flower,
                args=(flower_port, flower_auth),
                daemon=True
            )
            flower_thread.start()
            time.sleep(2)  # Give Flower time to start
            
            # Start worker and beat in foreground (they will block)
            # In production, these should be run separately
            self.stdout.write(self.style.WARNING(
                "Starting worker and beat in foreground. Flower is running in background."
            ))
            self.stdout.write(self.style.SUCCESS(
                f"Flower monitoring available at: http://localhost:{flower_port}"
            ))
            
            # Note: This will block on worker. For true parallel execution, use separate terminals or process manager
            self.stdout.write(self.style.WARNING(
                "For parallel execution, run services in separate terminals:"
            ))
            self.stdout.write("  Terminal 1: python manage.py start_celery --worker")
            self.stdout.write("  Terminal 2: python manage.py start_celery --beat")
            self.stdout.write(f"  Terminal 3: python manage.py start_celery --flower --flower-port={flower_port}")
            
            self.start_worker(loglevel, concurrency)
        else:
            if options['worker']:
                self.start_worker(loglevel, concurrency)
            
            if options['beat']:
                self.start_beat(loglevel)
            
            if options['flower']:
                self.start_flower(flower_port, flower_auth)
    
    def start_worker(self, loglevel, concurrency):
        """Start Celery worker"""
        self.stdout.write(self.style.SUCCESS("Starting Celery worker..."))
        try:
            # Determine environment and queue
            environment = os.environ.get('ENVIRONMENT', 'production').lower()
            if environment == 'production':
                queue_name = 'production'
                hostname = 'worker-prod@%h'
            else:
                queue_name = 'devapi'
                hostname = 'worker-dev@%h'
            
            self.stdout.write(self.style.SUCCESS(f"Environment: {environment.upper()}"))
            self.stdout.write(self.style.SUCCESS(f"Queue: {queue_name}"))
            
            cmd = [
                'celery', '-A', 'API', 'worker',
                '--loglevel', loglevel,
                '--concurrency', str(concurrency),
                '--pool', 'prefork',
                '--queues', queue_name,
                '--hostname', hostname
            ]
            
            self.stdout.write(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, cwd=project_dir)
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Celery worker stopped by user"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to start Celery worker: {str(e)}"))
    
    def start_beat(self, loglevel):
        """Start Celery beat scheduler"""
        self.stdout.write(self.style.SUCCESS("Starting Celery beat scheduler..."))
        try:
            cmd = [
                'celery', '-A', 'API', 'beat',
                '--loglevel', loglevel,
                '--scheduler', 'django_celery_beat.schedulers:DatabaseScheduler'
            ]
            
            self.stdout.write(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, cwd=project_dir)
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Celery beat stopped by user"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to start Celery beat: {str(e)}"))
    
    def start_flower(self, port=5555, auth=None):
        """Start Flower monitoring tool"""
        self.stdout.write(self.style.SUCCESS("Starting Flower monitoring tool..."))
        try:
            cmd = [
                'celery', '-A', 'API', 'flower',
                '--port', str(port),
                '--broker', settings.CELERY_BROKER_URL
            ]
            
            # Add authentication if provided
            if auth:
                cmd.extend(['--basic_auth', auth])
                self.stdout.write(self.style.SUCCESS(f"Flower authentication enabled: {auth.split(':')[0]}"))
            
            self.stdout.write(f"Running command: {' '.join(cmd)}")
            self.stdout.write(self.style.SUCCESS(f"Flower will be available at: http://localhost:{port}"))
            self.stdout.write(self.style.SUCCESS(
                "Flower provides real-time monitoring of:\n"
                "  - Scheduled tasks (tasks waiting to be executed)\n"
                "  - Reserved tasks (tasks assigned to workers but not started)\n"
                "  - Active tasks (tasks currently being executed)\n"
                "  - Task history, worker status, and performance metrics"
            ))
            subprocess.run(cmd, cwd=settings.BASE_DIR)
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Flower stopped by user"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to start Flower: {str(e)}"))
