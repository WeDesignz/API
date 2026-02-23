"""
Management command to migrate existing media files to the new user/product directory structure.

This command:
1. Finds all Media objects that are related to Products (via Product:Media relation)
2. Moves files from old location (media/) to new location (<user-id>/<product-id>/)
3. Updates the Media model's file field to point to the new location
4. Handles errors gracefully and provides detailed reporting

Usage:
    python manage.py migrate_media_files
    python manage.py migrate_media_files --dry-run
    python manage.py migrate_media_files --batch-size 100
    python manage.py migrate_media_files --skip-existing
"""

from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.conf import settings
from MediaFiles.models import Media, Relation
from Catalog.models import Product
from common.relations import get_related_for_right
import os


class Command(BaseCommand):
    help = 'Migrate existing media files to user/product directory structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually moving files',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of files to process in each batch (default: 50)',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip files that are already in the correct location',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information for each file',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        skip_existing = options['skip_existing']
        verbose = options['verbose']

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('Media Files Migration Script'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: No files will be moved\n'))

        # Get all Media objects that are related to Products
        self.stdout.write('Finding Media objects related to Products...')
        
        # Get all Product:Media relations
        product_media_relations = Relation.objects.filter(
            relation_type='Product:Media'
        ).select_related().values_list('id_2', flat=True).distinct()
        
        # Get unique Media IDs
        media_ids = list(set(product_media_relations))
        total_media = len(media_ids)
        
        self.stdout.write(f'Found {total_media} Media objects related to Products\n')

        if total_media == 0:
            self.stdout.write(self.style.SUCCESS('No media files to migrate.'))
            return

        # Statistics
        stats = {
            'total': total_media,
            'migrated': 0,
            'skipped': 0,
            'errors': 0,
            'already_correct': 0,
            'missing_file': 0,
            'no_product': 0,
            'no_user': 0,
        }

        error_details = []

        # Process in batches
        for batch_start in range(0, total_media, batch_size):
            batch_end = min(batch_start + batch_size, total_media)
            batch_ids = media_ids[batch_start:batch_end]
            
            self.stdout.write(f'Processing batch {batch_start // batch_size + 1}: files {batch_start + 1}-{batch_end} of {total_media}...')

            for media_id in batch_ids:
                try:
                    media = Media.objects.get(id=media_id)
                    
                    # Check if file exists
                    if not media.file:
                        stats['missing_file'] += 1
                        if verbose:
                            self.stdout.write(
                                self.style.WARNING(f'  Media {media_id}: No file attached')
                            )
                        continue

                    current_path = media.file.name
                    
                    # Check if already in correct location
                    if self._is_in_correct_location(current_path):
                        stats['already_correct'] += 1
                        if skip_existing:
                            stats['skipped'] += 1
                            if verbose:
                                self.stdout.write(
                                    self.style.SUCCESS(f'  Media {media_id}: Already in correct location: {current_path}')
                                )
                            continue
                    
                    # Get related products
                    products = get_related_for_right(media, 'Product:Media', Product)
                    
                    if not products.exists():
                        stats['no_product'] += 1
                        if verbose:
                            self.stdout.write(
                                self.style.WARNING(f'  Media {media_id}: No related Product found')
                            )
                        continue
                    
                    # Use the first product (in case of multiple, which shouldn't happen)
                    product = products.first()
                    
                    # Get user_id from product's created_by
                    if not product.created_by:
                        stats['no_user'] += 1
                        if verbose:
                            self.stdout.write(
                                self.style.WARNING(f'  Media {media_id}: Product {product.id} has no created_by user')
                            )
                        continue
                    
                    user_id = product.created_by.id
                    product_id = product.id
                    
                    # Generate new path
                    filename = os.path.basename(current_path)
                    new_path = f'{user_id}/{product_id}/{filename}'
                    
                    if verbose:
                        self.stdout.write(
                            f'  Media {media_id}: {current_path} -> {new_path}'
                        )
                    
                    if dry_run:
                        stats['migrated'] += 1
                        continue
                    
                    # Check if source file exists
                    if not default_storage.exists(current_path):
                        stats['missing_file'] += 1
                        error_details.append({
                            'media_id': media_id,
                            'error': f'Source file not found: {current_path}'
                        })
                        if verbose:
                            self.stdout.write(
                                self.style.ERROR(f'    ERROR: Source file not found')
                            )
                        continue
                    
                    # Check if destination already exists
                    if default_storage.exists(new_path):
                        if skip_existing:
                            stats['skipped'] += 1
                            if verbose:
                                self.stdout.write(
                                    self.style.WARNING(f'    SKIP: Destination already exists')
                                )
                            continue
                        else:
                            # Generate unique filename
                            base, ext = os.path.splitext(filename)
                            counter = 1
                            while default_storage.exists(new_path):
                                new_filename = f'{base}_{counter}{ext}'
                                new_path = f'{user_id}/{product_id}/{new_filename}'
                                counter += 1
                    
                    # Copy file to new location
                    try:
                        with default_storage.open(current_path, 'rb') as source_file:
                            default_storage.save(new_path, source_file)
                        
                        # Update Media model
                        media.file.name = new_path
                        media.save(update_fields=['file'])
                        
                        # Delete old file (only if it's in the old media/ directory)
                        if current_path.startswith('media/'):
                            try:
                                default_storage.delete(current_path)
                            except Exception as e:
                                pass
                        
                        stats['migrated'] += 1
                        if verbose:
                            self.stdout.write(
                                self.style.SUCCESS(f'    ✓ Migrated successfully')
                            )
                    
                    except Exception as e:
                        stats['errors'] += 1
                        error_msg = f'Failed to migrate: {str(e)}'
                        error_details.append({
                            'media_id': media_id,
                            'old_path': current_path,
                            'new_path': new_path,
                            'error': error_msg
                        })
                        if verbose:
                            self.stdout.write(
                                self.style.ERROR(f'    ✗ {error_msg}')
                            )
                
                except Media.DoesNotExist:
                    stats['errors'] += 1
                    error_details.append({
                        'media_id': media_id,
                        'error': 'Media object not found'
                    })
                    if verbose:
                        self.stdout.write(
                            self.style.ERROR(f'  Media {media_id}: Not found')
                        )
                
                except Exception as e:
                    stats['errors'] += 1
                    error_msg = f'Unexpected error: {str(e)}'
                    error_details.append({
                        'media_id': media_id,
                        'error': error_msg
                    })
                    if verbose:
                        self.stdout.write(
                            self.style.ERROR(f'  Media {media_id}: {error_msg}')
                        )

        # Print summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Migration Summary'))
        self.stdout.write('=' * 80 + '\n')
        
        self.stdout.write(f'Total Media objects: {stats["total"]}')
        self.stdout.write(self.style.SUCCESS(f'✓ Successfully migrated: {stats["migrated"]}'))
        
        if stats['already_correct'] > 0:
            self.stdout.write(self.style.SUCCESS(f'✓ Already in correct location: {stats["already_correct"]}'))
        
        if stats['skipped'] > 0:
            self.stdout.write(self.style.WARNING(f'⊘ Skipped: {stats["skipped"]}'))
        
        if stats['missing_file'] > 0:
            self.stdout.write(self.style.WARNING(f'⚠ Missing files: {stats["missing_file"]}'))
        
        if stats['no_product'] > 0:
            self.stdout.write(self.style.WARNING(f'⚠ No related Product: {stats["no_product"]}'))
        
        if stats['no_user'] > 0:
            self.stdout.write(self.style.WARNING(f'⚠ Product has no user: {stats["no_user"]}'))
        
        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f'✗ Errors: {stats["errors"]}'))
        
        if error_details and verbose:
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.ERROR('Error Details'))
            self.stdout.write('=' * 80 + '\n')
            for idx, error in enumerate(error_details[:20], 1):  # Show first 20 errors
                self.stdout.write(f'{idx}. Media ID {error["media_id"]}: {error["error"]}')
            if len(error_details) > 20:
                self.stdout.write(f'... and {len(error_details) - 20} more errors')
        
        if dry_run:
            self.stdout.write('\n' + self.style.WARNING(
                'DRY RUN COMPLETE: No files were actually moved.\n'
                'Run without --dry-run to perform the migration.'
            ))
        else:
            self.stdout.write('\n' + self.style.SUCCESS('Migration completed!'))
        
        self.stdout.write('')

    def _is_in_correct_location(self, file_path):
        """
        Check if a file path is already in the correct location format.
        Correct format: <user-id>/<product-id>/<filename>
        """
        # Remove leading slash if present
        path = file_path.lstrip('/')
        
        # Split path into parts
        parts = path.split('/')
        
        # Should have at least 3 parts: user_id, product_id, filename
        if len(parts) < 3:
            return False
        
        # Check if first two parts are numeric (user_id and product_id)
        try:
            int(parts[0])  # user_id
            int(parts[1])  # product_id
            return True
        except ValueError:
            return False

