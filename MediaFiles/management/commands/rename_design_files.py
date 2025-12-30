"""
Management command to rename design files using product_number.

This command:
1. Iterates through all user/designs/product directories in media root
2. For each product directory, gets the product_number from the database
3. Renames files to use product_number format:
   - MOCKUP files: WDG00000100_MOCKUP.jpg
   - Other files: WDG00000100.png, WDG00000100.eps, etc.
4. Updates Media model file references if files are tracked in database

Usage:
    python manage.py rename_design_files
    python manage.py rename_design_files --dry-run
    python manage.py rename_design_files --verbose
    python manage.py rename_design_files --user-id 4
    python manage.py rename_design_files --product-id 60
"""

import os
import logging
from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.conf import settings
from Catalog.models import Product
from MediaFiles.models import Media

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Rename design files to use product_number format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be renamed without actually renaming files',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information for each file',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Process only files for a specific user ID',
        )
        parser.add_argument(
            '--product-id',
            type=int,
            help='Process only files for a specific product ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        user_id_filter = options.get('user_id')
        product_id_filter = options.get('product_id')

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('Design Files Rename Script'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: No files will be renamed\n'))

        media_root = Path(settings.MEDIA_ROOT)
        
        if not media_root.exists():
            self.stdout.write(self.style.ERROR(f'Media root does not exist: {media_root}'))
            return

        # Statistics
        stats = {
            'total_files': 0,
            'renamed': 0,
            'skipped': 0,
            'errors': 0,
            'no_product': 0,
            'no_product_number': 0,
            'already_renamed': 0,
        }

        error_details = []

        # Iterate through user directories
        user_dirs = [d for d in media_root.iterdir() if d.is_dir() and d.name.isdigit()]
        
        if user_id_filter:
            user_dirs = [d for d in user_dirs if int(d.name) == user_id_filter]
        
        self.stdout.write(f'Found {len(user_dirs)} user directories to process\n')

        for user_dir in user_dirs:
            user_id = int(user_dir.name)
            designs_dir = user_dir / 'designs'
            
            if not designs_dir.exists():
                if verbose:
                    self.stdout.write(f'  User {user_id}: No designs directory')
                continue

            # Get product directories
            product_dirs = [d for d in designs_dir.iterdir() if d.is_dir() and d.name.isdigit()]
            
            if product_id_filter:
                product_dirs = [d for d in product_dirs if int(d.name) == product_id_filter]

            for product_dir in product_dirs:
                product_id = int(product_dir.name)
                
                try:
                    # Get product from database
                    product = Product.objects.get(id=product_id)
                    
                    if not product.product_number:
                        stats['no_product_number'] += 1
                        if verbose:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  Product {product_id}: No product_number found'
                                )
                            )
                        continue

                    product_number = product.product_number
                    
                    # Process files in product directory
                    files = [f for f in product_dir.iterdir() if f.is_file()]
                    stats['total_files'] += len(files)

                    if verbose:
                        self.stdout.write(
                            f'  User {user_id} / Product {product_id} ({product_number}): '
                            f'{len(files)} files'
                        )

                    for file_path in files:
                        try:
                            old_filename = file_path.name
                            
                            # Check if already renamed (starts with product_number)
                            if old_filename.startswith(product_number):
                                stats['already_renamed'] += 1
                                if verbose:
                                    self.stdout.write(
                                        f'    ✓ Already renamed: {old_filename}'
                                    )
                                continue

                            # Determine new filename
                            file_ext = file_path.suffix.lower()
                            
                            # Check if file is a MOCKUP file (case-insensitive)
                            is_mockup = 'MOCKUP' in old_filename.upper()
                            
                            if is_mockup:
                                new_filename = f'{product_number}_MOCKUP{file_ext}'
                            else:
                                new_filename = f'{product_number}{file_ext}'

                            new_file_path = product_dir / new_filename

                            # Check if target file already exists
                            if new_file_path.exists() and new_file_path != file_path:
                                stats['skipped'] += 1
                                if verbose:
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f'    ⊘ Target exists, skipping: {old_filename} -> {new_filename}'
                                        )
                                    )
                                continue

                            if verbose:
                                self.stdout.write(
                                    f'    {old_filename} -> {new_filename}'
                                )

                            if dry_run:
                                stats['renamed'] += 1
                                continue

                            # Rename the file
                            try:
                                # Use relative path for storage operations
                                old_relative_path = str(file_path.relative_to(media_root))
                                new_relative_path = str(new_file_path.relative_to(media_root))

                                # Rename using storage
                                if default_storage.exists(old_relative_path):
                                    # Copy to new location
                                    with default_storage.open(old_relative_path, 'rb') as old_file:
                                        default_storage.save(new_relative_path, old_file)
                                    
                                    # Update Media model if file is tracked
                                    self._update_media_references(
                                        old_relative_path,
                                        new_relative_path,
                                        verbose
                                    )
                                    
                                    # Delete old file
                                    try:
                                        default_storage.delete(old_relative_path)
                                    except Exception as e:
                                        logger.warning(
                                            f'Could not delete old file {old_relative_path}: {str(e)}'
                                        )
                                    
                                    stats['renamed'] += 1
                                    if verbose:
                                        self.stdout.write(
                                            self.style.SUCCESS(f'      ✓ Renamed successfully')
                                        )
                                else:
                                    # File doesn't exist in storage, try direct rename
                                    file_path.rename(new_file_path)
                                    stats['renamed'] += 1
                                    if verbose:
                                        self.stdout.write(
                                            self.style.SUCCESS(f'      ✓ Renamed successfully (direct)')
                                        )

                            except Exception as e:
                                stats['errors'] += 1
                                error_msg = f'Failed to rename: {str(e)}'
                                error_details.append({
                                    'user_id': user_id,
                                    'product_id': product_id,
                                    'old_filename': old_filename,
                                    'new_filename': new_filename,
                                    'error': error_msg
                                })
                                if verbose:
                                    self.stdout.write(
                                        self.style.ERROR(f'      ✗ {error_msg}')
                                    )
                                logger.error(
                                    f'Error renaming file {old_filename} to {new_filename}: {error_msg}',
                                    exc_info=True
                                )

                        except Exception as e:
                            stats['errors'] += 1
                            error_msg = f'Unexpected error processing file: {str(e)}'
                            error_details.append({
                                'user_id': user_id,
                                'product_id': product_id,
                                'file': str(file_path),
                                'error': error_msg
                            })
                            logger.error(
                                f'Unexpected error processing file {file_path}: {error_msg}',
                                exc_info=True
                            )

                except Product.DoesNotExist:
                    stats['no_product'] += 1
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Product {product_id}: Not found in database'
                            )
                        )
                except Exception as e:
                    stats['errors'] += 1
                    error_msg = f'Error processing product {product_id}: {str(e)}'
                    error_details.append({
                        'product_id': product_id,
                        'error': error_msg
                    })
                    logger.error(error_msg, exc_info=True)

        # Print summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Rename Summary'))
        self.stdout.write('=' * 80 + '\n')
        
        self.stdout.write(f'Total files found: {stats["total_files"]}')
        self.stdout.write(self.style.SUCCESS(f'✓ Successfully renamed: {stats["renamed"]}'))
        
        if stats['already_renamed'] > 0:
            self.stdout.write(self.style.SUCCESS(f'✓ Already renamed: {stats["already_renamed"]}'))
        
        if stats['skipped'] > 0:
            self.stdout.write(self.style.WARNING(f'⊘ Skipped: {stats["skipped"]}'))
        
        if stats['no_product'] > 0:
            self.stdout.write(self.style.WARNING(f'⚠ Product not found in database: {stats["no_product"]}'))
        
        if stats['no_product_number'] > 0:
            self.stdout.write(self.style.WARNING(f'⚠ Product missing product_number: {stats["no_product_number"]}'))
        
        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f'✗ Errors: {stats["errors"]}'))
        
        if error_details and verbose:
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.ERROR('Error Details'))
            self.stdout.write('=' * 80 + '\n')
            for idx, error in enumerate(error_details[:20], 1):  # Show first 20 errors
                error_str = f'{idx}. '
                if 'user_id' in error:
                    error_str += f'User {error["user_id"]} / '
                if 'product_id' in error:
                    error_str += f'Product {error["product_id"]}: '
                if 'old_filename' in error:
                    error_str += f'{error["old_filename"]} -> {error.get("new_filename", "?")}: '
                error_str += error['error']
                self.stdout.write(error_str)
            if len(error_details) > 20:
                self.stdout.write(f'... and {len(error_details) - 20} more errors')
        
        if dry_run:
            self.stdout.write('\n' + self.style.WARNING(
                'DRY RUN COMPLETE: No files were actually renamed.\n'
                'Run without --dry-run to perform the rename operation.'
            ))
        else:
            self.stdout.write('\n' + self.style.SUCCESS('Rename operation completed!'))
        
        self.stdout.write('')

    def _update_media_references(self, old_path, new_path, verbose=False):
        """
        Update Media model file references when files are renamed.
        This ensures database records point to the new file location.
        """
        try:
            # Find Media objects that reference the old path
            # The file field stores relative paths, so we need to check both
            # the exact path and paths that might have different separators
            media_objects = Media.objects.filter(file=old_path)
            
            if not media_objects.exists():
                # Try with different path formats
                old_path_alt = old_path.replace('/', os.sep).replace('\\', os.sep)
                media_objects = Media.objects.filter(file=old_path_alt)
            
            if not media_objects.exists():
                # Try with leading slash
                old_path_with_slash = '/' + old_path.lstrip('/')
                media_objects = Media.objects.filter(file=old_path_with_slash)
            
            updated_count = 0
            for media in media_objects:
                media.file.name = new_path
                media.save(update_fields=['file'])
                updated_count += 1
                if verbose:
                    logger.info(f'Updated Media {media.id} file reference: {old_path} -> {new_path}')
            
            if updated_count > 0:
                logger.info(f'Updated {updated_count} Media object(s) for file rename: {old_path} -> {new_path}')
            
        except Exception as e:
            # Log but don't fail - file rename is more important than DB update
            logger.warning(f'Could not update Media references for {old_path}: {str(e)}')

