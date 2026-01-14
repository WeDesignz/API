from django.core.management.base import BaseCommand
from common.models import PinterestIntegration, PinterestPost
from common.pinterest_service import PinterestService
import logging
import time

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Delete all pins from the configured Pinterest board'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--board-id',
            type=str,
            help='Specific board ID to delete pins from (defaults to configured board)',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0.5,
            help='Delay between deletions in seconds (default: 0.5) to respect rate limits',
        )
        parser.add_argument(
            '--update-db',
            action='store_true',
            help='Also update PinterestPost records in database to reset status to pending (allows reposting)',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip confirmation prompt (use with caution!)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        board_id = options.get('board_id')
        delay = options.get('delay', 0.5)
        update_db = options.get('update_db', False)
        skip_confirm = options.get('yes', False)
        
        # Check if Pinterest is configured
        integration = PinterestIntegration.get_instance()
        if not integration.is_enabled:
            self.stdout.write(self.style.ERROR('❌ Pinterest integration is disabled. Enable it in settings first.'))
            return
        
        if not integration.access_token:
            self.stdout.write(self.style.ERROR('❌ Pinterest access token not configured. Please authorize first.'))
            return
        
        if not integration.is_token_valid():
            self.stdout.write(self.style.ERROR('❌ Pinterest access token is invalid or expired. Please re-authorize.'))
            return
        
        # Use provided board_id or default to configured board
        target_board_id = board_id or integration.board_id
        if not target_board_id:
            self.stdout.write(self.style.ERROR('❌ Pinterest board ID is not set. Please set it in settings or use --board-id.'))
            return
        
        self.stdout.write(self.style.WARNING('\n=== Delete All Pinterest Posts ===\n'))
        self.stdout.write(f'📌 Pinterest Board: {integration.board_name or "Unknown"}')
        self.stdout.write(f'   Board ID: {target_board_id}')
        self.stdout.write(f'   Dry Run: {dry_run}')
        self.stdout.write(f'   Update DB: {update_db}')
        self.stdout.write(f'   Delay: {delay}s\n')
        
        if not dry_run and not skip_confirm:
            confirm = input('⚠️  WARNING: This will delete ALL pins from the board. Type "DELETE" to confirm: ')
            if confirm != 'DELETE':
                self.stdout.write(self.style.ERROR('❌ Deletion cancelled.'))
                return
        
        try:
            # Initialize service
            service = PinterestService()
            
            # Get all pins from the board
            self.stdout.write('📥 Fetching pins from board...')
            pins = service.get_pins(board_id=target_board_id)
            
            if pins is None:
                self.stdout.write(self.style.ERROR('❌ Failed to fetch pins. Check server logs for details.'))
                return
            
            total_pins = len(pins)
            
            if total_pins == 0:
                self.stdout.write(self.style.SUCCESS('✅ No pins found on the board.'))
                return
            
            self.stdout.write(self.style.SUCCESS(f'✅ Found {total_pins} pin(s) on the board.\n'))
            
            if dry_run:
                self.stdout.write(self.style.WARNING('DRY RUN MODE - No pins will be deleted\n'))
                for i, pin in enumerate(pins[:10], 1):  # Show first 10
                    pin_id = pin.get('id', 'N/A')
                    title = pin.get('title', 'Untitled')
                    self.stdout.write(f'{i}. {title} (ID: {pin_id})')
                if total_pins > 10:
                    self.stdout.write(f'... and {total_pins - 10} more')
                return
            
            # Delete each pin
            self.stdout.write('🗑️  Deleting pins...\n')
            deleted_count = 0
            failed_count = 0
            failed_pins = []
            
            for i, pin in enumerate(pins, 1):
                pin_id = pin.get('id')
                title = pin.get('title', 'Untitled')
                
                if not pin_id:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  Pin {i}/{total_pins}: No ID found, skipping'))
                    failed_count += 1
                    continue
                
                success = service.delete_pin(pin_id)
                
                if success:
                    deleted_count += 1
                    if i % 10 == 0 or i == total_pins:
                        self.stdout.write(f'  ✅ Deleted {i}/{total_pins}... ({deleted_count} successful)')
                else:
                    failed_count += 1
                    failed_pins.append({'id': pin_id, 'title': title})
                    self.stdout.write(self.style.WARNING(f'  ⚠️  Failed to delete: {title} (ID: {pin_id})'))
                
                # Rate limiting delay
                if i < total_pins:
                    time.sleep(delay)
            
            # Update database records if requested
            if update_db:
                self.stdout.write('\n📝 Updating database records...')
                updated_count = 0
                
                # Get all pin IDs that were deleted successfully
                deleted_pin_ids = {pin['id'] for pin in pins if pin.get('id') and pin['id'] not in [fp['id'] for fp in failed_pins]}
                
                # Find PinterestPost records that reference deleted pins
                pinterest_posts = PinterestPost.objects.filter(
                    status='success'
                ).exclude(pins_data={}).exclude(pin_id__isnull=True)
                
                for post in pinterest_posts:
                    updated = False
                    
                    # Check legacy pin_id field
                    if post.pin_id and post.pin_id in deleted_pin_ids:
                        post.pin_id = None
                        post.pin_url = None
                        updated = True
                    
                    # Check pins_data field
                    if post.pins_data and isinstance(post.pins_data, dict):
                        for key, pin_data in post.pins_data.items():
                            if isinstance(pin_data, dict) and pin_data.get('id') in deleted_pin_ids:
                                post.pins_data[key] = {}
                                updated = True
                    
                    # If any pins were deleted, reset the record
                    if updated:
                        # Check if all pins in pins_data are now empty
                        all_empty = True
                        if post.pins_data and isinstance(post.pins_data, dict):
                            for pin_data in post.pins_data.values():
                                if isinstance(pin_data, dict) and pin_data.get('id'):
                                    all_empty = False
                                    break
                        
                        if all_empty or (not post.pin_id and not post.pins_data):
                            post.pins_data = {}
                            post.status = 'pending'  # Reset to pending so it can be reposted
                            post.error_message = None
                            post.save(update_fields=['pin_id', 'pin_url', 'pins_data', 'status', 'error_message'])
                            updated_count += 1
                        else:
                            # Partial deletion - some pins still exist
                            post.save(update_fields=['pin_id', 'pin_url', 'pins_data'])
                            updated_count += 1
                
                self.stdout.write(self.style.SUCCESS(f'✅ Updated {updated_count} database record(s)'))
                self.stdout.write('   Status reset to "pending" - these can now be reposted using bulk_post_to_pinterest')
            
            # Summary
            self.stdout.write('\n' + '='*50)
            self.stdout.write(self.style.SUCCESS(f'✅ Successfully deleted: {deleted_count}/{total_pins}'))
            if failed_count > 0:
                self.stdout.write(self.style.WARNING(f'⚠️  Failed: {failed_count}/{total_pins}'))
                if failed_pins:
                    self.stdout.write('\nFailed pins:')
                    for pin in failed_pins[:10]:  # Show first 10
                        self.stdout.write(f'  - {pin["title"]} (ID: {pin["id"]})')
                    if len(failed_pins) > 10:
                        self.stdout.write(f'  ... and {len(failed_pins) - 10} more')
            
            if update_db:
                self.stdout.write('\n💡 Tip: Run "python manage.py bulk_post_to_pinterest" to repost all designs.')
            
            self.stdout.write('')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {str(e)}'))
            logger.error(f'Error deleting Pinterest posts: {str(e)}', exc_info=True)
            import traceback
            self.stdout.write(traceback.format_exc())


