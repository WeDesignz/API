import os
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Upload existing local MEDIA_ROOT files to current default storage (S3)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be uploaded without uploading.",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Skip files that already exist in destination storage.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_existing = options["skip_existing"]

        if not getattr(settings, "USE_S3", False):
            raise CommandError("USE_S3 is False. Enable S3 first, then run this command.")

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists() or not media_root.is_dir():
            raise CommandError(f"MEDIA_ROOT does not exist or is not a directory: {media_root}")

        local_storage = FileSystemStorage(location=str(media_root))
        all_files = [
            path
            for path in self._iter_relative_files(media_root)
            if not path.startswith("static/")
        ]

        if not all_files:
            self.stdout.write(self.style.WARNING("No local media files found to migrate."))
            return

        uploaded = 0
        skipped = 0
        failed = 0

        self.stdout.write(f"Found {len(all_files)} file(s) under MEDIA_ROOT.")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no files will be uploaded."))

        for rel_path in all_files:
            try:
                if skip_existing and default_storage.exists(rel_path):
                    skipped += 1
                    continue

                if dry_run:
                    uploaded += 1
                    continue

                with local_storage.open(rel_path, "rb") as fh:
                    default_storage.save(rel_path, File(fh))
                uploaded += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(f"[ERROR] {rel_path}: {exc}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Uploaded: {uploaded}"))
        self.stdout.write(self.style.WARNING(f"Skipped: {skipped}"))
        if failed:
            self.stdout.write(self.style.ERROR(f"Failed: {failed}"))
        else:
            self.stdout.write(self.style.SUCCESS("Failed: 0"))

    def _iter_relative_files(self, media_root: Path):
        for base, _, files in os.walk(media_root):
            for filename in files:
                full_path = Path(base) / filename
                yield str(full_path.relative_to(media_root)).replace("\\", "/")
