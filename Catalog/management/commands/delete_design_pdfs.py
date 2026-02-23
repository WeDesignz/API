"""
Management command to delete design PDF files from disk.

Only deletes PDF files for design downloads (Catalog.PDFDownload).
Never touches invoice PDFs, receipts, or other documents.

Design PDF paths:
  - pdfs/pdf_download_{id}.pdf (legacy)
  - {user_id}/pdfs/pdf_download_{id}.pdf (user-specific)

Usage:
    python manage.py delete_design_pdfs
    python manage.py delete_design_pdfs --dry-run  # show what would be deleted without deleting
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings

from Catalog.models import PDFDownload


class Command(BaseCommand):
    help = 'Delete design PDF files from disk (PDFDownload only). Never touches invoices or other PDFs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        media_root = getattr(settings, 'MEDIA_ROOT', None)

        if not media_root:
            self.stderr.write(self.style.ERROR('MEDIA_ROOT is not set.'))
            return

        if not os.path.isdir(media_root):
            self.stderr.write(self.style.ERROR(f'MEDIA_ROOT "{media_root}" is not a directory.'))
            return

        qs = PDFDownload.objects.filter(pdf_file_path__isnull=False).exclude(pdf_file_path='')
        total = qs.count()

        if total == 0:
            self.stdout.write('No PDF download records with file paths found.')
            return

        self.stdout.write(f'Found {total} PDF download record(s) with file paths.')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no files will be deleted.\n'))

        deleted = 0
        skipped = 0
        errors = 0

        for pdf_download in qs:
            rel_path = (pdf_download.pdf_file_path or '').strip()
            if not rel_path:
                continue

            full_path = os.path.normpath(os.path.join(media_root, rel_path))

            # Safety: ensure path is under MEDIA_ROOT
            media_norm = os.path.normpath(media_root)
            if not full_path.startswith(media_norm):
                self.stdout.write(self.style.WARNING(f'  Skipping path outside MEDIA_ROOT: {rel_path}'))
                skipped += 1
                continue

            if not os.path.isfile(full_path):
                if dry_run:
                    self.stdout.write(f'  Would skip (file not found): {rel_path}')
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f'  Would delete: {rel_path}')
                deleted += 1
                continue

            try:
                os.unlink(full_path)
                self.stdout.write(self.style.SUCCESS(f'  Deleted: {rel_path}'))
                deleted += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  Failed to delete {rel_path}: {e}'))
                errors += 1

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Dry run would delete {deleted} file(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} file(s).'))
        if skipped:
            self.stdout.write(f'Skipped {skipped} (not found or outside scope).')
        if errors:
            self.stderr.write(self.style.ERROR(f'Errors: {errors}'))
