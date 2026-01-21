# Visual Search Package - Integration Guide

## Overview

This package provides two main entry functions for visual search and image indexing:

1. **`search_image(image, num_results=20)`** - Search for similar images
2. **`train_images(images_data)`** - Index multiple images with ProductId and MediaFileId

## Quick Start

### 1. Copy the Package

Copy the entire `visual_search` directory to your Django project root or Python path.

### 2. Install Dependencies

```bash
pip install -r visual_search/requirements.txt
```

### 3. Configure

Set environment variables or edit `visual_search/config.py`:

```python
# Required: Qdrant connection
VISUAL_SEARCH_QDRANT_URL = "your-qdrant-cloud-url"
VISUAL_SEARCH_QDRANT_API_KEY = "your-api-key"

# OR for self-hosted:
VISUAL_SEARCH_QDRANT_HOST = "localhost"
VISUAL_SEARCH_QDRANT_PORT = "6333"
```

### 4. Use in Your Code

```python
from visual_search import search_image, train_images
from PIL import Image

# Search
image = Image.open("query.jpg")
product_ids, extracted_image = search_image(image)

# Train
images_data = [
    {
        'ProductId': 'prod123',
        'MediaFileId': 'media456',
        'image': Image.open("image1.jpg")
    }
]
results = train_images(images_data)
```

## Function Details

### `search_image(image, num_results=20)`

**Input:**
- `image`: PIL Image object
- `num_results`: Number of results to return (default: 20)

**Output:**
- `product_ids`: List of product ID strings
- `extracted_image`: PIL Image object of extracted garment region

**Example:**
```python
from PIL import Image
from visual_search import search_image

image = Image.open("query.jpg")
product_ids, extracted_image = search_image(image, num_results=10)

print(f"Found {len(product_ids)} matches:")
for pid in product_ids:
    print(f"  - {pid}")

# Save extracted region
extracted_image.save("extracted.jpg")
```

### `train_images(images_data)`

**Input:**
- `images_data`: List of dictionaries, each containing:
  - `ProductId`: str - Product identifier (required)
  - `MediaFileId`: str - Media file identifier (required)
  - `image`: PIL.Image - Image object to index (required)

**Output:**
- List of dictionaries with:
  - `ProductId`: str - Product identifier
  - `isIndexed`: bool - Whether indexing was successful

**Example:**
```python
from PIL import Image
from visual_search import train_images

images_data = [
    {
        'ProductId': 'PROD001',
        'MediaFileId': 'MEDIA001',
        'image': Image.open("image1.jpg")
    },
    {
        'ProductId': 'PROD002',
        'MediaFileId': 'MEDIA002',
        'image': Image.open("image2.jpg")
    }
]

results = train_images(images_data)

for result in results:
    if result['isIndexed']:
        print(f"✓ Indexed: {result['ProductId']}")
    else:
        print(f"✗ Failed: {result['ProductId']}")
```

## Django Integration

### Search View

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
from visual_search import search_image
import base64
from io import BytesIO

@csrf_exempt
def search_view(request):
    if request.method == 'POST':
        try:
            # Get image from request
            image_file = request.FILES['image']
            image = Image.open(image_file)
            
            # Get num_results (optional)
            num_results = int(request.POST.get('num_results', 20))
            
            # Search
            product_ids, extracted_image = search_image(image, num_results)
            
            # Convert extracted image to base64
            buffered = BytesIO()
            extracted_image.save(buffered, format="PNG")
            extracted_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            return JsonResponse({
                'success': True,
                'product_ids': product_ids,
                'extracted_image': f'data:image/png;base64,{extracted_base64}',
                'count': len(product_ids)
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
```

### Training View

```python
# views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
from visual_search import train_images
import json
import base64
from io import BytesIO

@csrf_exempt
def train_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            images_data = []
            
            for item in data['images']:
                # Decode base64 image
                image_data = base64.b64decode(item['image_base64'])
                image = Image.open(BytesIO(image_data))
                
                images_data.append({
                    'ProductId': item['ProductId'],
                    'MediaFileId': item['MediaFileId'],
                    'image': image
                })
            
            # Train
            results = train_images(images_data)
            
            return JsonResponse({
                'success': True,
                'results': results
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
```

## Package Structure

```
visual_search/
├── __init__.py              # Entry functions (search_image, train_images)
├── config.py                # Configuration (can override with env vars)
├── requirements.txt         # Python dependencies
├── README.md               # Package documentation
├── example_usage.py        # Usage examples
├── core/
│   ├── models.py           # Model initialization (singleton)
│   ├── search_engine.py    # SearchEngine class
│   └── training_engine.py  # TrainingEngine class
├── extractors/             # Garment extraction module
│   └── garment_extractor_owlvit_sam.py  # OWL-ViT + SAM2 extractor (default)
└── utils/
    └── collection_utils.py # Qdrant collection utilities
```

## Important Notes

1. **Model Initialization**: All models (CLIP, BLIP, Qdrant client) are initialized at import time. This means the first import may take some time, but subsequent calls are fast.

2. **ProductId Storage**: When indexing images, ProductId and MediaFileId are stored in the Qdrant payload. During search, ProductId is extracted from the payload and returned.

3. **Garment Extraction**: The package uses OWL-ViT + SAM2 for garment extraction (default extractor). If not available, it uses the full image.

4. **Error Handling**: Both functions handle errors gracefully:
   - `search_image`: Returns empty list if no matches found
   - `train_images`: Returns `isIndexed: false` for failed images

5. **Batch Processing**: `train_images` automatically processes images in batches for optimal performance.

## Environment Variables

All configuration can be overridden via environment variables:

- `VISUAL_SEARCH_QDRANT_URL` - Qdrant cloud URL
- `VISUAL_SEARCH_QDRANT_API_KEY` - Qdrant API key
- `VISUAL_SEARCH_QDRANT_HOST` - Qdrant host (self-hosted)
- `VISUAL_SEARCH_QDRANT_PORT` - Qdrant port (self-hosted)
- `VISUAL_SEARCH_MODEL_NAME` - CLIP model name (default: "patrickjohncyh/fashion-clip")
- `VISUAL_SEARCH_DESCRIPTION_MODEL` - BLIP model name
- `VISUAL_SEARCH_COLLECTION_NAME` - Qdrant collection name (default: "patterns")
- `VISUAL_SEARCH_NUM_RESULTS` - Default number of search results
- `VISUAL_SEARCH_HNSW_EF` - HNSW search accuracy parameter

## Troubleshooting

1. **Import Error**: Make sure all dependencies are installed: `pip install -r visual_search/requirements.txt`

2. **Qdrant Connection Error**: Check your Qdrant URL/API key or host/port settings

3. **Model Download**: First run will download models from HuggingFace (may take time)

4. **Memory Issues**: If you have memory constraints, consider using CPU-only mode or smaller models

## Support

For issues or questions, refer to the main README.md or check the example_usage.py file.

