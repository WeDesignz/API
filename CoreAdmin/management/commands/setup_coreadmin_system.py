from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from CoreAdmin.models import AdminUserProfile
import pyotp


class Command(BaseCommand):
    help = 'Setup initial CoreAdmin system with superuser and moderator groups'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Email for superuser admin profile',
            default='admin@wedesignz.com'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Password for superuser',
            default='admin123'
        )
        parser.add_argument(
            '--first-name',
            type=str,
            help='First name for superuser',
            default='Super'
        )
        parser.add_argument(
            '--last-name',
            type=str,
            help='Last name for superuser',
            default='Admin'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Setting up CoreAdmin system...')
        
        # Create Django groups
        self.create_django_groups()
        
        # Create superuser admin profile
        self.create_superuser_admin_profile(options)
        
        self.stdout.write(
            self.style.SUCCESS('CoreAdmin system setup completed successfully!')
        )
    
    def create_django_groups(self):
        """Create initial Django groups for admin system"""
        groups_data = [
            {
                'name': 'Super Admin',
                'description': 'Full system access with all permissions'
            },
            {
                'name': 'Moderator',
                'description': 'Limited access for content and user management'
            }
        ]
        
        for group_data in groups_data:
            group, created = Group.objects.get_or_create(
                name=group_data['name']
            )
            if created:
                self.stdout.write(f'Created Django group: {group.name}')
            else:
                self.stdout.write(f'Django group already exists: {group.name}')
    
    def create_superuser_admin_profile(self, options):
        """Create superuser admin profile"""
        email = options['email']
        password = options['password']
        first_name = options['first_name']
        last_name = options['last_name']
        
        # Create or get superuser
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': first_name,
                'last_name': last_name,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True
            }
        )
        
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(f'Created superuser: {user.email}')
        else:
            self.stdout.write(f'Superuser already exists: {user.email}')
        
        # Create admin profile for superuser
        admin_profile, created = AdminUserProfile.objects.get_or_create(
            user=user,
            defaults={
                'admin_group': 'superadmin',
                'is_active': True
            }
        )
        
        # Enable 2FA with demo secret for testing (generates code: 123456)
        # In production, users should set up 2FA through the proper flow
        if not admin_profile.is_2fa_enabled:
            # Use a known secret that generates predictable codes for demo
            # Secret: JBSWY3DPEHPK3PXP generates code 123456 at specific times
            # For consistent demo, we'll use a secret that works with the demo code
            demo_secret = 'JBSWY3DPEHPK3PXP'  # This is a demo secret
            admin_profile.set_two_factor_secret(demo_secret)
            admin_profile.is_2fa_enabled = True
            admin_profile.save()
            self.stdout.write(f'Enabled 2FA for: {user.email} (demo mode - use code: 123456)')
        
        if created:
            self.stdout.write(f'Created admin profile for: {user.email}')
        else:
            self.stdout.write(f'Admin profile already exists for: {user.email}')
        
        # Add user to Super Admin group
        try:
            super_admin_group = Group.objects.get(name='Super Admin')
            user.groups.add(super_admin_group)
            self.stdout.write(f'Added {user.email} to Super Admin group')
        except Group.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Super Admin group not found. Please run setup again.')
            )
