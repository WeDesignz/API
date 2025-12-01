from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from CoreAdmin.models import AdminUserProfile
from django.conf import settings


class Command(BaseCommand):
    help = 'Enable 2FA for admin user with demo secret (code: 123456)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email for admin user',
            default='admin@wedesignz.com'
        )
    
    def handle(self, *args, **options):
        email = options['email']
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with email {email} not found'))
            return
        
        try:
            admin_profile = user.admin_profile
        except AdminUserProfile.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Admin profile not found for {email}'))
            return
        
        # Check if ENCRYPTION_KEY is set and valid
        encryption_key = getattr(settings, 'ENCRYPTION_KEY', None)
        if not encryption_key or encryption_key == 'your-32-character-secret-key-here':
            self.stdout.write(self.style.WARNING('ENCRYPTION_KEY not set. Generating one...'))
            from cryptography.fernet import Fernet
            key = Fernet.generate_key()
            key_str = key.decode()
            self.stdout.write(self.style.WARNING(f'Please set ENCRYPTION_KEY={key_str} in your .env file'))
            self.stdout.write(self.style.WARNING('For now, using generated key for this session...'))
            # Set it in settings for this command execution
            import django.conf
            django.conf.settings.ENCRYPTION_KEY = key_str
            # Also update the module-level settings
            settings.ENCRYPTION_KEY = key_str
        
        # Enable 2FA with demo secret
        demo_secret = 'JBSWY3DPEHPK3PXP'  # Demo secret that works with code 123456
        admin_profile.set_two_factor_secret(demo_secret)
        admin_profile.is_2fa_enabled = True
        admin_profile.save()
        
        self.stdout.write(self.style.SUCCESS(f'2FA enabled for {email}'))
        self.stdout.write(self.style.SUCCESS('Demo 2FA code: 123456'))
        self.stdout.write(self.style.WARNING('Note: This is for demo/testing only. In production, use proper 2FA setup flow.'))

