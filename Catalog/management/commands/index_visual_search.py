"""
Management command to index product images into Qdrant for visual search (batch-wise).

Uses the visual_search package: loads images from Product media, encodes with CLIP,
and upserts vectors into the Qdrant collection. Processes in configurable batches.

Usage:
    python manage.py index_visual_search
    python manage.py index_visual_search --batch-size 50
    python manage.py index_visual_search --dry-run
    python manage.py index_visual_search --remaining  # skip products already indexed (is_indexed=True)
"""

import sys
from django.core.management.base import BaseCommand
from django.conf import settings
from PIL import Image
from Catalog.models import Product
from MediaFiles.models import Media
from common.relations import get_related
import os
import logging

logger = logging.getLogger(__name__)

# Only index PNG design images (per media storage: designs use .png)
IMAGE_EXTENSIONS = ('.png',)

def _set_huggingface_timeout(timeout_seconds=300):
    """Set longer HTTP timeout for Hugging Face Hub to avoid ReadTimeout when loading models."""
    try:
        from huggingface_hub import set_client_factory
        import httpx
        def make_client():
            return httpx.Client(timeout=httpx.Timeout(float(timeout_seconds)))
        set_client_factory(make_client)
    except Exception as e:

def get_visual_search():
    """Import visual_search from API project root."""
    api_root = str(settings.BASE_DIR)
    if api_root not in sys.path:
        sys.path.insert(0, api_root)
    from visual_search import train_images
    return train_images

class Command(BaseCommand):
    help = 'Index product images into Qdrant for visual search (batch-wise)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of images per batch (default: 50)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Collect and report what would be indexed without calling Qdrant',
        )
        parser.add_argument(
            '--remaining',
            action='store_true',
            help='Skip products already indexed (only index products with is_indexed=False)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Log each product/media being indexed',
        )
        parser.add_argument(
            '--hf-timeout',
            type=int,
            default=300,
            metavar='SECONDS',
            help='Hugging Face Hub HTTP timeout in seconds (default: 300)',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        dry_run = options['dry_run']
        remaining_only = options['remaining']
        verbose = options['verbose']
        hf_timeout = options.get('hf_timeout', 300)
        # Set longer timeout for Hugging Face before loading visual_search (avoids ReadTimeout)
        _set_huggingface_timeout(hf_timeout)
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if not media_root or not os.path.isdir(media_root):
            self.stderr.write(self.style.ERROR(f'MEDIA_ROOT not set or not a directory: {media_root}'))
            return

        # Products: active, visible; optionally only not yet indexed
        qs = Product.objects.filter(
            status='active',
            visibility_status='show',
        ).exclude(product_number__isnull=True).exclude(product_number='')
        if remaining_only and hasattr(Product, 'is_indexed'):
            qs = qs.filter(is_indexed=False)

        if dry_run:
            count = 0
            for product in qs.iterator():
                media_list = get_related(product, 'Product:Media', Media).filter(media_type='image')
                for media in media_list:
                    if not media.file:
                        continue
                    ext = os.path.splitext(media.file.name)[1].lower()
                    if ext not in IMAGE_EXTENSIONS:
                        continue
                    path = getattr(media.file, 'path', None) or os.path.join(media_root, media.file.name)
                    if os.path.isfile(path):
                        count += 1
            self.stdout.write(self.style.SUCCESS(f'[DRY RUN] Would index {count} images (PNG only) in batches of {batch_size}'))
            return

        train_images = get_visual_search()
        success = 0
        failed = 0
        total_media = 0
        batch_num = 0
        accum = []

        for product in qs.iterator():
            media_list = get_related(product, 'Product:Media', Media).filter(media_type='image')
            for media in media_list:
                if not media.file:
                    continue
                ext = os.path.splitext(media.file.name)[1].lower()
                if ext not in IMAGE_EXTENSIONS:
                    if verbose:
                        self.stdout.write(f'Skip (not PNG): {product.product_number} media {media.id} {media.file.name}')
                    continue
                path = getattr(media.file, 'path', None) or os.path.join(media_root, media.file.name)
                if not os.path.isfile(path):
                    if verbose:
                        self.stdout.write(f'Skip (file missing): {product.product_number} media {media.id} {media.file.name}')
                    continue
                try:
                    img = Image.open(path)
                    img.load()
                except Exception as e:
                    if verbose:
                        self.stdout.write(self.style.WARNING(f'Skip (open failed): {product.product_number} {path}: {e}'))
                    continue
                accum.append({
                    'ProductId': str(product.product_number),
                    'MediaFileId': str(media.id),
                    'image': img,
                })
                total_media += 1
                if verbose:
                    self.stdout.write(f'Queued: {product.product_number} media {media.id}')

                if len(accum) >= batch_size:
                    batch_num += 1
                    self.stdout.write(f'Indexing batch {batch_num} ({len(accum)} images)...')
                    try:
                        results = train_images(accum)
                        indexed_product_numbers = set()
                        for r in results:
                            if r.get('isIndexed'):
                                success += 1
                                indexed_product_numbers.add(r.get('ProductId'))
                            else:
                                failed += 1
                        if indexed_product_numbers and hasattr(Product, 'is_indexed'):
                            Product.objects.filter(product_number__in=indexed_product_numbers).update(is_indexed=True)
                    except Exception as e:
                        self.stderr.write(self.style.ERROR(f'Batch failed: {e}'))
                        failed += len(accum)
                    accum = []

        if accum:
            batch_num += 1
            self.stdout.write(f'Indexing batch {batch_num} ({len(accum)} images)...')
            try:
                results = train_images(accum)
                indexed_product_numbers = set()
                for r in results:
                    if r.get('isIndexed'):
                        success += 1
                        indexed_product_numbers.add(r.get('ProductId'))
                    else:
                        failed += 1
                if indexed_product_numbers and hasattr(Product, 'is_indexed'):
                    Product.objects.filter(product_number__in=indexed_product_numbers).update(is_indexed=True)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'Batch failed: {e}'))
                failed += len(accum)

        self.stdout.write(self.style.SUCCESS(f'Done. Total media: {total_media}, Indexed: {success}, Failed: {failed}'))
