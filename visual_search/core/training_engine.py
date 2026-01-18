"""
Training Engine for Visual Search.
Handles batch indexing of images with ProductId and MediaFileId.
"""
import math
import uuid
from typing import List, Dict, Any
from PIL import Image
from qdrant_client import models

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
                if hasattr(vector, "tolist"):
                    vector = vector.tolist()
                
                # Ensure vector is a list and check its length
                if not isinstance(vector, list):
                    vector = list(vector)
                
                # Check vector length
                if len(vector) == 0:
                    raise ValueError(f"Encoded vector is empty for ProductId {product_id}")
                
                # Check for NaN or invalid values and fix them - ensure we preserve length
                cleaned_vector = []
                has_nan = False
                for v in vector:
                    try:
                        val = float(v)
                        if math.isnan(val) or math.isinf(val):
                            has_nan = True
                            val = 0.0
                        cleaned_vector.append(val)
                    except (TypeError, ValueError):
                        has_nan = True
                        cleaned_vector.append(0.0)
                
                if has_nan:
                    print(f"[WARN] Vector for ProductId {product_id} contains NaN/Inf values, replaced with zeros (length: {len(cleaned_vector)})")
                
                vector = cleaned_vector
                
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
                # Prepare points - ensure vectors are proper Python lists of floats
                points = []
                for point_id, vector, payload in zip(ids, vectors, payloads):
                    # Ensure vector is a plain Python list of floats
                    if not isinstance(vector, list):
                        if hasattr(vector, "tolist"):
                            vector = vector.tolist()
                        else:
                            vector = list(vector)
                    
                    # Verify vector length and content
                    if len(vector) == 0:
                        print(f"[ERROR] Vector is empty for point {point_id}, skipping")
                        continue
                    
                    # Final check: ensure all are valid floats (should already be done above, but double-check)
                    try:
                        cleaned = []
                        for v in vector:
                            val = float(v)
                            if math.isnan(val) or math.isinf(val):
                                val = 0.0
                            cleaned.append(val)
                        vector = cleaned
                        
                        # Verify length matches expected (512)
                        if len(vector) != 512:
                            print(f"[ERROR] Vector length mismatch: expected 512, got {len(vector)} for point {point_id}")
                            continue
                    except (TypeError, ValueError) as e:
                        print(f"[ERROR] Cannot convert vector to floats: {e}")
                        continue
                    
                    # Create PointStruct - use string ID
                    point = models.PointStruct(
                        id=str(point_id),  # Ensure string
                        vector=vector,      # Plain list of floats
                        payload=payload or {}  # Ensure payload is dict
                    )
                    points.append(point)
                
                # Batch upsert all points
                self.client.upsert(
                    collection_name=COLLECTION_NAME,
                    wait=True,
                    points=points
                )
                print(f"[INFO] Successfully indexed {len(ids)} images")
            except Exception as exc:
                import traceback
                error_msg = str(exc)
                print(f"[ERROR] Failed to upload batch: {error_msg}")
                print(f"[ERROR] Exception type: {type(exc).__name__}")
                # Try to provide more context
                if "VectorStruct" in error_msg:
                    print(f"[ERROR] VectorStruct error - checking first vector:")
                    if vectors:
                        v = vectors[0]
                        print(f"  Type: {type(v)}, Is list: {isinstance(v, list)}")
                        if isinstance(v, list):
                            print(f"  Length: {len(v)}, First 3: {v[:3]}")
                            print(f"  Element types: {[type(x) for x in v[:3]]}")
                traceback.print_exc()
                # Mark all in batch as failed
                for result in batch_results:
                    if result['isIndexed']:
                        result['isIndexed'] = False
        
        return batch_results