"""
Example usage of Visual Search package.

This file demonstrates how to use the visual_search package
in a Django application or standalone Python script.
"""

from PIL import Image
from visual_search import search_image, train_images


def example_search():
    """Example: Search for similar images."""
    # Load an image
    image = Image.open("path/to/your/image.jpg")
    
    # Search for similar images
    product_ids, extracted_image = search_image(image, num_results=20)
    
    print(f"Found {len(product_ids)} similar products:")
    for product_id in product_ids:
        print(f"  - Product ID: {product_id}")
    
    # extracted_image is a PIL Image object of the extracted garment region
    # You can save it or convert to base64 for API responses
    extracted_image.save("extracted_region.jpg")
    
    return product_ids, extracted_image


def example_training():
    """Example: Train/index multiple images."""
    # Prepare your image data
    images_data = [
        {
            'ProductId': 'PROD001',
            'MediaFileId': 'MEDIA001',
            'image': Image.open("path/to/image1.jpg")
        },
        {
            'ProductId': 'PROD002',
            'MediaFileId': 'MEDIA002',
            'image': Image.open("path/to/image2.jpg")
        },
        {
            'ProductId': 'PROD003',
            'MediaFileId': 'MEDIA003',
            'image': Image.open("path/to/image3.jpg")
        },
    ]
    
    # Index the images
    results = train_images(images_data)
    
    # Check results
    for result in results:
        status = "✓" if result['isIndexed'] else "✗"
        print(f"{status} ProductId: {result['ProductId']}, Indexed: {result['isIndexed']}")
    
    return results


def example_django_view():
    """
    Example Django view integration.
    
    This is a template for how you might integrate visual_search
    into your Django application.
    """
    from django.http import JsonResponse
    from django.views.decorators.csrf import csrf_exempt
    from visual_search import search_image, train_images
    from PIL import Image
    import json
    import base64
    from io import BytesIO
    
    @csrf_exempt
    def search_api(request):
        """Django view for image search."""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST method required'}, status=405)
        
        try:
            # Get image from request
            if 'image' not in request.FILES:
                return JsonResponse({'error': 'No image provided'}, status=400)
            
            image_file = request.FILES['image']
            image = Image.open(image_file)
            
            # Get num_results from request (optional)
            num_results = int(request.POST.get('num_results', 20))
            
            # Search
            product_ids, extracted_image = search_image(image, num_results=num_results)
            
            # Convert extracted image to base64 for response
            buffered = BytesIO()
            extracted_image.save(buffered, format="PNG")
            extracted_image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            return JsonResponse({
                'success': True,
                'product_ids': product_ids,
                'extracted_image': f'data:image/png;base64,{extracted_image_base64}',
                'count': len(product_ids)
            })
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    @csrf_exempt
    def train_api(request):
        """Django view for batch training."""
        if request.method != 'POST':
            return JsonResponse({'error': 'POST method required'}, status=405)
        
        try:
            # Parse JSON body
            data = json.loads(request.body)
            
            if 'images' not in data:
                return JsonResponse({'error': 'No images provided'}, status=400)
            
            images_data = []
            
            # Process each image
            for item in data['images']:
                # Validate required fields
                if 'ProductId' not in item or 'MediaFileId' not in item or 'image' not in item:
                    continue
                
                # Decode base64 image if provided as string
                if isinstance(item['image'], str):
                    # Assume base64 encoded
                    image_data = base64.b64decode(item['image'])
                    image = Image.open(BytesIO(image_data))
                else:
                    # Assume PIL Image or file path
                    if isinstance(item['image'], Image.Image):
                        image = item['image']
                    else:
                        image = Image.open(item['image'])
                
                images_data.append({
                    'ProductId': item['ProductId'],
                    'MediaFileId': item['MediaFileId'],
                    'image': image
                })
            
            # Train
            results = train_images(images_data)
            
            return JsonResponse({
                'success': True,
                'results': results,
                'total': len(results),
                'indexed': sum(1 for r in results if r['isIndexed'])
            })
        
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return search_api, train_api


if __name__ == "__main__":
    print("Visual Search Package - Example Usage")
    print("=" * 50)
    print("\n1. Example Search:")
    print("   product_ids, extracted_image = example_search()")
    print("\n2. Example Training:")
    print("   results = example_training()")
    print("\n3. Django Integration:")
    print("   See example_django_view() function for Django view templates")

