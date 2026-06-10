"""
Remove public/private visibility segments from design media paths.

Fixes two legacy layouts:
  - Swapped:   {user_id}/designs/{visibility}/{product_id}/{filename}
               e.g. 4/designs/private/3066/WDG00002921.jpg
  - Nested:    {user_id}/designs/{product_id}/{visibility}/{filename}
               e.g. 4/designs/3066/private/WDG00002921.jpg

Target layout:
  - Flat:      {user_id}/designs/{product_id}/{filename}
               e.g. 4/designs/3066/WDG00002921.jpg

Updates Media.file paths in the database and moves objects in storage.

Usage:
    python manage.py flatten_design_media_paths --dry-run --verbose
    python manage.py flatten_design_media_paths
    python manage.py flatten_design_media_paths --avif-only
    python manage.py flatten_design_media_paths --product-id 3066 --verbose
"""

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db.models import Q

from MediaFiles.models import Media


def flatten_design_path(path: str) -> str | None:
    """
    Return a flattened design path without public/private segments.
    Returns None when the path is already flat or not a design path.
    """
    normalized = path.strip("/").replace("\\", "/")
    parts = normalized.split("/")
    if len(parts) < 5 or parts[1] != "designs" or not parts[0].isdigit():
        return None

    user_id = parts[0]

    # Swapped: designs/{visibility}/{product_id}/{filename...}
    if parts[2] in {"public", "private"} and parts[3].isdigit():
        product_id = parts[3]
        filename = "/".join(parts[4:])
        if not filename:
            return None
        return f"{user_id}/designs/{product_id}/{filename}"

    # Nested: designs/{product_id}/{visibility}/{filename...}
    if parts[2].isdigit() and parts[3] in {"public", "private"}:
        product_id = parts[2]
        filename = "/".join(parts[4:])
        if not filename:
            return None
        return f"{user_id}/designs/{product_id}/{filename}"

    return None


def path_layout(path: str) -> str | None:
    """Return 'swapped', 'nested', or None for design paths that need flattening."""
    normalized = path.strip("/").replace("\\", "/")
    parts = normalized.split("/")
    if len(parts) < 5 or parts[1] != "designs" or not parts[0].isdigit():
        return None
    if parts[2] in {"public", "private"} and parts[3].isdigit():
        return "swapped"
    if parts[2].isdigit() and parts[3] in {"public", "private"}:
        return "nested"
    return None


def extract_product_id_from_design_path(path: str) -> int | None:
    flattened = flatten_design_path(path) or path.strip("/").replace("\\", "/")
    parts = flattened.split("/")
    if len(parts) >= 4 and parts[1] == "designs" and parts[2].isdigit():
        return int(parts[2])
    return None


class Command(BaseCommand):
    help = "Flatten design media paths by removing public/private segments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without moving files or updating the database",
        )
        parser.add_argument(
            "--avif-only",
            action="store_true",
            help="Only flatten .avif files (default: all design file formats)",
        )
        parser.add_argument(
            "--product-id",
            type=int,
            help="Process only media linked to a specific product ID in the path",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print each file processed",
        )
        parser.add_argument(
            "--delete-source",
            action="store_true",
            help="Delete the old storage object after a successful move",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        avif_only = options["avif_only"]
        product_id_filter = options.get("product_id")
        verbose = options["verbose"]
        delete_source = options["delete_source"]

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 80))
        self.stdout.write(self.style.SUCCESS("Flatten Design Media Paths"))
        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no files or database rows will change\n"))
        if avif_only:
            self.stdout.write("Scope: .avif files only\n")
        else:
            self.stdout.write("Scope: all design file formats (jpg, png, avif, eps, cdr, ...)\n")

        stats = {
            "scanned": 0,
            "flattened": 0,
            "swapped": 0,
            "nested": 0,
            "skipped_filter": 0,
            "target_exists_db_only": 0,
            "errors": 0,
        }
        errors = []

        media_qs = (
            Media.objects.exclude(file="")
            .filter(Q(file__contains="/designs/private/") | Q(file__contains="/designs/public/"))
            .order_by("id")
        )
        self.stdout.write(f"Scanning {media_qs.count()} Media record(s) with public/private path segments...\n")

        for media in media_qs.iterator():
            stats["scanned"] += 1
            current_path = media.file.name
            target_path = flatten_design_path(current_path)
            layout = path_layout(current_path)

            if not target_path or target_path == current_path:
                continue

            if avif_only and not current_path.lower().endswith(".avif"):
                stats["skipped_filter"] += 1
                continue

            if product_id_filter is not None:
                path_product_id = extract_product_id_from_design_path(current_path)
                if path_product_id != product_id_filter:
                    stats["skipped_filter"] += 1
                    continue

            if layout == "swapped":
                stats["swapped"] += 1
            elif layout == "nested":
                stats["nested"] += 1

            if verbose:
                self.stdout.write(f"Media {media.id} ({layout}):")
                self.stdout.write(f"  from: {current_path}")
                self.stdout.write(f"  to:   {target_path}")

            new_visibility = "public" if target_path.lower().endswith(".avif") else media.visibility

            if default_storage.exists(target_path):
                stats["target_exists_db_only"] += 1
                if verbose:
                    self.stdout.write(self.style.WARNING("  target already exists in storage, updating DB only"))
                if not dry_run:
                    Media.objects.filter(pk=media.pk).update(file=target_path, visibility=new_visibility)
                    if delete_source and current_path != target_path and default_storage.exists(current_path):
                        default_storage.delete(current_path)
                stats["flattened"] += 1
                continue

            if not default_storage.exists(current_path):
                stats["errors"] += 1
                msg = f"Media {media.id}: source missing: {current_path}"
                errors.append(msg)
                if verbose:
                    self.stdout.write(self.style.ERROR(f"  {msg}"))
                continue

            if dry_run:
                stats["flattened"] += 1
                if verbose:
                    self.stdout.write(self.style.WARNING("  dry-run: would move and update"))
                continue

            try:
                with default_storage.open(current_path, "rb") as source_file:
                    default_storage.save(target_path, source_file)

                Media.objects.filter(pk=media.pk).update(file=target_path, visibility=new_visibility)

                if delete_source and current_path != target_path and default_storage.exists(current_path):
                    default_storage.delete(current_path)

                stats["flattened"] += 1
                if verbose:
                    self.stdout.write(self.style.SUCCESS("  moved and updated"))
            except Exception as exc:
                stats["errors"] += 1
                msg = f"Media {media.id}: {exc}"
                errors.append(msg)
                if verbose:
                    self.stdout.write(self.style.ERROR(f"  {msg}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Scanned: {stats['scanned']}"))
        self.stdout.write(self.style.SUCCESS(f"Flattened: {stats['flattened']}"))
        self.stdout.write(f"  swapped paths (designs/private/{{id}}/...): {stats['swapped']}")
        self.stdout.write(f"  nested paths (designs/{{id}}/private/...): {stats['nested']}")
        self.stdout.write(f"DB-only updates (target already in storage): {stats['target_exists_db_only']}")
        self.stdout.write(f"Skipped by filter: {stats['skipped_filter']}")
        if stats["errors"]:
            self.stdout.write(self.style.ERROR(f"Errors: {stats['errors']}"))
            for msg in errors[:20]:
                self.stdout.write(self.style.ERROR(f"  - {msg}"))
            if len(errors) > 20:
                self.stdout.write(self.style.ERROR(f"  ... and {len(errors) - 20} more"))
        else:
            self.stdout.write(self.style.SUCCESS("Errors: 0"))
