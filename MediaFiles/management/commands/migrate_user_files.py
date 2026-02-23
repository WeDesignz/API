"""
Management command to migrate existing files to the new user-centric folder structure.

This command migrates:
1. Invoices from invoices/ to {user_id}/invoices/
2. PDF downloads from pdfs/ to {user_id}/pdfs/
3. Design files from media/ or {user_id}/{product_id}/ to {user_id}/designs/{product_id}/
4. Bulk uploads from design_uploads/{user_id}/ to {user_id}/uploads/
5. Temp uploads from temp_uploads/{user_id}/ to {user_id}/temp/
6. Profile photos from media/ to {user_id}/profile/
7. Business documents from media/ to {user_id}/documents/
8. Custom order deliverables from media/ to {user_id}/orders/{order_id}/deliverables/

Usage:
    python manage.py migrate_user_files
    python manage.py migrate_user_files --dry-run
    python manage.py migrate_user_files --type invoices
    python manage.py migrate_user_files --skip-existing
    python manage.py migrate_user_files --cleanup  # Remove empty old folders after migration
"""

from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from django.conf import settings
from MediaFiles.models import Media, Relation
from Catalog.models import Product, PDFDownload
from Orders.models import Invoice
from common.relations import get_related_for_right
import os
import shutil


class Command(BaseCommand):
    help = 'Migrate existing files to user-centric folder structure'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually moving files',
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['invoices', 'pdfs', 'designs', 'uploads', 'temp', 'profile', 'documents', 'deliverables', 'all'],
            default='all',
            help='Type of files to migrate (default: all)',
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
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Remove empty old folders after migration (default: False)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        file_type = options['type']
        batch_size = options['batch_size']
        skip_existing = options['skip_existing']
        verbose = options['verbose']
        cleanup = options['cleanup']

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('User Files Migration Script'))
        self.stdout.write(self.style.SUCCESS('=' * 80 + '\n'))

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: No files will be moved\n'))

        # Overall statistics
        total_stats = {
            'invoices': {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0},
            'pdfs': {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0},
            'designs': {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0},
            'uploads': {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0},
            'temp': {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0},
            'profile': {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0},
            'documents': {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0},
            'deliverables': {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0},
        }

        # Migrate based on type
        if file_type in ['invoices', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Migrating Invoices ---\n'))
            stats = self.migrate_invoices(dry_run, batch_size, skip_existing, verbose)
            total_stats['invoices'] = stats

        if file_type in ['pdfs', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Migrating PDF Downloads ---\n'))
            stats = self.migrate_pdfs(dry_run, batch_size, skip_existing, verbose)
            total_stats['pdfs'] = stats

        if file_type in ['designs', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Migrating Design Files ---\n'))
            stats = self.migrate_designs(dry_run, batch_size, skip_existing, verbose)
            total_stats['designs'] = stats

        if file_type in ['uploads', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Migrating Bulk Uploads ---\n'))
            stats = self.migrate_bulk_uploads(dry_run, skip_existing, verbose)
            total_stats['uploads'] = stats

        if file_type in ['temp', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Migrating Temp Uploads ---\n'))
            stats = self.migrate_temp_uploads(dry_run, skip_existing, verbose)
            total_stats['temp'] = stats

        if file_type in ['profile', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Migrating Profile Photos ---\n'))
            stats = self.migrate_profile_photos(dry_run, batch_size, skip_existing, verbose)
            total_stats['profile'] = stats

        if file_type in ['documents', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Migrating Business Documents ---\n'))
            stats = self.migrate_documents(dry_run, batch_size, skip_existing, verbose)
            total_stats['documents'] = stats

        if file_type in ['deliverables', 'all']:
            self.stdout.write(self.style.SUCCESS('\n--- Migrating Custom Order Deliverables ---\n'))
            stats = self.migrate_deliverables(dry_run, batch_size, skip_existing, verbose)
            total_stats['deliverables'] = stats

        # Cleanup empty old folders if requested
        if cleanup and not dry_run:
            self.stdout.write(self.style.SUCCESS('\n--- Cleaning Up Empty Folders ---\n'))
            cleanup_stats = self.cleanup_empty_folders(verbose)
            if cleanup_stats['removed'] > 0:
                self.stdout.write(self.style.SUCCESS(
                    f'Removed {cleanup_stats["removed"]} empty folder(s)'
                ))
            else:
                self.stdout.write('No empty folders to remove.')

        # Print overall summary
        self.print_summary(total_stats, dry_run)

    def migrate_invoices(self, dry_run, batch_size, skip_existing, verbose):
        """Migrate invoice files from invoices/ to {user_id}/invoices/"""
        stats = {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0}
        
        invoices = Invoice.objects.filter(pdf_file_path__isnull=False).exclude(pdf_file_path='')
        stats['total'] = invoices.count()
        
        if stats['total'] == 0:
            self.stdout.write('No invoices found to migrate.')
            return stats

        self.stdout.write(f'Found {stats["total"]} invoices to process...\n')

        for idx, invoice in enumerate(invoices, 1):
            try:
                current_path = invoice.pdf_file_path
                
                # Check if already in correct location
                if self._is_in_user_folder(current_path, 'invoices'):
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(f'  Invoice {invoice.id}: Already in correct location')
                    continue

                # Extract filename from path
                filename = os.path.basename(current_path)
                
                # Build new path
                user_id = invoice.user.id
                new_path = f'{user_id}/invoices/{filename}'
                
                if verbose:
                    self.stdout.write(f'  Invoice {invoice.id}: {current_path} -> {new_path}')

                if dry_run:
                    stats['migrated'] += 1
                    continue

                # Build full paths
                media_root = settings.MEDIA_ROOT
                old_full_path = os.path.join(media_root, current_path) if not os.path.isabs(current_path) else current_path
                new_full_path = os.path.join(media_root, new_path)

                # Check if source exists
                if not os.path.exists(old_full_path):
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Source file not found'))
                    continue

                # Create destination directory
                os.makedirs(os.path.dirname(new_full_path), exist_ok=True)

                # Move file
                try:
                    shutil.move(old_full_path, new_full_path)
                    invoice.pdf_file_path = new_path
                    invoice.save(update_fields=['pdf_file_path'])
                    stats['migrated'] += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(f'    ✓ Migrated successfully'))
                except Exception as e:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Error: {str(e)}'))

            except Exception as e:
                stats['errors'] += 1

        return stats

    def migrate_pdfs(self, dry_run, batch_size, skip_existing, verbose):
        """Migrate PDF download files from pdfs/ to {user_id}/pdfs/"""
        stats = {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0}
        
        pdf_downloads = PDFDownload.objects.filter(pdf_file_path__isnull=False).exclude(pdf_file_path='')
        stats['total'] = pdf_downloads.count()
        
        if stats['total'] == 0:
            self.stdout.write('No PDF downloads found to migrate.')
            return stats

        self.stdout.write(f'Found {stats["total"]} PDF downloads to process...\n')

        for idx, pdf_download in enumerate(pdf_downloads, 1):
            try:
                current_path = pdf_download.pdf_file_path
                
                # Check if already in correct location
                if self._is_in_user_folder(current_path, 'pdfs'):
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(f'  PDF {pdf_download.id}: Already in correct location')
                    continue

                # Get user
                user = pdf_download.get_user()
                if not user:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(f'  PDF {pdf_download.id}: No user found')
                    continue

                # Extract filename from path
                filename = os.path.basename(current_path)
                
                # Build new path
                user_id = user.id
                new_path = f'{user_id}/pdfs/{filename}'
                
                if verbose:
                    self.stdout.write(f'  PDF {pdf_download.id}: {current_path} -> {new_path}')

                if dry_run:
                    stats['migrated'] += 1
                    continue

                # Build full paths
                media_root = settings.MEDIA_ROOT
                old_full_path = os.path.join(media_root, current_path) if not os.path.isabs(current_path) else current_path
                new_full_path = os.path.join(media_root, new_path)

                # Check if source exists
                if not os.path.exists(old_full_path):
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Source file not found'))
                    continue

                # Create destination directory
                os.makedirs(os.path.dirname(new_full_path), exist_ok=True)

                # Move file
                try:
                    shutil.move(old_full_path, new_full_path)
                    pdf_download.pdf_file_path = new_path
                    pdf_download.save(update_fields=['pdf_file_path'])
                    stats['migrated'] += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(f'    ✓ Migrated successfully'))
                except Exception as e:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Error: {str(e)}'))

            except Exception as e:
                stats['errors'] += 1

        return stats

    def migrate_designs(self, dry_run, batch_size, skip_existing, verbose):
        """Migrate design files from media/ or {user_id}/{product_id}/ to {user_id}/designs/{product_id}/"""
        stats = {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0}
        
        # Get all Media objects related to Products
        product_media_relations = Relation.objects.filter(
            relation_type='Product:Media'
        ).select_related().values_list('id_2', flat=True).distinct()
        
        media_ids = list(set(product_media_relations))
        stats['total'] = len(media_ids)
        
        if stats['total'] == 0:
            self.stdout.write('No design files found to migrate.')
            return stats

        self.stdout.write(f'Found {stats["total"]} design files to process...\n')

        for idx, media_id in enumerate(media_ids, 1):
            try:
                media = Media.objects.get(id=media_id)
                
                if not media.file:
                    continue

                current_path = media.file.name
                
                # Check if already in correct location (designs subfolder)
                if self._is_in_designs_folder(current_path):
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(f'  Media {media_id}: Already in designs folder')
                    continue

                # Get related products
                products = get_related_for_right(media, 'Product:Media', Product)
                if not products.exists():
                    continue

                product = products.first()
                if not product.created_by:
                    continue

                user_id = product.created_by.id
                product_id = product.id
                
                # Extract filename
                filename = os.path.basename(current_path)
                
                # Build new path
                new_path = f'{user_id}/designs/{product_id}/{filename}'
                
                if verbose:
                    self.stdout.write(f'  Media {media_id}: {current_path} -> {new_path}')

                if dry_run:
                    stats['migrated'] += 1
                    continue

                # Build full paths
                media_root = settings.MEDIA_ROOT
                old_full_path = os.path.join(media_root, current_path) if not os.path.isabs(current_path) else current_path
                new_full_path = os.path.join(media_root, new_path)

                # Check if source exists
                if not os.path.exists(old_full_path):
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Source file not found'))
                    continue

                # Create destination directory
                os.makedirs(os.path.dirname(new_full_path), exist_ok=True)

                # Move file
                try:
                    shutil.move(old_full_path, new_full_path)
                    media.file.name = new_path
                    media.save(update_fields=['file'])
                    stats['migrated'] += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(f'    ✓ Migrated successfully'))
                except Exception as e:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Error: {str(e)}'))

            except Media.DoesNotExist:
                continue
            except Exception as e:
                stats['errors'] += 1

        return stats

    def migrate_bulk_uploads(self, dry_run, skip_existing, verbose):
        """Migrate bulk upload ZIP files from design_uploads/{user_id}/ to {user_id}/uploads/"""
        stats = {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0}
        
        media_root = settings.MEDIA_ROOT
        old_base_dir = os.path.join(media_root, 'design_uploads')
        
        if not os.path.exists(old_base_dir):
            self.stdout.write('No design_uploads directory found.')
            return stats

        # Find all user directories
        user_dirs = []
        for item in os.listdir(old_base_dir):
            item_path = os.path.join(old_base_dir, item)
            if os.path.isdir(item_path):
                try:
                    user_id = int(item)  # Validate it's a user ID
                    user_dirs.append((user_id, item_path))
                except ValueError:
                    continue

        stats['total'] = sum(len([f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))]) for _, d in user_dirs)
        
        if stats['total'] == 0:
            self.stdout.write('No bulk upload files found to migrate.')
            return stats

        self.stdout.write(f'Found {stats["total"]} bulk upload files to process...\n')

        for user_id, old_user_dir in user_dirs:
            new_user_dir = os.path.join(media_root, str(user_id), 'uploads')
            
            if not os.path.exists(old_user_dir):
                continue

            files = [f for f in os.listdir(old_user_dir) if os.path.isfile(os.path.join(old_user_dir, f))]
            
            for filename in files:
                try:
                    old_file_path = os.path.join(old_user_dir, filename)
                    new_file_path = os.path.join(new_user_dir, filename)
                    
                    # Check if already migrated
                    if os.path.exists(new_file_path) and skip_existing:
                        stats['skipped'] += 1
                        if verbose:
                            self.stdout.write(f'  {filename}: Already exists in new location')
                        continue

                    if verbose:
                        self.stdout.write(f'  {filename}: design_uploads/{user_id}/ -> {user_id}/uploads/')

                    if dry_run:
                        stats['migrated'] += 1
                        continue

                    # Create destination directory
                    os.makedirs(new_user_dir, exist_ok=True)

                    # Move file
                    try:
                        shutil.move(old_file_path, new_file_path)
                        stats['migrated'] += 1
                        if verbose:
                            self.stdout.write(self.style.SUCCESS(f'    ✓ Migrated successfully'))
                    except Exception as e:
                        stats['errors'] += 1
                        if verbose:
                            self.stdout.write(self.style.ERROR(f'    ✗ Error: {str(e)}'))

                except Exception as e:
                    stats['errors'] += 1

        return stats

    def migrate_temp_uploads(self, dry_run, skip_existing, verbose):
        """Migrate temp upload files from temp_uploads/{user_id}/ to {user_id}/temp/"""
        stats = {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0}
        
        media_root = settings.MEDIA_ROOT
        old_base_dir = os.path.join(media_root, 'temp_uploads')
        
        if not os.path.exists(old_base_dir):
            self.stdout.write('No temp_uploads directory found.')
            return stats

        # Find all user directories
        user_dirs = []
        for item in os.listdir(old_base_dir):
            item_path = os.path.join(old_base_dir, item)
            if os.path.isdir(item_path):
                try:
                    user_id = int(item)  # Validate it's a user ID
                    user_dirs.append((user_id, item_path))
                except ValueError:
                    continue

        stats['total'] = sum(len([f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))]) for _, d in user_dirs)
        
        if stats['total'] == 0:
            self.stdout.write('No temp upload files found to migrate.')
            return stats

        self.stdout.write(f'Found {stats["total"]} temp upload files to process...\n')

        for user_id, old_user_dir in user_dirs:
            new_user_dir = os.path.join(media_root, str(user_id), 'temp')
            
            if not os.path.exists(old_user_dir):
                continue

            files = [f for f in os.listdir(old_user_dir) if os.path.isfile(os.path.join(old_user_dir, f))]
            
            for filename in files:
                try:
                    old_file_path = os.path.join(old_user_dir, filename)
                    new_file_path = os.path.join(new_user_dir, filename)
                    
                    # Check if already migrated
                    if os.path.exists(new_file_path) and skip_existing:
                        stats['skipped'] += 1
                        if verbose:
                            self.stdout.write(f'  {filename}: Already exists in new location')
                        continue

                    if verbose:
                        self.stdout.write(f'  {filename}: temp_uploads/{user_id}/ -> {user_id}/temp/')

                    if dry_run:
                        stats['migrated'] += 1
                        continue

                    # Create destination directory
                    os.makedirs(new_user_dir, exist_ok=True)

                    # Move file
                    try:
                        shutil.move(old_file_path, new_file_path)
                        stats['migrated'] += 1
                        if verbose:
                            self.stdout.write(self.style.SUCCESS(f'    ✓ Migrated successfully'))
                    except Exception as e:
                        stats['errors'] += 1
                        if verbose:
                            self.stdout.write(self.style.ERROR(f'    ✗ Error: {str(e)}'))

                except Exception as e:
                    stats['errors'] += 1

        return stats

    def migrate_profile_photos(self, dry_run, batch_size, skip_existing, verbose):
        """Migrate profile photos from media/ to {user_id}/profile/"""
        stats = {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0}
        
        # Find all Media objects related to profile photos via DesignerProfile:Media or AdminUserProfile:Media
        profile_relations = Relation.objects.filter(
            relation_type__in=['DesignerProfile:Media', 'AdminUserProfile:Media']
        ).filter(meta__type='profile_photo')
        
        media_ids = list(profile_relations.values_list('id_2', flat=True).distinct())
        stats['total'] = len(media_ids)
        
        if stats['total'] == 0:
            self.stdout.write('No profile photos found to migrate.')
            return stats
        
        self.stdout.write(f'Found {stats["total"]} profile photos to process...\n')
        
        for idx, media_id in enumerate(media_ids, 1):
            try:
                media = Media.objects.get(id=media_id)
                
                if not media.file:
                    continue
                
                current_path = media.file.name
                
                # Check if already in correct location
                if self._is_in_user_folder(current_path, 'profile'):
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(f'  Media {media_id}: Already in profile folder')
                    continue
                
                # Get user from created_by
                if not media.created_by:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'  Media {media_id}: No created_by user'))
                    continue
                
                user_id = media.created_by.id
                filename = os.path.basename(current_path)
                new_path = f'{user_id}/profile/{filename}'
                
                if verbose:
                    self.stdout.write(f'  Media {media_id}: {current_path} -> {new_path}')
                
                if dry_run:
                    stats['migrated'] += 1
                    continue
                
                # Build full paths
                media_root = settings.MEDIA_ROOT
                old_full_path = os.path.join(media_root, current_path) if not os.path.isabs(current_path) else current_path
                new_full_path = os.path.join(media_root, new_path)
                
                # Check if source exists
                if not os.path.exists(old_full_path):
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Source file not found'))
                    continue
                
                # Create destination directory
                os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
                
                # Move file
                try:
                    shutil.move(old_full_path, new_full_path)
                    # Update database
                    media.file.name = new_path
                    media.save(update_fields=['file'])
                    stats['migrated'] += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(f'    ✓ Migrated successfully'))
                except Exception as e:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Error: {str(e)}'))
                    
            except Exception as e:
                stats['errors'] += 1
        
        return stats

    def migrate_documents(self, dry_run, batch_size, skip_existing, verbose):
        """Migrate business documents (PAN, MSME) from media/ to {user_id}/documents/"""
        stats = {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0}
        
        # Find all Media objects related to business documents via Studio:Media
        document_relations = Relation.objects.filter(
            relation_type='Studio:Media'
        )
        
        # Filter for PAN card or MSME certificate documents
        media_ids = []
        for relation in document_relations:
            # Check if it's a business document (PAN or MSME)
            # These are typically stored in StudioBusinessDetails, but we can identify by relation
            media_ids.append(relation.id_2)
        
        # Also check Media objects that might be documents but not in relations
        # Look for Media objects in media/ folder that are not product-related
        all_media = Media.objects.exclude(file__isnull=True).exclude(file='')
        for media in all_media:
            if media.file.name.startswith('media/') and media.created_by:
                # Check if it's not a product-related media
                product_relations = get_related_for_right(media, 'Product:Media', Product)
                if not product_relations.exists():
                    # Check if it's a document type
                    if media.media_type in ['pdf', 'doc', 'docx', 'other']:
                        media_ids.append(media.id)
        
        media_ids = list(set(media_ids))  # Remove duplicates
        stats['total'] = len(media_ids)
        
        if stats['total'] == 0:
            self.stdout.write('No business documents found to migrate.')
            return stats
        
        self.stdout.write(f'Found {stats["total"]} business documents to process...\n')
        
        for idx, media_id in enumerate(media_ids, 1):
            try:
                media = Media.objects.get(id=media_id)
                
                if not media.file:
                    continue
                
                current_path = media.file.name
                
                # Skip if already in correct location
                if self._is_in_user_folder(current_path, 'documents'):
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(f'  Media {media_id}: Already in documents folder')
                    continue
                
                # Skip if it's a design file (in designs folder)
                if self._is_in_designs_folder(current_path):
                    stats['skipped'] += 1
                    continue
                
                # Skip if it's a profile photo
                if self._is_in_user_folder(current_path, 'profile'):
                    stats['skipped'] += 1
                    continue
                
                # Get user from created_by
                if not media.created_by:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'  Media {media_id}: No created_by user'))
                    continue
                
                user_id = media.created_by.id
                filename = os.path.basename(current_path)
                new_path = f'{user_id}/documents/{filename}'
                
                if verbose:
                    self.stdout.write(f'  Media {media_id}: {current_path} -> {new_path}')
                
                if dry_run:
                    stats['migrated'] += 1
                    continue
                
                # Build full paths
                media_root = settings.MEDIA_ROOT
                old_full_path = os.path.join(media_root, current_path) if not os.path.isabs(current_path) else current_path
                new_full_path = os.path.join(media_root, new_path)
                
                # Check if source exists
                if not os.path.exists(old_full_path):
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Source file not found'))
                    continue
                
                # Create destination directory
                os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
                
                # Move file
                try:
                    shutil.move(old_full_path, new_full_path)
                    # Update database
                    media.file.name = new_path
                    media.save(update_fields=['file'])
                    stats['migrated'] += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(f'    ✓ Migrated successfully'))
                except Exception as e:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Error: {str(e)}'))
                    
            except Exception as e:
                stats['errors'] += 1
        
        return stats

    def migrate_deliverables(self, dry_run, batch_size, skip_existing, verbose):
        """Migrate custom order deliverables from media/ to {user_id}/orders/{order_id}/deliverables/"""
        stats = {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0}
        
        # Find all Media objects related to custom orders via CustomRequest:Media
        deliverable_relations = Relation.objects.filter(
            relation_type='CustomRequest:Media'
        ).filter(meta__type='delivery_file')
        
        media_ids = list(deliverable_relations.values_list('id_2', flat=True).distinct())
        stats['total'] = len(media_ids)
        
        if stats['total'] == 0:
            self.stdout.write('No custom order deliverables found to migrate.')
            return stats
        
        self.stdout.write(f'Found {stats["total"]} deliverables to process...\n')
        
        for idx, media_id in enumerate(media_ids, 1):
            try:
                media = Media.objects.get(id=media_id)
                
                if not media.file:
                    continue
                
                current_path = media.file.name
                
                # Get the custom order from relation
                relations = Relation.objects.filter(
                    relation_type='CustomRequest:Media',
                    id_2=media_id,
                    meta__type='delivery_file'
                )
                
                if not relations.exists():
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'  Media {media_id}: No custom order relation found'))
                    continue
                
                order_id = relations.first().id_1
                
                # Check if already in correct location
                path_parts = current_path.split('/')
                if len(path_parts) >= 4 and path_parts[1] == 'orders' and path_parts[2] == str(order_id) and path_parts[3] == 'deliverables':
                    stats['skipped'] += 1
                    if verbose:
                        self.stdout.write(f'  Media {media_id}: Already in deliverables folder')
                    continue
                
                # Get user from created_by (should be the customer who created the order)
                if not media.created_by:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'  Media {media_id}: No created_by user'))
                    continue
                
                user_id = media.created_by.id
                filename = os.path.basename(current_path)
                new_path = f'{user_id}/orders/{order_id}/deliverables/{filename}'
                
                if verbose:
                    self.stdout.write(f'  Media {media_id}: {current_path} -> {new_path}')
                
                if dry_run:
                    stats['migrated'] += 1
                    continue
                
                # Build full paths
                media_root = settings.MEDIA_ROOT
                old_full_path = os.path.join(media_root, current_path) if not os.path.isabs(current_path) else current_path
                new_full_path = os.path.join(media_root, new_path)
                
                # Check if source exists
                if not os.path.exists(old_full_path):
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Source file not found'))
                    continue
                
                # Create destination directory
                os.makedirs(os.path.dirname(new_full_path), exist_ok=True)
                
                # Move file
                try:
                    shutil.move(old_full_path, new_full_path)
                    # Update database
                    media.file.name = new_path
                    media.save(update_fields=['file'])
                    stats['migrated'] += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS(f'    ✓ Migrated successfully'))
                except Exception as e:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'    ✗ Error: {str(e)}'))
                    
            except Exception as e:
                stats['errors'] += 1
        
        return stats

    def _is_in_user_folder(self, file_path, subfolder):
        """Check if file path is in user-specific folder structure"""
        path = file_path.lstrip('/')
        parts = path.split('/')
        
        # Should have at least 3 parts: user_id, subfolder, filename
        if len(parts) < 3:
            return False
        
        # Check if first part is numeric (user_id) and second part matches subfolder
        try:
            int(parts[0])  # user_id
            return parts[1] == subfolder
        except ValueError:
            return False

    def _is_in_designs_folder(self, file_path):
        """Check if file path is in designs subfolder"""
        path = file_path.lstrip('/')
        parts = path.split('/')
        
        # Should have at least 4 parts: user_id, designs, product_id, filename
        if len(parts) < 4:
            return False
        
        # Check if first part is numeric (user_id), second is 'designs', third is numeric (product_id)
        try:
            int(parts[0])  # user_id
            int(parts[2])  # product_id
            return parts[1] == 'designs'
        except ValueError:
            return False

    def cleanup_empty_folders(self, verbose):
        """Remove empty old folders after migration"""
        stats = {'checked': 0, 'removed': 0, 'errors': 0}
        media_root = settings.MEDIA_ROOT
        
        if not os.path.exists(media_root):
            return stats
        
        # List of old folder patterns to check and remove if empty
        old_folders_to_check = [
            'design_uploads',
            'temp_uploads',
            'invoices',
            'pdfs',
        ]
        
        # Check and remove old top-level folders
        for folder_name in old_folders_to_check:
            folder_path = os.path.join(media_root, folder_name)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                stats['checked'] += 1
                try:
                    # Check if folder is empty (recursively)
                    if self._is_folder_empty(folder_path):
                        os.rmdir(folder_path)
                        stats['removed'] += 1
                        if verbose:
                            self.stdout.write(self.style.SUCCESS(f'  ✓ Removed empty folder: {folder_name}/'))
                    else:
                        # Try to remove empty subdirectories
                        removed_subdirs = self._remove_empty_subdirs(folder_path, verbose)
                        stats['removed'] += removed_subdirs
                        # If folder is now empty, remove it
                        if self._is_folder_empty(folder_path):
                            os.rmdir(folder_path)
                            stats['removed'] += 1
                            if verbose:
                                self.stdout.write(self.style.SUCCESS(f'  ✓ Removed empty folder: {folder_name}/'))
                except Exception as e:
                    stats['errors'] += 1
                    if verbose:
                        self.stdout.write(self.style.ERROR(f'  ✗ Error removing {folder_name}/: {str(e)}'))
        
        # Check and remove old user/product folders (old structure: {user_id}/{product_id}/)
        # These should be empty after migration to {user_id}/designs/{product_id}/
        try:
            for user_folder in os.listdir(media_root):
                user_folder_path = os.path.join(media_root, user_folder)
                if not os.path.isdir(user_folder_path):
                    continue
                
                # Check if it's a numeric user folder (old structure)
                try:
                    user_id = int(user_folder)
                except ValueError:
                    continue
                
                # Check if this folder has old product subfolders (not in new structure)
                for item in os.listdir(user_folder_path):
                    item_path = os.path.join(user_folder_path, item)
                    if not os.path.isdir(item_path):
                        continue
                    
                    # Check if it's a numeric product_id folder (old structure)
                    # New structure would have 'designs', 'invoices', etc. as subfolders
                    try:
                        product_id = int(item)
                        # This is an old product folder structure
                        product_folder_path = item_path
                        if self._is_folder_empty(product_folder_path):
                            os.rmdir(product_folder_path)
                            stats['removed'] += 1
                            if verbose:
                                self.stdout.write(self.style.SUCCESS(
                                    f'  ✓ Removed old product folder: {user_folder}/{item}/'
                                ))
                    except ValueError:
                        # Not a numeric folder, skip
                        continue
                
                # If user folder is now empty (no subfolders), we could remove it
                # But be careful - it might have new structure folders
                # Only remove if it's completely empty
                if self._is_folder_empty(user_folder_path):
                    # Check if it's not part of new structure (should have subfolders like designs/, invoices/, etc.)
                    has_new_structure = any(
                        os.path.isdir(os.path.join(user_folder_path, subfolder))
                        for subfolder in ['designs', 'invoices', 'pdfs', 'uploads', 'temp', 'profile', 'documents', 'orders']
                    )
                    if not has_new_structure:
                        os.rmdir(user_folder_path)
                        stats['removed'] += 1
                        if verbose:
                            self.stdout.write(self.style.SUCCESS(
                                f'  ✓ Removed empty user folder: {user_folder}/'
                            ))
        except Exception as e:
            stats['errors'] += 1
        
        # Check media/ folder - only remove if it's empty or only has non-user files
        media_folder_path = os.path.join(media_root, 'media')
        if os.path.exists(media_folder_path) and os.path.isdir(media_folder_path):
            stats['checked'] += 1
            try:
                # Check if media/ folder is empty
                if self._is_folder_empty(media_folder_path):
                    os.rmdir(media_folder_path)
                    stats['removed'] += 1
                    if verbose:
                        self.stdout.write(self.style.SUCCESS('  ✓ Removed empty folder: media/'))
                else:
                    # Try to remove empty subdirectories in media/
                    removed_subdirs = self._remove_empty_subdirs(media_folder_path, verbose)
                    stats['removed'] += removed_subdirs
            except Exception as e:
                stats['errors'] += 1
                if verbose:
                    self.stdout.write(self.style.ERROR(f'  ✗ Error removing media/: {str(e)}'))
        
        return stats
    
    def _is_folder_empty(self, folder_path):
        """Check if a folder is empty (no files or subdirectories)"""
        try:
            return len(os.listdir(folder_path)) == 0
        except (OSError, PermissionError):
            return False
    
    def _remove_empty_subdirs(self, folder_path, verbose):
        """Recursively remove empty subdirectories"""
        removed_count = 0
        
        try:
            for root, dirs, files in os.walk(folder_path, topdown=False):
                # Remove empty directories (walking bottom-up)
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if self._is_folder_empty(dir_path):
                            os.rmdir(dir_path)
                            removed_count += 1
                            if verbose:
                                rel_path = os.path.relpath(dir_path, settings.MEDIA_ROOT)
                                self.stdout.write(self.style.SUCCESS(
                                    f'  ✓ Removed empty subdirectory: {rel_path}/'
                                ))
                    except (OSError, PermissionError) as e:
                        if verbose:
                            self.stdout.write(self.style.WARNING(
                                f'  ⊘ Could not remove {dir_path}: {str(e)}'
                            ))
        except Exception as e:
            pass
        
        return removed_count

    def print_summary(self, total_stats, dry_run):
        """Print migration summary"""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Migration Summary'))
        self.stdout.write('=' * 80 + '\n')

        for file_type, stats in total_stats.items():
            if stats['total'] == 0:
                continue

            self.stdout.write(f'\n{file_type.upper()}:')
            self.stdout.write(f'  Total: {stats["total"]}')
            self.stdout.write(self.style.SUCCESS(f'  ✓ Migrated: {stats["migrated"]}'))
            if stats['skipped'] > 0:
                self.stdout.write(self.style.WARNING(f'  ⊘ Skipped: {stats["skipped"]}'))
            if stats['errors'] > 0:
                self.stdout.write(self.style.ERROR(f'  ✗ Errors: {stats["errors"]}'))

        if dry_run:
            self.stdout.write('\n' + self.style.WARNING(
                'DRY RUN COMPLETE: No files were actually moved.\n'
                'Run without --dry-run to perform the migration.'
            ))
        else:
            self.stdout.write('\n' + self.style.SUCCESS('Migration completed!'))
        
        self.stdout.write('')

