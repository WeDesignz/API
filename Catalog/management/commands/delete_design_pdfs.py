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

from Catalog.models import PDFDownload, PDFClientJob


class Command(BaseCommand):
    help = 'Delete design PDF files from disk (PDFDownload and admin PDF client jobs only). Never touches invoices or other PDFs.'

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

        pdf_qs = PDFDownload.objects.filter(pdf_file_path__isnull=False).exclude(pdf_file_path='')
        total_pdf_downloads = pdf_qs.count()

        self.stdout.write(f'Found {total_pdf_downloads} PDFDownload record(s) with file paths.')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no files will be deleted.\n'))

        deleted = 0
        skipped = 0
        errors = 0

        media_norm = os.path.normpath(media_root)

        # Delete customer/mock PDF files (PDFDownload)
        for pdf_download in pdf_qs:
            rel_path = (pdf_download.pdf_file_path or '').strip()
            if not rel_path:
                continue

            full_path = os.path.normpath(os.path.join(media_root, rel_path))

            if not full_path.startswith(media_norm):
                self.stdout.write(self.style.WARNING(f'  [PDFDownload] Skipping path outside MEDIA_ROOT: {rel_path}'))
                skipped += 1
                continue

            if not os.path.isfile(full_path):
                if dry_run:
                    self.stdout.write(f'  [PDFDownload] Would skip (file not found): {rel_path}')
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f'  [PDFDownload] Would delete: {rel_path}')
                deleted += 1
                continue

            try:
                os.unlink(full_path)
                self.stdout.write(self.style.SUCCESS(f'  [PDFDownload] Deleted: {rel_path}'))
                deleted += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'  [PDFDownload] Failed to delete {rel_path}: {e}'))
                errors += 1

        # Delete admin PDF client job files (only under admin_pdf_clients/)
        self.stdout.write('\nChecking admin PDF client job files under "admin_pdf_clients/".')
        jobs = PDFClientJob.objects.all()
        for job in jobs:
            paths = list(job.pdf_file_paths or [])
            if job.zip_file_path:
                paths.append(job.zip_file_path)

            for rel_path in paths:
                rel_path_str = str(rel_path or '').strip()
                if not rel_path_str:
                    continue

                # Safety: only touch files under admin_pdf_clients/
                if not rel_path_str.startswith('admin_pdf_clients/'):
                    self.stdout.write(self.style.WARNING(f'  [PDFClientJob] Skipping non-admin path: {rel_path_str}'))
                    skipped += 1
                    continue

                full_path = os.path.normpath(os.path.join(media_root, rel_path_str))
                if not full_path.startswith(media_norm):
                    self.stdout.write(self.style.WARNING(f'  [PDFClientJob] Skipping path outside MEDIA_ROOT: {rel_path_str}'))
                    skipped += 1
                    continue

                if not os.path.isfile(full_path):
                    if dry_run:
                        self.stdout.write(f'  [PDFClientJob] Would skip (file not found): {rel_path_str}')
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(f'  [PDFClientJob] Would delete: {rel_path_str}')
                    deleted += 1
                    continue

                try:
                    os.unlink(full_path)
                    self.stdout.write(self.style.SUCCESS(f'  [PDFClientJob] Deleted: {rel_path_str}'))
                    deleted += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'  [PDFClientJob] Failed to delete {rel_path_str}: {e}'))
                    errors += 1

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'Dry run would delete {deleted} file(s).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Deleted {deleted} file(s).'))
        if skipped:
            self.stdout.write(f'Skipped {skipped} (not found, outside scope, or non-admin paths).')
        if errors:
            self.stderr.write(self.style.ERROR(f'Errors: {errors}'))
