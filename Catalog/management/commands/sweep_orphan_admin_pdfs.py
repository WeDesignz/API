"""
Management command to delete orphaned admin PDF client files from disk.

Finds all files under MEDIA_ROOT/admin_pdf_clients/ and removes any that are
not referenced by a PDFClientJob (pdf_file_paths or zip_file_path). Use this
when job records were deleted without the post_delete signal (e.g. bulk delete
or before the signal existed).

Usage:
    python manage.py sweep_orphan_admin_pdfs
    python manage.py sweep_orphan_admin_pdfs --dry-run  # show what would be deleted
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings

from Catalog.models import PDFClientJob


def _normalize_rel_path(path):
    """Normalize path for comparison: forward slashes, no leading slash."""
    if not path:
        return ""
    p = (path or "").strip().replace("\\", "/")
    return p.lstrip("/")


def _collect_referenced_paths(media_root):
    """Return a set of normalized relative paths referenced by PDFClientJob."""
    admin_prefix = "admin_pdf_clients"
    media_norm = os.path.normpath(media_root)
    referenced = set()
    for job in PDFClientJob.objects.all():
        for rel in job.pdf_file_paths or []:
            r = _normalize_rel_path(rel)
            if r.startswith(admin_prefix):
                referenced.add(r)
        if job.zip_file_path:
            r = _normalize_rel_path(job.zip_file_path)
            if r.startswith(admin_prefix):
                referenced.add(r)
    return referenced


def _collect_disk_paths(media_root, admin_dir):
    """Walk admin_pdf_clients dir and return set of relative file paths (normalized)."""
    disk_paths = []
    admin_prefix = "admin_pdf_clients"
    media_norm = os.path.normpath(media_root)
    if not os.path.isdir(admin_dir):
        return disk_paths
    for root, _dirs, files in os.walk(admin_dir, topdown=True):
        for name in files:
            full = os.path.join(root, name)
            full_norm = os.path.normpath(full)
            if not full_norm.startswith(media_norm):
                continue
            rel = os.path.relpath(full_norm, media_norm)
            rel_norm = _normalize_rel_path(rel.replace("\\", "/"))
            if rel_norm.startswith(admin_prefix):
                disk_paths.append((rel_norm, full_norm))
    return disk_paths


class Command(BaseCommand):
    help = (
        "Delete orphaned files under admin_pdf_clients/ that are not "
        "referenced by any PDFClientJob."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        media_root = getattr(settings, "MEDIA_ROOT", None)

        if not media_root:
            self.stderr.write(self.style.ERROR("MEDIA_ROOT is not set."))
            return

        if not os.path.isdir(media_root):
            self.stderr.write(
                self.style.ERROR(f'MEDIA_ROOT "{media_root}" is not a directory.')
            )
            return

        admin_dir = os.path.join(media_root, "admin_pdf_clients")
        if not os.path.isdir(admin_dir):
            self.stdout.write(
                f'Directory "admin_pdf_clients/" not found under MEDIA_ROOT. Nothing to sweep.'
            )
            return

        referenced = _collect_referenced_paths(media_root)
        disk_paths = _collect_disk_paths(media_root, admin_dir)

        orphaned = [(rel, full) for rel, full in disk_paths if rel not in referenced]
        deleted = 0
        errors = 0

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN - no files will be deleted.\n")
            )

        if not orphaned:
            self.stdout.write("No orphaned files under admin_pdf_clients/.")
            return

        self.stdout.write(f"Found {len(orphaned)} orphaned file(s).\n")

        for rel_path, full_path in orphaned:
            if not os.path.isfile(full_path):
                continue
            if dry_run:
                self.stdout.write(f"  Would delete: {rel_path}")
                deleted += 1
                continue
            try:
                os.unlink(full_path)
                self.stdout.write(self.style.SUCCESS(f"  Deleted: {rel_path}"))
                deleted += 1
            except OSError as e:
                self.stderr.write(
                    self.style.ERROR(f"  Failed to delete {rel_path}: {e}")
                )
                errors += 1

        self.stdout.write("")
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Dry run would delete {deleted} file(s).")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} file(s)."))
        if errors:
            self.stderr.write(self.style.ERROR(f"Errors: {errors}"))
