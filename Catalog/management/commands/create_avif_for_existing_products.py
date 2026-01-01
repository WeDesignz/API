"""
Management command to create AVIF versions for existing product images.

This command processes all existing products and creates AVIF versions for:
- JPG/JPEG files -> WDG00000001_JPG.avif
- PNG files -> WDG00000001_PNG.avif
- MOCKUP files -> WDG00000001_MOCKUP.avif

AVIF files are only created if they don't already exist.

Usage:
    python manage.py create_avif_for_existing_products
    python manage.py create_avif_for_existing_products --dry-run
    python manage.py create_avif_for_existing_products --product-id 123
    python manage.py create_avif_for_existing_products --batch-size 100
"""

from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from Catalog.models import Product
from MediaFiles.models import Media
from common.avif_converter import create_avif_from_media_file
from common.relations import get_related
import os
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create AVIF versions for existing product images (only if not already exist)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be converted without actually creating AVIF files',
        )
        parser.add_argument(
            '--product-id',
            type=int,
            help='Process only a specific product ID',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of products to process in each batch (default: 50)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information for each file',
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=['draft', 'active', 'inactive', 'deleted', 'all'],
            default='all',
            help='Filter products by status (default: all)',
        )

    def check_avif_exists(self, file_dir, product_number, is_mockup, is_jpg, is_png):
        """Check if AVIF file already exists"""
        if is_mockup:
            avif_filename = f'{product_number}_MOCKUP.avif'
        elif is_jpg:
            avif_filename = f'{product_number}_JPG.avif'
        else:  # PNG
            avif_filename = f'{product_number}_PNG.avif'
        
        avif_path = os.path.join(file_dir, avif_filename)
        return default_storage.exists(avif_path), avif_filename

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        product_id = options.get('product_id')
        batch_size = options['batch_size']
        verbose = options['verbose']
        status_filter = options['status']

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('AVIF Conversion for Existing Products'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

        # Check AVIF support upfront
        from common.avif_converter import is_avif_supported
        import sys
        
        # Check if pillow-avif-plugin is installed
        try:
            import pillow_avif
            plugin_installed = True
        except ImportError:
            plugin_installed = False
        
        if not is_avif_supported():
            self.stdout.write(self.style.ERROR('\n❌ AVIF format is not supported!\n'))
            
            if not plugin_installed:
                self.stdout.write(self.style.WARNING('1. Install the Python package:\n'))
                self.stdout.write('   pip install pillow-avif-plugin\n')
            else:
                self.stdout.write(self.style.SUCCESS('✓ pillow-avif-plugin is installed\n'))
                self.stdout.write(self.style.WARNING('However, AVIF support is still not working.\n'))
                self.stdout.write(self.style.WARNING('This usually means system libraries are missing.\n'))
            
            self.stdout.write(self.style.WARNING('\n2. Install system libraries (required):\n'))
            self.stdout.write('   Ubuntu/Debian:\n')
            self.stdout.write('     sudo apt-get update\n')
            self.stdout.write('     sudo apt-get install -y libavif-dev libavif-bin\n')
            self.stdout.write('\n   CentOS/RHEL:\n')
            self.stdout.write('     sudo yum install -y libavif-devel\n')
            self.stdout.write('\n   After installing system libraries, you may need to:\n')
            self.stdout.write('     - Restart your Python process/application\n')
            self.stdout.write('     - Or reinstall pillow-avif-plugin: pip install --force-reinstall pillow-avif-plugin\n')
            self.stdout.write('\n3. Verify installation:\n')
            self.stdout.write('   python -c "from PIL import Image; img = Image.new(\'RGB\', (1,1)); img.save(\'/tmp/test.avif\', format=\'AVIF\')"\n')
            self.stdout.write('\nIf the test succeeds, run this command again.\n')
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: No AVIF files will be created\n'))

        # Get products to process
        if product_id:
            products = Product.objects.filter(id=product_id)
            if not products.exists():
                self.stdout.write(self.style.ERROR(f'Product with ID {product_id} not found'))
                return
        else:
            products = Product.objects.all()
            if status_filter != 'all':
                products = products.filter(status=status_filter)

        total_products = products.count()
        self.stdout.write(f'Found {total_products} product(s) to process\n')

        # Statistics
        stats = {
            'total_products': total_products,
            'processed_products': 0,
            'skipped_products': 0,
            'total_images': 0,
            'created_avif': 0,
            'skipped_avif': 0,
            'errors': 0,
            'error_details': []
        }

        # Process products in batches
        for batch_start in range(0, total_products, batch_size):
            batch_products = products[batch_start:batch_start + batch_size]
            
            for product in batch_products:
                try:
                    self.stdout.write(f'\nProcessing Product ID {product.id}: {product.title}')
                    
                    # Get product number
                    if not product.product_number:
                        self.stdout.write(self.style.WARNING(f'  ⚠ Product {product.id} has no product_number, skipping'))
                        stats['skipped_products'] += 1
                        continue
                    
                    product_number = product.product_number
                    
                    # Get all media files for this product
                    try:
                        media_list = get_related(product, 'Product:Media', Media)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'  ✗ Error getting media: {e}'))
                        stats['errors'] += 1
                        stats['error_details'].append({
                            'product_id': product.id,
                            'error': f'Error getting media: {e}'
                        })
                        continue
                    
                    if not media_list:
                        if verbose:
                            self.stdout.write(f'  ℹ No media files found')
                        stats['skipped_products'] += 1
                        continue
                    
                    # Process each media file
                    product_images_processed = 0
                    product_avif_created = 0
                    product_avif_skipped = 0
                    
                    for media in media_list:
                        try:
                            if not media.file:
                                continue
                            
                            file_name = media.file.name if hasattr(media.file, 'name') else ''
                            if not file_name:
                                continue
                            
                            file_name_lower = file_name.lower()
                            
                            # Check if it's a JPG, PNG, or MOCKUP file
                            is_jpg = file_name_lower.endswith(('.jpg', '.jpeg'))
                            is_png = file_name_lower.endswith('.png')
                            
                            # Check if it's a mockup
                            base_name = os.path.splitext(os.path.basename(file_name_lower))[0]
                            is_mockup = base_name == 'mockup' or 'mockup' in file_name_lower
                            
                            # Also check metadata
                            if not is_mockup:
                                try:
                                    from MediaFiles.models import Relation
                                    relation = Relation.objects.filter(
                                        relation_type='Product:Media',
                                        id_1=product.pk,
                                        id_2=media.pk
                                    ).first()
                                    if relation and relation.meta:
                                        meta_str = str(relation.meta).lower()
                                        if 'mockup' in meta_str or '"is_mockup":true' in meta_str:
                                            is_mockup = True
                                except Exception:
                                    pass
                            
                            # Only process JPG, PNG, or MOCKUP files
                            if not (is_jpg or is_png or is_mockup):
                                continue
                            
                            stats['total_images'] += 1
                            product_images_processed += 1
                            
                            # Get file directory
                            file_dir = os.path.dirname(file_name)
                            
                            # Check if AVIF already exists
                            avif_exists, avif_filename = self.check_avif_exists(
                                file_dir, product_number, is_mockup, is_jpg, is_png
                            )
                            
                            if avif_exists:
                                if verbose:
                                    self.stdout.write(f'  ⊘ AVIF already exists: {avif_filename} (skipping)')
                                stats['skipped_avif'] += 1
                                product_avif_skipped += 1
                                continue
                            
                            # Create AVIF version (only if it doesn't exist)
                            if not dry_run:
                                try:
                                    media_file_path = media.file.name
                                    avif_path, avif_media_obj = create_avif_from_media_file(
                                        media_file_path,
                                        product_number,
                                        is_mockup=is_mockup,
                                        product=product,
                                        created_by=product.created_by if hasattr(product, 'created_by') else None
                                    )
                                    
                                    if avif_path:
                                        if verbose:
                                            self.stdout.write(self.style.SUCCESS(f'  ✓ Created AVIF: {os.path.basename(avif_path)}'))
                                        if avif_media_obj:
                                            if verbose:
                                                self.stdout.write(self.style.SUCCESS(f'  ✓ Linked AVIF to product via Media object {avif_media_obj.id}'))
                                        stats['created_avif'] += 1
                                        product_avif_created += 1
                                    else:
                                        self.stdout.write(self.style.WARNING(f'  ⚠ Failed to create AVIF for {file_name}'))
                                        stats['errors'] += 1
                                        stats['error_details'].append({
                                            'product_id': product.id,
                                            'media_id': media.id,
                                            'file_name': file_name,
                                            'error': 'AVIF conversion returned None'
                                        })
                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(f'  ✗ Error creating AVIF for {file_name}: {e}'))
                                    stats['errors'] += 1
                                    stats['error_details'].append({
                                        'product_id': product.id,
                                        'media_id': media.id,
                                        'file_name': file_name,
                                        'error': str(e)
                                    })
                            else:
                                # Dry run - just show what would be created
                                if verbose:
                                    self.stdout.write(f'  [DRY RUN] Would create: {avif_filename}')
                                stats['created_avif'] += 1
                                product_avif_created += 1
                        
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'  ✗ Error processing media {getattr(media, "id", "unknown")}: {e}'))
                            stats['errors'] += 1
                            stats['error_details'].append({
                                'product_id': product.id,
                                'media_id': getattr(media, 'id', None),
                                'error': str(e)
                            })
                    
                    if product_images_processed > 0:
                        if verbose:
                            self.stdout.write(f'  Summary: {product_avif_created} AVIF created, {product_avif_skipped} skipped (already exist)')
                        stats['processed_products'] += 1
                    else:
                        stats['skipped_products'] += 1
                
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'\n✗ Error processing product {product.id}: {e}'))
                    stats['errors'] += 1
                    stats['error_details'].append({
                        'product_id': product.id,
                        'error': str(e)
                    })
                    stats['skipped_products'] += 1
            
            # Progress update
            processed = min(batch_start + batch_size, total_products)
            self.stdout.write(f'\nProgress: {processed}/{total_products} products processed')
        
        # Final summary
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('Conversion Summary'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'Total Products: {stats["total_products"]}')
        self.stdout.write(f'Processed Products: {stats["processed_products"]}')
        self.stdout.write(f'Skipped Products: {stats["skipped_products"]}')
        self.stdout.write(f'Total Images Found: {stats["total_images"]}')
        self.stdout.write(self.style.SUCCESS(f'AVIF Files Created: {stats["created_avif"]}'))
        self.stdout.write(f'AVIF Files Skipped (already exist): {stats["skipped_avif"]}')
        self.stdout.write(self.style.ERROR(f'Errors: {stats["errors"]}'))
        
        if stats['errors'] > 0 and verbose:
            self.stdout.write('\nError Details:')
            for error in stats['error_details'][:10]:  # Show first 10 errors
                self.stdout.write(f'  - Product {error.get("product_id", "unknown")}: {error.get("error", "Unknown error")}')
            if len(stats['error_details']) > 10:
                self.stdout.write(f'  ... and {len(stats["error_details"]) - 10} more errors')
        
        self.stdout.write('\n')

