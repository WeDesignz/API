"""
Shared helpers for picking public display image URLs on landing-page catalog endpoints.
"""

from __future__ import annotations

import os
import re

from MediaFiles.models import Relation


def _absolute_url(url: str | None, request) -> str | None:
    if not url:
        return None
    if request and url.startswith('/'):
        return request.build_absolute_uri(url)
    return url


def _normalize_display_url(url: str | None) -> str | None:
    """Use flat public design paths for browser display."""
    if not url:
        return None
    normalized = url.replace('/designs/private/', '/designs/')
    normalized = re.sub(r'/designs/(\d+)/public/', r'/designs/\1/', normalized, flags=re.IGNORECASE)
    normalized = re.sub(r'/designs/(\d+)/private/', r'/designs/\1/', normalized, flags=re.IGNORECASE)
    return normalized


def _relation_meta(product, media_obj):
    try:
        relation = Relation.objects.filter(
            relation_type='Product:Media',
            id_1=product.pk,
            id_2=media_obj.pk,
        ).first()
        if relation and relation.meta:
            return relation.meta
    except Exception:
        pass
    return None


def _classify_media(product, media_obj):
    file_name = media_obj.file.name if getattr(media_obj, 'file', None) else ''
    if not file_name:
        return None

    file_name_lower = file_name.lower()
    base_name = os.path.splitext(os.path.basename(file_name_lower))[0]
    meta = _relation_meta(product, media_obj)

    is_mockup = base_name == 'mockup' or base_name.endswith('_mockup') or '_mockup' in base_name
    if not is_mockup and meta:
        if isinstance(meta, dict):
            is_mockup = bool(meta.get('is_mockup')) or meta.get('type') == 'mockup'
        elif isinstance(meta, str):
            meta_lower = meta.lower()
            is_mockup = 'mockup' in meta_lower or '"is_mockup":true' in meta_lower

    is_avif = file_name_lower.endswith('.avif')
    if not is_avif and meta and isinstance(meta, dict):
        is_avif = bool(meta.get('is_avif'))

    is_jpg_png = file_name_lower.endswith(('.jpg', '.jpeg', '.png'))
    is_image = is_avif or is_jpg_png or any(
        file_name_lower.endswith(ext) for ext in ('.gif', '.webp')
    )

    media_type = getattr(media_obj, 'media_type', 'image') or 'image'
    if media_type.lower() != 'image' or not is_image:
        return None

    try:
        url = media_obj.file.url
    except Exception:
        return None

    return {
        'url': url,
        'is_avif': is_avif,
        'is_mockup': is_mockup,
        'is_jpg_png': is_jpg_png,
        'file_name': file_name,
    }


def _pick_best_media(candidates: list[dict]) -> dict | None:
    if not candidates:
        return None

    def sort_key(item: dict):
        return (
            0 if item['is_avif'] and item['is_jpg_png'] and not item['is_mockup'] else
            1 if item['is_avif'] and item['is_mockup'] else
            2 if item['is_jpg_png'] and not item['is_mockup'] else
            3 if item['is_mockup'] else
            4 if item['is_avif'] else 5,
            item['file_name'],
        )

    return sorted(candidates, key=sort_key)[0]


def get_product_display_image_url(product, request=None) -> str | None:
    """
    Return the best image URL for public landing-page display.
    Prefers AVIF design thumbnails, then JPG/PNG, then mockups.
    """
    try:
        media_list = list(product.get_media())
    except Exception:
        media_list = []

    candidates = []
    for media_obj in media_list:
        if not getattr(media_obj, 'file', None):
            continue
        classified = _classify_media(product, media_obj)
        if classified:
            candidates.append(classified)

    best = _pick_best_media(candidates)
    if not best:
        return None

    return _normalize_display_url(_absolute_url(best['url'], request))
