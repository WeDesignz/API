# Visual Search Package

A reusable Python package for visual similarity search and image indexing. Designed for easy integration into Django applications.

## Features

- **Image Search**: Find similar images using CLIP embeddings
- **Batch Training**: Index multiple images with ProductId and MediaFileId
- **Garment Extraction**: Automatic garment region extraction using OWL-ViT + SAM2
- **Pattern Matching**: Multi-region pattern matching with consensus scoring
- **Auto-initialization**: All models initialize at import time for optimal performance

## Installation

1. Copy the `visual_search` directory to your Django project
2. Install dependencies:

```bash
pip install torch transformers pillow qdrant-client
```

3. (Optional) For garment extraction, install SAM2 and required dependencies:
```bash
# Install SAM2 (follow SAM2 installation instructions)
# Install ultralytics for YOLO: pip install ultralytics
# OWL-ViT is included with transformers
```

## Configuration

Set environment variables or modify `visual_search/config.py`:

```python
# Qdrant Configuration
VISUAL_SEARCH_QDRANT_URL = "your-qdrant-url"
VISUAL_SEARCH_QDRANT_API_KEY = "your-api-key"
VISUAL_SEARCH_QDRANT_HOST = "localhost"  # If using self-hosted
VISUAL_SEARCH_QDRANT_PORT = "6333"

# Model Configuration (optional)
VISUAL_SEARCH_MODEL_NAME = "patrickjohncyh/fashion-clip"
VISUAL_SEARCH_DESCRIPTION_MODEL = "Salesforce/blip-image-captioning-base"
VISUAL_SEARCH_COLLECTION_NAME = "patterns"
```

## Usage

### Search for Similar Images

```python
from visual_search import search_image
from PIL import Image

# Load your image
image = Image.open("path/to/image.jpg")

# Search for similar images
product_ids, extracted_image = search_image(image, num_results=20)

# product_ids: List of product ID strings
# extracted_image: PIL Image object of extracted garment region
```

### Train/Index Images

```python
from visual_search import train_images
from PIL import Image

# Prepare image data
images_data = [
    {
        'ProductId': 'prod123',
        'MediaFileId': 'media456',
        'image': Image.open("path/to/image1.jpg")
    },
    {
        'ProductId': 'prod124',
        'MediaFileId': 'media457',
        'image': Image.open("path/to/image2.jpg")
    },
    # ... more images
]

# Index images
results = train_images(images_data)

# results: List of dicts with 'ProductId' and 'isIndexed' (bool)
for result in results:
    print(f"ProductId: {result['ProductId']}, Indexed: {result['isIndexed']}")
```

## Django Integration Example

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
from visual_search import search_image, train_images
import json

@csrf_exempt
def search_view(request):
    if request.method == 'POST':
        # Get image from request
        image_file = request.FILES['image']
        image = Image.open(image_file)
        
        # Search
        product_ids, extracted_image = search_image(image)
        
        # Return results
        return JsonResponse({
            'product_ids': product_ids,
            'extracted_image': extracted_image  # You may want to convert to base64
        })

@csrf_exempt
def train_view(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        images_data = []
        
        # Process each image
        for item in data['images']:
            # Load image from your storage
            image = Image.open(item['image_path'])
            images_data.append({
                'ProductId': item['ProductId'],
                'MediaFileId': item['MediaFileId'],
                'image': image
            })
        
        # Train
        results = train_images(images_data)
        
        return JsonResponse({'results': results})
```

## Architecture

```
visual_search/
├── __init__.py          # Entry functions (search_image, train_images)
├── config.py            # Configuration settings
├── core/
│   ├── models.py        # Model initialization (singleton)
│   ├── search_engine.py # SearchEngine class
│   └── training_engine.py # TrainingEngine class
├── extractors/          # Garment extraction module
│   └── garment_extractor_owlvit_sam.py  # OWL-ViT + SAM2 extractor (default)
└── utils/
    └── collection_utils.py # Qdrant collection utilities
```

## Notes

- All models are initialized at import time (singleton pattern) for optimal performance
- The package uses OWL-ViT + SAM2 for garment extraction (default extractor)
- If garment extraction is not available, the full image is used for search
- ProductId and MediaFileId are stored in Qdrant payload for easy retrieval
- Search uses multi-region pattern matching with consensus scoring for better accuracy

## Requirements

- Python 3.8+
- PyTorch
- transformers
- PIL/Pillow
- qdrant-client
- (Optional) SAM2 for garment extraction

