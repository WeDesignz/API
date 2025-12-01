from django.core.management.base import BaseCommand
import subprocess
import os
import sys
from django.conf import settings


class Command(BaseCommand):
    help = 'Start Celery worker and beat scheduler'
    
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
    
    def handle(self, *args, **options):
        loglevel = options['loglevel']
        concurrency = options['concurrency']
        
        # Get the project directory
        project_dir = settings.BASE_DIR
        
        if options['all'] or (not options['worker'] and not options['beat'] and not options['flower']):
            self.stdout.write("Starting all Celery services...")
            self.start_worker(loglevel, concurrency)
            self.start_beat(loglevel)
            self.start_flower()
        else:
            if options['worker']:
                self.start_worker(loglevel, concurrency)
            
            if options['beat']:
                self.start_beat(loglevel)
            
            if options['flower']:
                self.start_flower()
    
    def start_worker(self, loglevel, concurrency):
        """Start Celery worker"""
        self.stdout.write("Starting Celery worker...")
        try:
            cmd = [
                'celery', '-A', 'API', 'worker',
                '--loglevel', loglevel,
                '--concurrency', str(concurrency),
                '--pool', 'prefork',
                '--queues', 'default,email,backup',
                '--hostname', 'wedesignz-worker@%h'
            ]
            
            self.stdout.write(f"Running command: {' '.join(cmd)}")
            subprocess.run(cmd, cwd=project_dir)
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Celery worker stopped by user"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to start Celery worker: {str(e)}"))
    
    def start_beat(self, loglevel):
        """Start Celery beat scheduler"""
        self.stdout.write("Starting Celery beat scheduler...")
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
    
    def start_flower(self):
        """Start Flower monitoring tool"""
        self.stdout.write("Starting Flower monitoring tool...")
        try:
            cmd = [
                'celery', '-A', 'API', 'flower',
                '--port', '5555',
                '--broker', settings.CELERY_BROKER_URL
            ]
            
            self.stdout.write(f"Running command: {' '.join(cmd)}")
            self.stdout.write("Flower will be available at: http://localhost:5555")
            subprocess.run(cmd, cwd=project_dir)
            
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Flower stopped by user"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to start Flower: {str(e)}"))
