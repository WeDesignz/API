"""
Visual Search Package - Entry Functions for Django Integration

This package provides simple entry functions for image search and training.
All models are initialized at import time for optimal performance.

Usage:
    from visual_search import search_image, train_images
    
    # Search
    product_ids, extracted_image = search_image(image_object)
    
    # Training
    results = train_images([
        {
            'ProductId': 'prod123',
            'MediaFileId': 'media456',
            'image': image_object
        },
        ...
    ])
"""

from visual_search.core.models import get_models
from visual_search.core.search_engine import SearchEngine
from visual_search.core.training_engine import TrainingEngine
from typing import List, Dict, Tuple, Any
from PIL import Image

# Initialize models at import time (singleton pattern)
_models = get_models()
_search_engine = SearchEngine()
_training_engine = TrainingEngine()


def search_image(
    image: Image.Image,
    num_results: int = 20
) -> Tuple[List[str], Image.Image]:
    """
    Search for similar images and return product IDs and extracted image.
    
    Args:
        image: PIL Image object to search for
        num_results: Number of results to return (default: 20)
    
    Returns:
        Tuple of (list of product IDs, extracted image object)
        - product_ids: List of product ID strings from matching images
        - extracted_image: PIL Image object of the extracted garment region
    """
    return _search_engine.search(image, num_results)


def train_images(
    images_data: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Train/index multiple images with ProductId and MediaFileId.
    
    Args:
        images_data: List of dictionaries, each containing:
            - 'ProductId': str - Product identifier
            - 'MediaFileId': str - Media file identifier
            - 'image': PIL.Image - Image object to index
    
    Returns:
        List of dictionaries with:
            - 'ProductId': str - Product identifier
            - 'isIndexed': bool - Whether indexing was successful
    """
    return _training_engine.train_batch(images_data)

