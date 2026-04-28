import os
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import FileSystemStorage, default_storage, storages
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
        parser.add_argument(
            "--rewrite-visibility-structure",
            action="store_true",
            help=(
                "Rewrite Media files to visibility-aware structure. "
                "Design .avif files become public; all other migrated Media files become private."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skip_existing = options["skip_existing"]
        rewrite_visibility_structure = options["rewrite_visibility_structure"]

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

        mixed_storage = storages["mixed_media"] if "mixed_media" in storages.backends else default_storage
        private_storage = storages["private_media"] if "private_media" in storages.backends else default_storage

        media_model = None
        if rewrite_visibility_structure:
            from MediaFiles.models import Media
            media_model = Media

        uploaded = 0
        skipped = 0
        failed = 0

        self.stdout.write(f"Found {len(all_files)} file(s) under MEDIA_ROOT.")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no files will be uploaded."))

        for index, rel_path in enumerate(all_files, start=1):
            try:
                destination_storage = mixed_storage
                destination_path = rel_path
                visibility_value = None
                source_paths = [rel_path]

                # Files managed by explicit PrivateMediaStorage-backed fields.
                if rel_path.startswith("pdf_logos/") or rel_path.startswith("admin_pdf_clients/"):
                    destination_storage = private_storage
                    destination_path = rel_path
                elif rewrite_visibility_structure:
                    destination_path, visibility_value = self._map_media_destination(rel_path)
                    source_paths = self._build_source_candidates(rel_path, destination_path, visibility_value)

                if skip_existing and destination_storage.exists(destination_path):
                    skipped += 1
                    updated_rows = 0
                    if rewrite_visibility_structure and media_model and destination_path != rel_path:
                        updated_rows = self._update_media_references(
                            media_model,
                            source_paths,
                            destination_path,
                            visibility_value,
                        )
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{index}/{len(all_files)}] SKIP exists: {rel_path} -> {destination_path}"
                            + (f" | DB updated: {updated_rows}" if updated_rows else "")
                        )
                    )
                    continue

                if dry_run:
                    uploaded += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"[{index}/{len(all_files)}] DRY-RUN: {rel_path} -> {destination_path}"
                        )
                    )
                    continue

                with local_storage.open(rel_path, "rb") as fh:
                    destination_storage.save(destination_path, File(fh))

                if rewrite_visibility_structure and media_model and destination_path != rel_path:
                    self._update_media_references(
                        media_model,
                        source_paths,
                        destination_path,
                        visibility_value,
                    )

                uploaded += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{index}/{len(all_files)}] UPLOADED: {rel_path} -> {destination_path}"
                    )
                )
            except Exception as exc:
                failed += 1
                self.stderr.write(f"[{index}/{len(all_files)}] [ERROR] {rel_path}: {exc}")

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

    def _map_media_destination(self, rel_path: str):
        """
        Re-map legacy Media paths to new visibility-based structure.
        Returns (destination_path, visibility|None).
        """
        normalized = rel_path.strip("/").replace("\\", "/")
        parts = normalized.split("/")
        if len(parts) < 3:
            return normalized, None

        user_id = parts[0]
        if not user_id.isdigit():
            return normalized, None

        # Already in new structure (contains explicit visibility segment).
        if parts[1] == "designs" and len(parts) >= 5 and parts[3] in {"public", "private"}:
            return normalized, parts[3]
        if parts[1] in {"profile", "documents", "media"} and len(parts) >= 4 and parts[2] in {"public", "private"}:
            return normalized, parts[2]
        if parts[1] == "orders" and len(parts) >= 6 and parts[3] == "deliverables" and parts[4] in {"public", "private"}:
            return normalized, parts[4]

        # designs/{product_id}/{filename} -> designs/{product_id}/{visibility}/{filename}
        if parts[1] == "designs" and len(parts) >= 4:
            visibility = "public" if normalized.lower().endswith(".avif") else "private"
            return "/".join([parts[0], parts[1], parts[2], visibility, *parts[3:]]), visibility

        # profile/{filename}
        if parts[1] == "profile" and len(parts) >= 3:
            visibility = "private"
            return "/".join([parts[0], parts[1], visibility, *parts[2:]]), visibility

        # documents/{filename}
        if parts[1] == "documents" and len(parts) >= 3:
            visibility = "private"
            return "/".join([parts[0], parts[1], visibility, *parts[2:]]), visibility

        # orders/{order_id}/deliverables/{filename} -> orders/{order_id}/deliverables/{visibility}/{filename}
        if parts[1] == "orders" and len(parts) >= 5 and parts[3] == "deliverables":
            visibility = "private"
            return "/".join([parts[0], parts[1], parts[2], parts[3], visibility, *parts[4:]]), visibility

        # media/{filename} fallback
        if parts[1] == "media" and len(parts) >= 3:
            visibility = "private"
            return "/".join([parts[0], parts[1], visibility, *parts[2:]]), visibility

        return normalized, None

    def _build_source_candidates(self, rel_path: str, destination_path: str, visibility: str | None):
        """
        Build possible source DB paths that should be rewritten to destination_path.
        Includes legacy swapped designs path: designs/{visibility}/{product_id}/{filename}.
        """
        normalized = rel_path.strip("/").replace("\\", "/")
        candidates = {normalized}

        parts = normalized.split("/")
        if len(parts) >= 4 and parts[0].isdigit() and parts[1] == "designs":
            product_id = parts[2]
            filename = "/".join(parts[3:])
            if visibility in {"public", "private"}:
                candidates.add(f"{parts[0]}/designs/{visibility}/{product_id}/{filename}")

        if destination_path:
            candidates.add(destination_path.strip("/"))

        return list(candidates)

    def _update_media_references(self, media_model, source_paths, destination_path, visibility):
        update_payload = {"file": destination_path}
        if visibility in {"public", "private"}:
            update_payload["visibility"] = visibility
        return media_model.objects.filter(file__in=source_paths).exclude(file=destination_path).update(**update_payload)
