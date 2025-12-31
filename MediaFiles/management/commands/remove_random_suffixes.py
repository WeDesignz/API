"""
Management command to remove random suffixes from product design files.

Django FileField adds random suffixes (like _eNarIlh, _nfIoUmh) to prevent filename collisions.
Since product files are in unique folders ({user_id}/designs/{product_id}/), these suffixes
are unnecessary and cause issues with AVIF matching.

This command:
1. Finds all Media objects with product files
2. Removes random suffixes from filenames
3. Renames files in storage
4. Updates Media model references

Usage:
    python manage.py remove_random_suffixes
    python manage.py remove_random_suffixes --dry-run
    python manage.py remove_random_suffixes --verbose
    python manage.py remove_random_suffixes --product-id 34
"""

import os
import re
import logging
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.conf import settings
from Catalog.models import Product
from MediaFiles.models import Media, Relation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Remove random suffixes from product design files'

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
            '--product-id',
            type=int,
            help='Process only files for a specific product ID',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        product_id_filter = options.get('product_id')

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('Remove Random Suffixes from Product Files'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: No files will be renamed\n'))

        # Statistics
        stats = {
            'total_media': 0,
            'processed': 0,
            'renamed': 0,
            'skipped': 0,
            'errors': 0,
        }

        error_details = []

        # Get all Media objects linked to products
        relations = Relation.objects.filter(relation_type='Product:Media')
        
        if product_id_filter:
            relations = relations.filter(id_1=product_id_filter)

        # Get unique media IDs
        media_ids = relations.values_list('id_2', flat=True).distinct()
        
        self.stdout.write(f'Found {len(media_ids)} media files linked to products\n')

        for media_id in media_ids:
            try:
                media = Media.objects.get(pk=media_id)
                stats['total_media'] += 1

                if not media.file:
                    stats['skipped'] += 1
                    continue

                current_path = media.file.name
                
                # Check if this is a product file
                if '/designs/' not in current_path:
                    stats['skipped'] += 1
                    continue

                # Extract filename
                filename = os.path.basename(current_path)
                
                # Check if filename has a random suffix pattern
                # Pattern: _ followed by 6-8 alphanumeric characters before extension
                # e.g., WDG00000034_MOCKUP_oVHZGT7.jpg -> WDG00000034_MOCKUP.jpg
                pattern = r'^(.+)_([a-z0-9]{6,8})(\.[^.]+)$'
                match = re.match(pattern, filename, re.IGNORECASE)
                
                if not match:
                    # No random suffix found
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(f'  Media {media_id}: {filename} - No suffix to remove')
                    continue

                base_name = match.group(1)
                suffix = match.group(2)
                extension = match.group(3)
                new_filename = base_name + extension
                new_path = os.path.dirname(current_path) + '/' + new_filename

                if verbose:
                    self.stdout.write(f'  Media {media_id}:')
                    self.stdout.write(f'    Current: {filename}')
                    self.stdout.write(f'    Target:  {new_filename}')
                    self.stdout.write(f'    Suffix:  {suffix}')

                # Check if target file (without suffix) already exists
                target_exists = default_storage.exists(new_path)
                
                if target_exists:
                    # Both files exist - check if there's already a Media object pointing to the target
                    existing_media = Media.objects.filter(file=new_path).exclude(pk=media_id).first()
                    
                    if existing_media:
                        # Another Media object already points to the target file
                        # Delete this Media object and its suffixed file (they're duplicates)
                        if verbose:
                            self.stdout.write(self.style.WARNING(f'    Duplicate: Media {existing_media.id} already points to {new_filename}'))
                            self.stdout.write(self.style.WARNING(f'    Will delete Media {media_id} and its suffixed file'))
                        
                        if dry_run:
                            stats['renamed'] += 1
                            if verbose:
                                self.stdout.write(self.style.SUCCESS(f'    Would delete Media {media_id} and file {filename}'))
                            continue
                        
                        # Delete the suffixed file
                        if default_storage.exists(current_path):
                            try:
                                default_storage.delete(current_path)
                            except Exception as e:
                                logger.warning(f'Could not delete suffixed file {current_path}: {str(e)}')
                        
                        # Delete this Media object (duplicate)
                        try:
                            media.delete()
                            stats['renamed'] += 1
                            if verbose:
                                self.stdout.write(self.style.SUCCESS(f'    ✓ Deleted duplicate Media {media_id} and file {filename}'))
                        except Exception as e:
                            stats['errors'] += 1
                            error_msg = f'Failed to delete duplicate Media: {str(e)}'
                            error_details.append({
                                'media_id': media_id,
                                'error': error_msg
                            })
                            if verbose:
                                self.stdout.write(self.style.ERROR(f'    ✗ {error_msg}'))
                            logger.error(f'Error deleting duplicate media {media_id}: {error_msg}', exc_info=True)
                    else:
                        # No other Media points to target - update this Media to point to it
                        if verbose:
                            self.stdout.write(self.style.WARNING(f'    Both files exist - will delete suffixed version and update Media'))
                        
                        if dry_run:
                            stats['renamed'] += 1
                            if verbose:
                                self.stdout.write(self.style.SUCCESS(f'    Would delete {filename} and update Media to point to {new_filename}'))
                            continue
                        
                        # Check if current file exists
                        if not default_storage.exists(current_path):
                            stats['errors'] += 1
                            error_msg = f'File with suffix not found: {current_path}'
                            error_details.append({
                                'media_id': media_id,
                                'error': error_msg
                            })
                            if verbose:
                                self.stdout.write(self.style.ERROR(f'    ERROR: {error_msg}'))
                            continue
                        
                        # Update Media model to point to the file without suffix
                        try:
                            media.file.name = new_path
                            media.save(update_fields=['file'])
                            
                            # Delete the file with suffix
                            try:
                                default_storage.delete(current_path)
                                stats['renamed'] += 1
                                if verbose:
                                    self.stdout.write(self.style.SUCCESS(f'    ✓ Deleted {filename} and updated Media to point to {new_filename}'))
                            except Exception as e:
                                logger.warning(f'Could not delete suffixed file {current_path}: {str(e)}')
                                # Media is already updated, so count as success
                                stats['renamed'] += 1
                                if verbose:
                                    self.stdout.write(self.style.WARNING(f'    ✓ Updated Media but could not delete {filename}: {str(e)}'))
                        except Exception as e:
                            stats['errors'] += 1
                            error_msg = f'Failed to update Media: {str(e)}'
                            error_details.append({
                                'media_id': media_id,
                                'old_path': current_path,
                                'new_path': new_path,
                                'error': error_msg
                            })
                            if verbose:
                                self.stdout.write(self.style.ERROR(f'    ✗ {error_msg}'))
                            logger.error(f'Error updating media {media_id}: {error_msg}', exc_info=True)
                    
                    continue

                if dry_run:
                    stats['renamed'] += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(f'    Would rename'))
                    continue

                # Check if current file exists
                if not default_storage.exists(current_path):
                    stats['errors'] += 1
                    error_msg = f'File not found: {current_path}'
                    error_details.append({
                        'media_id': media_id,
                        'error': error_msg
                    })
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ERROR: {error_msg}'))
                    continue

                # Rename file in storage
                try:
                    # Copy to new location
                    with default_storage.open(current_path, 'rb') as old_file:
                        default_storage.save(new_path, old_file)
                    
                    # Update Media model
                    media.file.name = new_path
                    media.save(update_fields=['file'])
                    
                    # Delete old file
                    try:
                        default_storage.delete(current_path)
                    except Exception as e:
                        logger.warning(f'Could not delete old file {current_path}: {str(e)}')
                    
                    stats['renamed'] += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(f'    ✓ Renamed successfully'))
                
                except Exception as e:
                    stats['errors'] += 1
                    error_msg = f'Failed to rename: {str(e)}'
                    error_details.append({
                        'media_id': media_id,
                        'old_path': current_path,
                        'new_path': new_path,
                        'error': error_msg
                    })
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ {error_msg}'))
                    logger.error(f'Error renaming media {media_id}: {error_msg}', exc_info=True)

            except Media.DoesNotExist:
                stats['skipped'] += 1
                if verbose:
                    self.stdout.write(self.style.WARNING(f'  Media {media_id}: Not found'))
            except Exception as e:
                stats['errors'] += 1
                error_msg = f'Unexpected error: {str(e)}'
                error_details.append({
                    'media_id': media_id,
                    'error': error_msg
                })
                logger.error(f'Unexpected error processing media {media_id}: {error_msg}', exc_info=True)

        # Print summary
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Summary'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Total media files: {stats["total_media"]}')
        self.stdout.write(self.style.SUCCESS(f'Renamed: {stats["renamed"]}'))
        self.stdout.write(f'Skipped: {stats["skipped"]}')
        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {stats["errors"]}'))
        
        if error_details and verbose:
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.ERROR('Error Details'))
            self.stdout.write('=' * 80)
            for error in error_details[:10]:  # Show first 10 errors
                self.stdout.write(f'Media {error.get("media_id")}: {error.get("error")}')

