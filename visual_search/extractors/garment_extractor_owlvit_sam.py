"""
Garment region extraction using YOLO first, then OWL-ViT as fallback if SAM2 fails, and SAM2 for masking.

Flow:
1. YOLO detects bounding boxes for class 0 (person)
2. If YOLO detects boxes: try SAM2 on YOLO boxes
   - If SAM2 succeeds: use YOLO boxes
   - If SAM2 fails: run OWL-ViT and use OWL-ViT boxes
3. If YOLO doesn't detect: run OWL-ViT on whole image, then SAM2
4. SAM2 generates masks from the final selected boxes
"""
from __future__ import annotations

import numpy as np
from typing import List, Optional
from PIL import Image
import torch
import os

try:
    from transformers import OwlViTProcessor, OwlViTForObjectDetection
    OWLVIT_AVAILABLE = True
except ImportError:
    OWLVIT_AVAILABLE = False

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

try:
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    SAM2_AVAILABLE = True
except ImportError:
    SAM2_AVAILABLE = False


class OwlViTSAMGarmentExtractor:
    """
    Extractor: YOLO (class 0 detection) -> SAM2 -> OWL-ViT (fallback if SAM2 fails) -> SAM2.
    Uses YOLO first, if YOLO finds boxes try SAM2, if SAM2 fails use OWL-ViT, otherwise fallback to OWL-ViT if YOLO fails.
    """

    def __init__(
        self,
        owlvit_model: str = "google/owlvit-base-patch32",
        yolo_model: str = "yolov8n.pt",
        sam2_model: str = "facebook/sam2-hiera-base-plus",
        text_prompt: str = "t-shirt, shirt, garment, clothing",
        owlvit_threshold: float = 0.1,
        yolo_conf_threshold: float = 0.25,
        device: str = "cpu",
    ):
        """
        Initialize OWL-ViT + YOLO + SAM2 extractor.
        
        Args:
            owlvit_model: OWL-ViT model name from Hugging Face
            yolo_model: YOLO model path (default: yolov8n.pt)
            sam2_model: SAM2 model name from Hugging Face
            text_prompt: Text prompt for OWL-ViT detection
            owlvit_threshold: Confidence threshold for OWL-ViT detections
            yolo_conf_threshold: Confidence threshold for YOLO detections
            device: Device to run inference on
        """
        if not OWLVIT_AVAILABLE:
            raise ImportError("transformers with OwlViT is required for OwlViTSAMGarmentExtractor")
        if not YOLO_AVAILABLE:
            raise ImportError("ultralytics is required for OwlViTSAMGarmentExtractor")
        if not SAM2_AVAILABLE:
            raise ImportError("sam2 is required for OwlViTSAMGarmentExtractor")

        actual_device = device if (device == "cuda" and torch.cuda.is_available()) else "cpu"
        self.device = actual_device
        self.owlvit_threshold = owlvit_threshold
        self.yolo_conf_threshold = yolo_conf_threshold
        self.text_prompt = text_prompt

        # Load OWL-ViT
        print(f"[INFO] Loading OWL-ViT model: {owlvit_model}")
        self.owlvit_processor = OwlViTProcessor.from_pretrained(owlvit_model)
        self.owlvit_model = OwlViTForObjectDetection.from_pretrained(owlvit_model)
        self.owlvit_model.to(self.device)
        self.owlvit_model.eval()

        # Load YOLO
        yolo_model = os.environ.get("YOLO_MODEL_PATH", yolo_model)
        print(f"[INFO] Loading YOLO model: {yolo_model}")
        self.yolo = YOLO(yolo_model)
        self.yolo.to(self.device)
        print(f"[INFO] YOLO classes: {self.yolo.names}")

        # Load SAM2
        print(f"[INFO] Loading SAM2 model: {sam2_model} (device: {actual_device})")
        self.sam2_predictor = SAM2ImagePredictor.from_pretrained(sam2_model, device=actual_device)

        print(f"[INFO] OWL-ViT + YOLO + SAM2 extractor initialized successfully")

    def _detect_boxes_owlvit(self, img: Image.Image) -> List[dict]:
        """
        Run OWL-ViT and return list of detection dictionaries with bbox, text, score.
        """
        # Prepare text queries - split prompt into individual queries
        text_queries = [query.strip() for query in self.text_prompt.split(",")]
        texts = [text_queries]
        
        # Resize if image is too large (max 1024px on longest side)
        original_size = img.size
        max_size = 1024
        scale_factor = 1.0
        
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img_resized = img.resize(new_size, Image.Resampling.LANCZOS)
            scale_factor = original_size[0] / new_size[0]
        else:
            img_resized = img
        
        # Process inputs
        inputs = self.owlvit_processor(text=texts, images=img_resized, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Perform inference
        with torch.no_grad():
            outputs = self.owlvit_model(**inputs)

        # Post-process outputs
        target_sizes = torch.tensor([img_resized.size[::-1]], device=self.device)
        results = self.owlvit_processor.post_process_object_detection(
            outputs=outputs,
            threshold=self.owlvit_threshold,
            target_sizes=target_sizes,
        )[0]

        detections = []
        text_queries_list = text_queries
        
        for box, score, label in zip(results["boxes"], results["scores"], results["labels"]):
            # Scale box back to original image size if resized
            bbox = box.cpu().numpy()
            if scale_factor != 1.0:
                bbox = bbox * scale_factor
            
            # Clamp to original image boundaries
            bbox[0] = max(0, min(original_size[0], bbox[0]))
            bbox[1] = max(0, min(original_size[1], bbox[1]))
            bbox[2] = max(0, min(original_size[0], bbox[2]))
            bbox[3] = max(0, min(original_size[1], bbox[3]))
            
            # Get text label
            label_idx = label.item()
            if label_idx < len(text_queries_list):
                text = text_queries_list[label_idx]
            else:
                text = "garment"
            
            detections.append({
                "bbox": bbox,
                "text": text,
                "score": float(score.item()),
            })
        
        return detections

    def _detect_boxes_yolo(self, img: Image.Image, class_id: int = 0) -> List[np.ndarray]:
        """
        Run YOLO and return list of [x1,y1,x2,y2] boxes (float) for specified class.
        
        Args:
            img: Input PIL image
            class_id: Class ID to detect (0 = person by default)
        
        Returns:
            List of bounding boxes as numpy arrays
        """
        results = self.yolo.predict(img, verbose=False, conf=self.yolo_conf_threshold, device=self.device)
        boxes = []
        for r in results:
            if r.boxes is None:
                continue
            for b, c in zip(r.boxes.xyxy, r.boxes.cls):
                cls_id = int(c.item())
                if cls_id == class_id:
                    boxes.append(b.cpu().numpy())
        return boxes

    def _detect_with_yolo_then_owlvit(self, img: Image.Image) -> List[dict]:
        """
        Detect using YOLO first, then OWL-ViT as fallback.
        If YOLO detected boxes: use them directly (skip OWL-ViT).
        If YOLO didn't detect: run OWL-ViT on whole image.
        
        Args:
            img: Original full image
        
        Returns:
            List of detection dictionaries with bbox, text, score
        """
        # Step 1: YOLO detection
        print("[INFO] Step 1: YOLO detection (class 0)...")
        yolo_boxes = self._detect_boxes_yolo(img, class_id=0)
        
        if yolo_boxes:
            # YOLO detected boxes - use them directly, skip OWL-ViT
            print(f"[INFO] YOLO detected {len(yolo_boxes)} boxes, using YOLO detections (skipping OWL-ViT)")
            detections = []
            for yolo_box in yolo_boxes:
                detections.append({
                    "bbox": yolo_box,
                    "text": "person",
                    "score": 0.8,
                })
            return detections
        else:
            # YOLO didn't detect - run OWL-ViT on whole image
            print("[INFO] YOLO didn't detect boxes, running OWL-ViT on whole image...")
            owlvit_detections = self._detect_boxes_owlvit(img)
            
            if owlvit_detections:
                print(f"[INFO] OWL-ViT found {len(owlvit_detections)} detections on whole image")
                return owlvit_detections
            else:
                print("[WARN] Neither YOLO nor OWL-ViT detected any boxes")
                return []

    def _generate_masks(self, img: Image.Image, detections: List[dict]) -> List[np.ndarray]:
        """
        Generate masks for detected regions using SAM2.
        
        Returns:
            List of boolean mask arrays
        """
        if not detections:
            return []
        
        image_np = np.array(img)
        h, w = image_np.shape[:2]
        self.sam2_predictor.set_image(image_np)
        
        masks = []
        for det in detections:
            bbox = det["bbox"].copy()
            x1, y1, x2, y2 = bbox
            
            # Clamp to image boundaries
            x1_clamped = max(0, min(w - 1, int(round(x1))))
            y1_clamped = max(0, min(h - 1, int(round(y1))))
            x2_clamped = max(0, min(w, int(round(x2))))
            y2_clamped = max(0, min(h, int(round(y2))))
            
            if x2_clamped <= x1_clamped or y2_clamped <= y1_clamped:
                continue
            
            clamped_bbox = np.array([x1_clamped, y1_clamped, x2_clamped, y2_clamped])
            
            masks_np, scores, _ = self.sam2_predictor.predict(
                box=clamped_bbox,
                multimask_output=True,
            )
            if masks_np.size == 0:
                continue
            
            # Use best mask
            best_idx = int(np.argmax(scores))
            mask = masks_np[best_idx].astype(bool)
            masks.append(mask)
        
        return masks

    def _extract_masked_region(self, img: Image.Image, mask: np.ndarray) -> Optional[Image.Image]:
        """
        Extract masked region with tight crop and background removal.
        """
        base = np.array(img.convert("RGB"))
        h, w = base.shape[:2]
        
        if mask.shape[:2] != (h, w):
            from PIL import Image as PILImage
            mask_img = PILImage.fromarray(mask.astype(np.uint8) * 255)
            mask_img = mask_img.resize((w, h), PILImage.NEAREST)
            mask = np.array(mask_img) > 127
        
        # Get bounding box from mask (tight crop)
        ys, xs = np.where(mask)
        if ys.size == 0 or xs.size == 0:
            return None
        
        x1 = max(0, int(xs.min()))
        y1 = max(0, int(ys.min()))
        x2 = min(w, int(xs.max()) + 1)
        y2 = min(h, int(ys.max()) + 1)
        
        if x2 <= x1 or y2 <= y1:
            return None
        
        # Crop mask and image to bounding box
        mask_cropped = mask[y1:y2, x1:x2]
        base_cropped = base[y1:y2, x1:x2]
        
        # Apply mask to remove background (white background where mask is False)
        masked_rgb = np.ones_like(base_cropped) * 255  # White background
        masked_rgb[mask_cropped] = base_cropped[mask_cropped]  # Original pixels where mask is True
        
        return Image.fromarray(masked_rgb)

    def extract_region(self, img: Image.Image, region_type: str = "auto") -> Optional[Image.Image]:
        """
        Extract garment region using YOLO -> SAM2 (if SAM2 fails, use OWL-ViT) -> SAM2 pipeline.
        
        Args:
            img: Input PIL image
            region_type: "auto" (uses YOLO + SAM2 check + OWL-ViT fallback + SAM2 pipeline)
        
        Returns:
            Extracted region as PIL Image with background removed, or original image if extraction fails
        """
        # Step 1: YOLO detection
        print("[INFO] Step 1: YOLO detection (class 0)...")
        yolo_boxes = self._detect_boxes_yolo(img, class_id=0)
        
        detections = []
        use_owlvit = False
        
        if yolo_boxes:
            # YOLO detected boxes - try SAM2 on them first
            print(f"[INFO] YOLO detected {len(yolo_boxes)} boxes, trying SAM2...")
            yolo_detections = [{"bbox": box, "text": "person", "score": 0.8} for box in yolo_boxes]
            masks = self._generate_masks(img, yolo_detections)
            
            if masks:
                # SAM2 succeeded with YOLO boxes
                print(f"[INFO] SAM2 successfully generated {len(masks)} masks from YOLO boxes")
                detections = yolo_detections
            else:
                # SAM2 failed with YOLO boxes - fallback to OWL-ViT
                print("[WARN] SAM2 failed to generate masks from YOLO boxes, falling back to OWL-ViT...")
                use_owlvit = True
        else:
            # YOLO didn't detect - use OWL-ViT
            print("[INFO] YOLO didn't detect boxes, using OWL-ViT...")
            use_owlvit = True
        
        # Step 2: OWL-ViT if needed
        if use_owlvit:
            print("[INFO] Step 2: OWL-ViT detection...")
            owlvit_detections = self._detect_boxes_owlvit(img)
            
            if not owlvit_detections:
                print("[WARN] No detections found (neither YOLO nor OWL-ViT), using original image")
                return img
            
            print(f"[INFO] OWL-ViT found {len(owlvit_detections)} detections")
            detections = owlvit_detections
        
        # Step 3: SAM2 generates masks from final detections
        print("[INFO] Step 3: SAM2 mask generation...")
        masks = self._generate_masks(img, detections)
        if not masks:
            print("[WARN] No masks generated, using original image")
            return img
        
        # Select the mask with the largest pixel count
        mask_with_pixels = []
        for det, mask in zip(detections, masks):
            pixel_count = int(np.sum(mask))
            mask_with_pixels.append((mask, pixel_count, det))
        
        if not mask_with_pixels:
            return img
        
        largest_mask, total_pixels, best_detection = max(mask_with_pixels, key=lambda x: x[1])
        print(f"[INFO] Selected largest mask: {total_pixels:,} pixels (score: {best_detection['score']:.3f})")
        
        # Extract masked region
        extracted = self._extract_masked_region(img, largest_mask)
        if extracted is None:
            return img
        
        # Ensure minimum size
        if extracted.size[0] < 50 or extracted.size[1] < 50:
            return img
        
        return extracted

    def extract_pattern_focused_regions(self, img: Image.Image) -> List[Image.Image]:
        """
        Extract multiple pattern-focused regions from the provided garment image.
        """
        if img is None:
            return []
        
        full_region = img
        if full_region.size[0] < 50 or full_region.size[1] < 50:
            return [full_region]
        
        regions = [full_region]
        rw, rh = full_region.size
        
        def add_crop(box: tuple) -> None:
            crop = full_region.crop(box)
            if crop.size[0] > 50 and crop.size[1] > 50:
                regions.append(crop)
        
        # 2. Left side strip
        if rw > 100:
            add_crop((0, rh // 8, rw // 2, 7 * rh // 8))
        
        # 3. Right side strip
        if rw > 100:
            add_crop((rw // 2, rh // 8, rw, 7 * rh // 8))
        
        # 4. Center horizontal strip
        if rw > 100 and rh > 150:
            add_crop((rw // 5, rh // 3, 4 * rw // 5, 2 * rh // 3))
        
        # 5. Center 70% x 70% region
        if rw > 100 and rh > 100:
            left_margin = int(rw * 0.15)
            right_margin = int(rw * 0.15)
            top_margin = int(rh * 0.15)
            bottom_margin = int(rh * 0.15)
            add_crop((left_margin, top_margin, rw - right_margin, rh - bottom_margin))
        
        return regions

