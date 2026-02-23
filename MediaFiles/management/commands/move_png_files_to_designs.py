"""
Management command to move PNG and AVIF files from {user_id}/media/ to {user_id}/designs/{product_id}/.

This command:
1. Finds all Media objects with files in {user_id}/media/ that match product number pattern (WDG*)
2. Queries Product table to find matching product by product_number
3. Moves files to correct location: {user_id}/designs/{product_id}/
4. Updates Media object file paths in database
5. Handles AVIF files that correspond to PNG files

Usage:
    python manage.py move_png_files_to_designs
    python manage.py move_png_files_to_designs --dry-run
    python manage.py move_png_files_to_designs --verbose
    python manage.py move_png_files_to_designs --user-id 2
"""

import os
import re
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from Catalog.models import Product
from MediaFiles.models import Media, Relation


class Command(BaseCommand):
    help = 'Move PNG and AVIF files from {user_id}/media/ to {user_id}/designs/{product_id}/'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be moved without actually moving files',
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

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        user_id_filter = options.get('user_id')

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('Move PNG/AVIF Files to Product Design Folders'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: No files will be moved\n'))

        # Statistics
        stats = {
            'total_media': 0,
            'moved': 0,
            'skipped': 0,
            'errors': 0,
        }

        error_details = []

        # Find all Media objects with files in {user_id}/media/ folder
        # Pattern: {user_id}/media/WDG*.png or {user_id}/media/WDG*_PNG.avif
        all_media = Media.objects.all()
        
        if user_id_filter:
            # Filter by user_id in file path
            all_media = [m for m in all_media if m.file and f'/{user_id_filter}/media/' in m.file.name]
        else:
            all_media = [m for m in all_media if m.file and '/media/' in m.file.name and '/designs/' not in m.file.name]

        self.stdout.write(f'Found {len(all_media)} media files in media/ folders\n')

        for media in all_media:
            try:
                stats['total_media'] += 1

                if not media.file:
                    stats['skipped'] += 1
                    continue

                current_path = media.file.name
                
                # Check if file is in {user_id}/media/ folder (not in designs/)
                if '/designs/' in current_path:
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(f'  Media {media.id}: {current_path} - Already in designs folder, skipping.')
                    continue

                # Extract user_id and filename from path
                # Pattern: {user_id}/media/{filename}
                path_parts = current_path.split('/')
                if len(path_parts) < 3 or path_parts[1] != 'media':
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(f'  Media {media.id}: {current_path} - Unexpected path format, skipping.')
                    continue

                user_id = path_parts[0]
                filename = '/'.join(path_parts[2:])  # Handle subdirectories if any
                filename_only = os.path.basename(filename)

                # Check if filename matches product number pattern (WDG*)
                product_number_match = re.match(r'^(WDG\d+)', filename_only, re.IGNORECASE)
                if not product_number_match:
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(f'  Media {media.id}: {filename_only} - Does not match product number pattern, skipping.')
                    continue

                product_number = product_number_match.group(1).upper()

                # Find product by product_number and user_id
                try:
                    product = Product.objects.filter(
                        product_number__iexact=product_number,
                        created_by_id=user_id
                    ).first()

                    if not product:
                        stats['skipped'] += 1
                        if verbose:
                            self.stdout.write(f'  Media {media.id}: {filename_only} - Product not found for {product_number}, skipping.')
                        continue

                    # Determine target path: {user_id}/designs/{product_id}/{filename}
                    target_path = f'{user_id}/designs/{product.id}/{filename_only}'

                    if verbose:
                        self.stdout.write(f'\nProcessing Media {media.id}:')
                        self.stdout.write(f'  Current: {current_path}')
                        self.stdout.write(f'  Target:  {target_path}')
                        self.stdout.write(f'  Product: {product.id} ({product.product_number})')

                    # Check if target file already exists
                    if default_storage.exists(target_path):
                        if verbose:
                            self.stdout.write(self.style.WARNING(f'  Target file already exists: {target_path}'))
                        # Check if it's the same file (same Media object)
                        existing_media = Media.objects.filter(file=target_path).exclude(pk=media.pk).first()
                        if existing_media:
                            # Another Media object already points to the target file
                            if verbose:
                                self.stdout.write(self.style.WARNING(f'    Another Media object ({existing_media.pk}) already points to target. Deleting duplicate.'))
                            if not dry_run:
                                # Delete the file in wrong location
                                if default_storage.exists(current_path):
                                    try:
                                        default_storage.delete(current_path)
                                    except Exception as e:
                                        pass
                                # Delete the duplicate Media object
                                media.delete()
                                stats['moved'] += 1
                            else:
                                stats['moved'] += 1
                            continue

                    # Check if source file exists
                    if not default_storage.exists(current_path):
                        stats['errors'] += 1
                        error_msg = f'Source file not found: {current_path}'
                        error_details.append({'media_id': media.id, 'error': error_msg})
                        if verbose:
                            self.stdout.write(self.style.ERROR(f'    ERROR: {error_msg}'))
                        continue

                    if not dry_run:
                        # Copy file to new location
                        with default_storage.open(current_path, 'rb') as source_file:
                            default_storage.save(target_path, source_file)

                        # Update Media object file path
                        media.file.name = target_path
                        media.save(update_fields=['file'])

                        # Delete old file
                        try:
                            default_storage.delete(current_path)
                        except Exception as e:
                            pass
                            error_details.append({'media_id': media.id, 'error': f'Failed to delete old file: {str(e)}'})

                        stats['moved'] += 1
                        if verbose:
                            self.stdout.write(self.style.SUCCESS(f'    ✓ Moved successfully'))
                    else:
                        stats['moved'] += 1
                        if verbose:
                            self.stdout.write(self.style.SUCCESS(f'    Would move to {target_path}'))

                except Product.DoesNotExist:
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(self.style.WARNING(f'  Media {media.id}: Product not found for {product_number}'))
                except Exception as e:
                    stats['errors'] += 1
                    error_msg = f'Unexpected error processing media {media.id}: {str(e)}'
                    error_details.append({'media_id': media.id, 'error': error_msg})
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'  ✗ {error_msg}'))

            except Media.DoesNotExist:
                stats['skipped'] += 1
                if verbose:
                    self.stdout.write(self.style.WARNING(f'  Media {media.id}: Not found in DB, skipping.'))
            except Exception as e:
                stats['errors'] += 1
                error_msg = f'Unexpected error processing media {media.id}: {str(e)}'
                error_details.append({'media_id': media.id, 'error': error_msg})
                if verbose:
                    self.stdout.write(self.style.ERROR(f'  ✗ {error_msg}'))

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Summary'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Total media files processed: {stats["total_media"]}')
        self.stdout.write(self.style.SUCCESS(f'Files moved: {stats["moved"]}'))
        self.stdout.write(f'Files skipped: {stats["skipped"]}')
        if stats['errors'] > 0:
            self.stdout.write(self.style.ERROR(f'Errors encountered: {stats["errors"]}'))
        
        if error_details and verbose:
            self.stdout.write('\n' + '=' * 80)
            self.stdout.write(self.style.ERROR('Error Details (first 10 shown)'))
            self.stdout.write('=' * 80)
            for error in error_details[:10]:
                self.stdout.write(f'Media {error.get("media_id", "N/A")}: {error.get("error", "Unknown error")}')
            if len(error_details) > 10:
                self.stdout.write(f'... and {len(error_details) - 10} more errors.')
        self.stdout.write('\n')

