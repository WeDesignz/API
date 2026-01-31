"""
Search Engine for Visual Search.
Handles image similarity search and returns product IDs.
"""
import time
from typing import List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

from visual_search.core.models import get_models
from visual_search.config import COLLECTION_NAME, HNSW_EF, NUM_RESULTS
from visual_search.utils.collection_utils import ensure_collection_exists

# Import OWL-ViT + SAM2 garment extractor (default extractor)
try:
    from visual_search.extractors.garment_extractor_owlvit_sam import OwlViTSAMGarmentExtractor
    OWLVIT_SAM_EXTRACTOR_AVAILABLE = True
except ImportError:
    OWLVIT_SAM_EXTRACTOR_AVAILABLE = False
    OwlViTSAMGarmentExtractor = None


class SearchEngine:
    """
    Handles image similarity search operations.
    """
    
    def __init__(self):
        """Initialize search engine with models and extractors."""
        embedding_model, image_describer, qdrant_client = get_models()
        self.model = embedding_model
        self.describer = image_describer
        self.client = qdrant_client
        
        # Ensure collection exists
        ensure_collection_exists(self.client)
        
        # Initialize OWL-ViT + SAM2 garment extractor (default extractor)
        self.garment_extractor = None
        if OWLVIT_SAM_EXTRACTOR_AVAILABLE and OwlViTSAMGarmentExtractor:
            try:
                self.garment_extractor = OwlViTSAMGarmentExtractor()
                print("[INFO] Using OWL-ViT + SAM2 for garment extraction")
            except Exception as exc:
                print(f"[WARN] OWL-ViT + SAM2 extractor initialization failed: {exc}")
                print("[WARN] Garment extraction will be disabled")
        else:
            print("[WARN] OWL-ViT + SAM2 extractor not available. Garment extraction will be disabled")
    
    def search(
        self,
        image: Image.Image,
        num_results: int = NUM_RESULTS
    ) -> Tuple[List[str], Image.Image]:
        """
        Search for similar images and return product IDs and extracted image.
        
        Args:
            image: PIL Image object to search for
            num_results: Number of results to return
        
        Returns:
            Tuple of (list of product IDs, extracted image object)
        """
        # Convert to RGB if needed
        img = image.convert("RGB")
        
        # Extract garment region if extractor is available
        extracted_image = img
        if self.garment_extractor:
            try:
                extracted_region = self.garment_extractor.extract_region(img, region_type="auto")
                if extracted_region and extracted_region.size[0] > 50 and extracted_region.size[1] > 50:
                    extracted_image = extracted_region
            except Exception as exc:
                print(f"Garment extraction failed: {exc}, using original image")
        
        # Extract pattern regions (70% width × 90% height + additional regions)
        regions_to_search = self._extract_pattern_regions(extracted_image)
        
        # Encode and search
        all_hits = {}
        hit_scores_by_region = {}
        region_weights = [1.0] + [0.85] * (len(regions_to_search) - 1)
        
        # Batch encode all regions
        query_vectors = self.model.encode_images_batch(regions_to_search)
        
        # Search limit
        search_limit = max(num_results * 3, num_results + 40)
        
        # Parallelize Qdrant searches (qdrant_client uses query_points, not search)
        def search_region(idx: int, query_vector: list, weight: float):
            """Search Qdrant for a single region and return weighted hits."""
            response = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                query_filter=None,
                with_payload=True,
                limit=search_limit,
                search_params=None,
            )
            hits = response.points
            return idx, hits, weight
        
        # Execute searches in parallel
        with ThreadPoolExecutor(max_workers=min(len(regions_to_search), 4)) as executor:
            futures = [
                executor.submit(search_region, idx, vec, region_weights[idx] if idx < len(region_weights) else 0.7)
                for idx, vec in enumerate(query_vectors)
            ]
            for future in as_completed(futures):
                idx, hits, weight = future.result()
                
                # Aggregate by point ID with weighted scores
                for hit in hits:
                    point_id = hit.id
                    weighted_score = hit.score * weight
                    
                    if point_id not in all_hits:
                        all_hits[point_id] = hit
                        hit_scores_by_region[point_id] = []
                    
                    hit_scores_by_region[point_id].append(weighted_score)
        
        # Calculate final scores using consensus-based aggregation
        for point_id, hit in all_hits.items():
            region_scores = hit_scores_by_region.get(point_id, [])
            if not region_scores:
                continue
            
            num_regions_found = len(region_scores)
            max_score = max(region_scores)
            avg_score = sum(region_scores) / len(region_scores)
            consensus_ratio = num_regions_found / len(regions_to_search)
            
            if num_regions_found >= 2:
                consensus_bonus = consensus_ratio * 0.1
                final_score = avg_score * (1.0 + consensus_bonus)
            else:
                final_score = max_score * 0.95
            
            hit.score = min(1.0, final_score)
        
        # Sort by score and get top results
        sorted_hits = sorted(all_hits.values(), key=lambda x: x.score, reverse=True)
        final_results = sorted_hits[:num_results]
        
        # Extract product IDs from results
        product_ids = []
        for hit in final_results:
            # Get ProductId from payload, fallback to point ID if not available
            payload = hit.payload if hit.payload is not None else {}
            product_id = payload.get("ProductId")
            if not product_id:
                product_id = str(hit.id)
            product_ids.append(str(product_id))
        
        return product_ids, extracted_image
    
    def _extract_pattern_regions(self, img: Image.Image) -> List[Image.Image]:
        """Extract pattern-focused regions from the image."""
        regions = []
        w, h = img.size
        
        if w > 100 and h > 100:
            # Create 70% width × 90% height crop
            left_margin = int(w * 0.15)
            right_margin = int(w * 0.15)
            top_margin = int(h * 0.05)
            bottom_margin = int(h * 0.05)
            main_crop = img.crop((left_margin, top_margin, w - right_margin, h - bottom_margin))
            regions.append(main_crop)
            
            # Extract additional regions from main crop
            cw, ch = main_crop.size
            if cw > 80 and ch > 80:
                # Top third
                top_third = main_crop.crop((0, 0, cw, int(ch * 0.33)))
                if top_third.size[0] > 50 and top_third.size[1] > 50:
                    regions.append(top_third)
                
                # Middle third
                middle_third = main_crop.crop((0, int(ch * 0.33), cw, int(ch * 0.67)))
                if middle_third.size[0] > 50 and middle_third.size[1] > 50:
                    regions.append(middle_third)
                
                # Bottom third
                bottom_third = main_crop.crop((0, int(ch * 0.67), cw, ch))
                if bottom_third.size[0] > 50 and bottom_third.size[1] > 50:
                    regions.append(bottom_third)
                
                # Center square
                center_square = main_crop.crop((
                    int(cw * 0.2),
                    int(ch * 0.2),
                    int(cw * 0.8),
                    int(ch * 0.8)
                ))
                if center_square.size[0] > 50 and center_square.size[1] > 50:
                    regions.append(center_square)
        else:
            regions.append(img)
        
        return regions

