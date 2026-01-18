"""
Training Engine for Visual Search.
Handles batch indexing of images with ProductId and MediaFileId.
"""
import uuid
from typing import List, Dict, Any
from PIL import Image
from qdrant_client.http.models import PointStruct, Batch, PointsBatch

from visual_search.core.models import get_models
from visual_search.config import COLLECTION_NAME, BATCH_SIZE
from visual_search.utils.collection_utils import ensure_collection_exists


class TrainingEngine:
    """
    Handles batch training/indexing of images.
    """
    
    def __init__(self):
        """Initialize training engine with models."""
        embedding_model, image_describer, qdrant_client = get_models()
        self.model = embedding_model
        self.describer = image_describer
        self.client = qdrant_client
        
        # Ensure collection exists
        ensure_collection_exists(self.client)
    
    def train_batch(
        self,
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
        results = []
        
        # Process in batches
        for i in range(0, len(images_data), BATCH_SIZE):
            batch = images_data[i:i + BATCH_SIZE]
            batch_results = self._process_batch(batch)
            results.extend(batch_results)
        
        return results
    
    def _process_batch(
        self,
        batch: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process a single batch of images."""
        ids = []
        vectors = []
        payloads = []
        batch_results = []
        
        for item in batch:
            product_id = item.get('ProductId')
            media_file_id = item.get('MediaFileId')
            image = item.get('image')
            
            if not product_id or not media_file_id or not image:
                batch_results.append({
                    'ProductId': product_id or 'unknown',
                    'isIndexed': False
                })
                continue
            
            try:
                # Ensure image is PIL Image and RGB
                if not isinstance(image, Image.Image):
                    raise ValueError("Image must be a PIL Image object")
                
                img = image.convert("RGB")
                
                # Encode image
                vector = self.model.encode_image(img)
                
                # Generate description (optional, can fail)
                description = None
                try:
                    description = self.describer.describe(img)
                except Exception as exc:
                    print(f"Description generation failed for ProductId {product_id}: {exc}")
                
                # Create point ID (use UUID string)
                point_id = str(uuid.uuid4())
                
                # Create payload with ProductId and MediaFileId
                payload = {
                    "ProductId": str(product_id),
                    "MediaFileId": str(media_file_id),
                    "description": description,
                }
                
                ids.append(point_id)
                vectors.append(vector)
                payloads.append(payload)
                
                batch_results.append({
                    'ProductId': str(product_id),
                    'isIndexed': True
                })
                
            except Exception as exc:
                print(f"Failed to index image for ProductId {product_id}: {exc}")
                batch_results.append({
                    'ProductId': str(product_id),
                    'isIndexed': False
                })
        
        # Upload batch to Qdrant
        if ids:
            try:
                self.client.http.points_api.upsert_points(
                    collection_name=COLLECTION_NAME,
                    wait=True,
                    point_insert_operations=PointsBatch(
                        batch=Batch(
                            ids=ids,
                            vectors=vectors,
                            payloads=payloads,
                        )
                    ),
                )
                print(f"[INFO] Successfully indexed {len(ids)} images")
            except Exception as exc:
                print(f"[ERROR] Failed to upload batch: {exc}")
                # Mark all in batch as failed
                for result in batch_results:
                    if result['isIndexed']:
                        result['isIndexed'] = False
        
        return batch_results

