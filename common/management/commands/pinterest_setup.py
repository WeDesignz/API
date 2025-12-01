from django.core.management.base import BaseCommand
from django.conf import settings
from common.models import PinterestIntegration
from common.pinterest_service import PinterestService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Setup Pinterest integration: get boards, set board ID, check status'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--get-boards',
            action='store_true',
            help='List all Pinterest boards',
        )
        parser.add_argument(
            '--set-board',
            type=str,
            help='Set the board ID for posting',
        )
        parser.add_argument(
            '--status',
            action='store_true',
            help='Check Pinterest integration status',
        )
    
    def handle(self, *args, **options):
        integration = PinterestIntegration.get_instance()
        
        # Check status
        if options['status']:
            self.stdout.write(self.style.SUCCESS('\n=== Pinterest Integration Status ==='))
            self.stdout.write(f"Enabled: {integration.is_enabled}")
            self.stdout.write(f"Configured: {bool(integration.access_token and integration.board_id)}")
            self.stdout.write(f"Token Valid: {integration.is_token_valid()}")
            self.stdout.write(f"Board ID: {integration.board_id or 'Not set'}")
            self.stdout.write(f"Board Name: {integration.board_name or 'Not set'}")
            if integration.last_successful_post:
                self.stdout.write(f"Last Successful Post: {integration.last_successful_post}")
            if integration.last_error:
                self.stdout.write(self.style.WARNING(f"Last Error: {integration.last_error}"))
            return
        
        # Get boards
        if options['get_boards']:
            if not integration.access_token:
                self.stdout.write(self.style.ERROR('Pinterest access token not configured. Please authorize first.'))
                return
            
            try:
                # Use the class method that doesn't require board_id
                boards = PinterestService.get_boards_with_token(integration.access_token)
                
                if not boards:
                    self.stdout.write(self.style.WARNING('No boards found or error occurred.'))
                    return
                
                self.stdout.write(self.style.SUCCESS(f'\n=== Your Pinterest Boards ({len(boards)}) ===\n'))
                for i, board in enumerate(boards, 1):
                    board_id = board.get('id', 'N/A')
                    board_name = board.get('name', 'Unknown')
                    description = board.get('description', '')
                    pin_count = board.get('pin_count', 0)
                    
                    current = ' ← CURRENT' if board_id == integration.board_id else ''
                    self.stdout.write(f"{i}. {board_name}{current}")
                    self.stdout.write(f"   ID: {board_id}")
                    self.stdout.write(f"   Pins: {pin_count}")
                    if description:
                        self.stdout.write(f"   Description: {description[:100]}")
                    self.stdout.write('')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error getting boards: {str(e)}'))
                import traceback
                self.stdout.write(traceback.format_exc())
                if 'not configured' in str(e).lower():
                    self.stdout.write('Please authorize Pinterest first by visiting: /api/pinterest/authorize/')
        
        # Set board ID
        if options['set_board']:
            board_id = options['set_board']
            
            if not integration.access_token:
                self.stdout.write(self.style.ERROR('Pinterest access token not configured. Please authorize first.'))
                return
            
            try:
                # Verify board exists and get its name
                # Use the class method that doesn't require board_id
                boards = PinterestService.get_boards_with_token(integration.access_token)
                
                if not boards:
                    self.stdout.write(self.style.ERROR('Could not fetch boards. Please check your access token.'))
                    return
                
                # Find the board
                board_found = None
                for board in boards:
                    if board.get('id') == board_id:
                        board_found = board
                        break
                
                if not board_found:
                    self.stdout.write(self.style.ERROR(f'Board ID "{board_id}" not found in your boards.'))
                    self.stdout.write('Use --get-boards to see available boards.')
                    return
                
                # Set the board
                integration.board_id = board_id
                integration.board_name = board_found.get('name', '')
                integration.save()
                
                self.stdout.write(self.style.SUCCESS(f'✅ Board set successfully!'))
                self.stdout.write(f'Board: {integration.board_name}')
                self.stdout.write(f'Board ID: {integration.board_id}')
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error setting board: {str(e)}'))
        
        # If no options provided, show help
        if not any([options['get_boards'], options['set_board'], options['status']]):
            self.stdout.write(self.style.WARNING('\nPinterest Setup Commands:'))
            self.stdout.write('  python manage.py pinterest_setup --status        # Check integration status')
            self.stdout.write('  python manage.py pinterest_setup --get-boards     # List all boards')
            self.stdout.write('  python manage.py pinterest_setup --set-board ID   # Set board ID for posting')
            self.stdout.write('\nFirst, authorize Pinterest by visiting: /api/pinterest/authorize/')

