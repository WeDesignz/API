"""
Management command to create AdminUserProfile for an existing User.
Usage: python manage.py create_admin_profile <user_id> <admin_group>
Example: python manage.py create_admin_profile 123 moderator
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from CoreAdmin.models import AdminUserProfile


class Command(BaseCommand):
    help = 'Create AdminUserProfile for an existing User'

    def add_arguments(self, parser):
        parser.add_argument('user_id', type=int, help='ID of the User to create profile for')
        parser.add_argument(
            'admin_group',
            type=str,
            choices=['superadmin', 'moderator'],
            help='Admin group to assign (superadmin or moderator)'
        )

    def handle(self, *args, **options):
        user_id = options['user_id']
        admin_group = options['admin_group']

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise CommandError(f'User with id {user_id} does not exist')

        # Check if AdminUserProfile already exists
        if hasattr(user, 'admin_profile'):
            self.stdout.write(
                self.style.WARNING(
                    f'AdminUserProfile already exists for user {user.email}. '
                    f'Current admin_group: {user.admin_profile.admin_group}'
                )
            )
            return

        # Create AdminUserProfile
        admin_profile = AdminUserProfile.objects.create(
            user=user,
            admin_group=admin_group,
            is_active=user.is_active
        )

        # Ensure user is staff
        user.is_staff = True
        user.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created AdminUserProfile for user {user.email} '
                f'({user.get_full_name()}) with admin_group: {admin_group}'
            )
        )

