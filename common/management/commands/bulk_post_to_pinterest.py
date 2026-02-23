from django.core.management.base import BaseCommand
from django.conf import settings
from Catalog.models import Product
from common.models import PinterestPost, PinterestIntegration
from common.tasks import post_design_to_pinterest


class Command(BaseCommand):
    help = 'Bulk post all approved designs to Pinterest that haven\'t been posted yet'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be posted without actually posting',
        )
        parser.add_argument(
            '--force-retry',
            action='store_true',
            help='Retry failed posts as well',
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of designs to process',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force_retry = options['force_retry']
        limit = options.get('limit')
        
        # Check if Pinterest is configured
        integration = PinterestIntegration.get_instance()
        if not integration.is_enabled:
            self.stdout.write(self.style.ERROR('❌ Pinterest integration is disabled. Enable it in settings first.'))
            return
        
        if not integration.is_token_valid():
            self.stdout.write(self.style.ERROR('❌ Pinterest access token is invalid or expired. Please re-authorize.'))
            return
        
        if not integration.board_id:
            self.stdout.write(self.style.ERROR('❌ Pinterest board ID is not set. Please set it in settings.'))
            return
        
        self.stdout.write(self.style.SUCCESS('\n=== Bulk Pinterest Posting ===\n'))
        self.stdout.write(f'📌 Pinterest Board: {integration.board_name or "Unknown"}')
        self.stdout.write(f'   Board ID: {integration.board_id}')
        self.stdout.write(f'   Dry Run: {dry_run}\n')
        
        # Get all approved products (status='active')
        approved_products = Product.objects.filter(
            status='active',
            visibility_status='show'
        )
        
        # Filter products that need posting
        products_to_post = []
        
        for product in approved_products:
            # Check if product has image media (required for Pinterest)
            media_files = product.get_media().filter(media_type='image')
            if not media_files.exists():
                continue  # Skip products without images
            
            # Check PinterestPost status
            try:
                pinterest_post = PinterestPost.objects.get(product=product)
                
                # Skip if already successfully posted
                if pinterest_post.status == 'success':
                    continue
                
                # Include if pending, retrying, or (failed if force_retry)
                if pinterest_post.status in ['pending', 'retrying']:
                    products_to_post.append((product, pinterest_post, 'existing'))
                elif pinterest_post.status == 'failed' and force_retry:
                    products_to_post.append((product, pinterest_post, 'retry'))
                else:
                    continue
                    
            except PinterestPost.DoesNotExist:
                # Product doesn't have a PinterestPost record yet
                products_to_post.append((product, None, 'new'))
        
        # Apply limit if specified
        if limit:
            products_to_post = products_to_post[:limit]
        
        total_count = len(products_to_post)
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('✅ No designs need posting. All approved designs are already posted or have no images.'))
            return
        
        self.stdout.write(f'Found {total_count} design(s) to post:\n')
        
        # Show breakdown
        new_count = sum(1 for _, _, status in products_to_post if status == 'new')
        existing_count = sum(1 for _, _, status in products_to_post if status == 'existing')
        retry_count = sum(1 for _, _, status in products_to_post if status == 'retry')
        
        if new_count > 0:
            self.stdout.write(f'  • New posts: {new_count}')
        if existing_count > 0:
            self.stdout.write(f'  • Pending/Retrying: {existing_count}')
        if retry_count > 0:
            self.stdout.write(f'  • Failed (retrying): {retry_count}')
        
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No posts will be made\n'))
            for i, (product, pinterest_post, status) in enumerate(products_to_post[:10], 1):  # Show first 10
                self.stdout.write(f'{i}. {product.title} (ID: {product.id}) - {status}')
            if total_count > 10:
                self.stdout.write(f'... and {total_count - 10} more')
            return
        
        # Get base URL for links
        base_url = getattr(settings, 'SITE_DOMAIN', 'https://wedesignz.com')
        if not base_url.startswith('http'):
            base_url = f"https://{base_url}"
        
        # Process each product
        created_count = 0
        queued_count = 0
        error_count = 0
        
        self.stdout.write('Processing designs...\n')
        
        for product, pinterest_post, status in products_to_post:
            try:
                # Create or get PinterestPost record
                if pinterest_post is None:
                    pinterest_post, created = PinterestPost.objects.get_or_create(
                        product=product,
                        defaults={'status': 'pending'}
                    )
                    if created:
                        created_count += 1
                
                # Queue the post task
                post_design_to_pinterest.delay(pinterest_post.id, base_url)
                queued_count += 1
                
                if queued_count % 10 == 0:
                    self.stdout.write(f'  Queued {queued_count}/{total_count}...')
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.WARNING(f'  ⚠️  Error for {product.title}: {str(e)}'))
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✅ Successfully queued {queued_count} design(s) for Pinterest posting'))
        if created_count > 0:
            self.stdout.write(f'   Created {created_count} new PinterestPost record(s)')
        if error_count > 0:
            self.stdout.write(self.style.WARNING(f'   ⚠️  {error_count} error(s) occurred'))
        
        self.stdout.write('')
        self.stdout.write('Posts are being processed asynchronously. Check PinterestPost admin or logs for status.')
        self.stdout.write('Note: Pinterest API rate limits apply. Processing may take some time.')

