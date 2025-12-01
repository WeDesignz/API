from django.core.management.base import BaseCommand
from cryptography.fernet import Fernet


class Command(BaseCommand):
    help = 'Generate a valid Fernet encryption key for ENCRYPTION_KEY setting'
    
    def handle(self, *args, **options):
        # Generate a new Fernet key
        key = Fernet.generate_key()
        key_str = key.decode()
        
        self.stdout.write(self.style.SUCCESS('Generated Fernet encryption key:'))
        self.stdout.write(self.style.SUCCESS(key_str))
        self.stdout.write('')
        self.stdout.write('Add this to your .env file:')
        self.stdout.write(self.style.WARNING(f'ENCRYPTION_KEY={key_str}'))
        self.stdout.write('')
        self.stdout.write('Note: Keep this key secure and do not share it publicly!')

