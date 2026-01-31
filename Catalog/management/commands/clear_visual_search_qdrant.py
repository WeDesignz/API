"""
Management command to delete Qdrant vector data for visual search.

Deletes the visual search collection (all vectors). The collection can be
recreated on next index or next search (ensure_collection_exists).

Usage:
    python manage.py clear_visual_search_qdrant
    python manage.py clear_visual_search_qdrant --no-input  # skip confirmation
"""

import sys
from django.core.management.base import BaseCommand
from django.conf import settings


def get_qdrant_client_and_collection():
    """Import visual_search config and create Qdrant client from API project root."""
    api_root = str(settings.BASE_DIR)
    if api_root not in sys.path:
        sys.path.insert(0, api_root)
    from visual_search.config import (
        COLLECTION_NAME,
        QDRANT_URL,
        QDRANT_API_KEY,
        QDRANT_HOST,
        QDRANT_PORT,
    )
    from qdrant_client import QdrantClient

    if QDRANT_URL:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    else:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return client, COLLECTION_NAME


class Command(BaseCommand):
    help = 'Delete Qdrant vector data for visual search (removes the collection)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        no_input = options['no_input']
        try:
            client, collection_name = get_qdrant_client_and_collection()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to connect to Qdrant: {e}'))
            return

        try:
            collections = client.get_collections()
            names = [c.name for c in collections.collections]
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to list collections: {e}'))
            return

        if collection_name not in names:
            self.stdout.write(self.style.WARNING(f'Collection "{collection_name}" does not exist. Nothing to delete.'))
            return

        if not no_input:
            confirm = input(f'Delete collection "{collection_name}" and all its vectors? [y/N]: ')
            if confirm.lower() != 'y':
                self.stdout.write('Aborted.')
                return

        try:
            client.delete_collection(collection_name=collection_name)
            self.stdout.write(self.style.SUCCESS(f'Deleted collection "{collection_name}".'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Failed to delete collection: {e}'))
