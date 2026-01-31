"""
Model initialization and singleton management.
All models are initialized once at import time for optimal performance.
"""
import torch
from typing import Optional, Tuple
from PIL import Image
from transformers import CLIPModel, CLIPProcessor, BlipForConditionalGeneration, BlipProcessor
from qdrant_client import QdrantClient

from visual_search.config import (
    MODEL_NAME, VECTOR_SIZE, DESCRIPTION_MODEL,
    QDRANT_URL, QDRANT_API_KEY, QDRANT_HOST, QDRANT_PORT
)


class EmbeddingModel:
    """
    Wraps a CLIP model (via HuggingFace transformers) for image embeddings.
    """
    
    def __init__(self, model_name: str, vector_size: int):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[INFO] Initializing CLIP model '{model_name}' on {self.device}...")
        self.model = CLIPModel.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=False,
        ).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.vector_size = vector_size
        print(f"[INFO] CLIP model initialized successfully")
    
    def _get_embedding_tensor(self, outputs):
        """Unwrap CLIP output: newer transformers return BaseModelOutputWithPooling with .pooler_output."""
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            return outputs.pooler_output
        if hasattr(outputs, "last_hidden_state"):
            return outputs.last_hidden_state[:, 0, :]
        return outputs

    def encode_image(self, img: Image.Image) -> list:
        """Encode a PIL image into a vector using CLIP's image encoder."""
        inputs = self.processor(images=img, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            out = self.model.get_image_features(**inputs)
            embeddings = self._get_embedding_tensor(out)
            embeddings = embeddings / embeddings.norm(p=2, dim=-1, keepdim=True)
        return embeddings.squeeze(0).cpu().tolist()

    def encode_images_batch(self, images: list) -> list:
        """Batch encode multiple images for faster processing."""
        inputs = self.processor(images=images, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            out = self.model.get_image_features(**inputs)
            embeddings = self._get_embedding_tensor(out)
            embeddings = embeddings / embeddings.norm(p=2, dim=-1, keepdim=True)
        return embeddings.cpu().tolist()


class ImageDescriber:
    """
    Generates natural-language descriptions for pattern images.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        model_id = model_name or DESCRIPTION_MODEL
        print(f"[INFO] Initializing BLIP model '{model_id}' on {self.device}...")
        self.processor = BlipProcessor.from_pretrained(model_id)
        self.model = BlipForConditionalGeneration.from_pretrained(
            model_id,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=False,
        ).to(self.device)
        print(f"[INFO] BLIP model initialized successfully")
    
    def describe(self, img: Image.Image) -> str:
        """Generate a description for the image."""
        inputs = self.processor(images=img, return_tensors="pt").to(self.device)
        with torch.no_grad():
            output_ids = self.model.generate(
                **inputs, max_new_tokens=40, num_beams=3, early_stopping=True
            )
        caption = self.processor.decode(output_ids[0], skip_special_tokens=True)
        return caption.strip()


def create_qdrant_client() -> QdrantClient:
    """Instantiate QdrantClient using either URL/API key (cloud) or host/port (self-hosted)."""
    timeout = 86400  # 24 hours for large batch operations
    if QDRANT_URL:
        print(f"[INFO] Connecting to Qdrant cloud at {QDRANT_URL}")
        return QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=timeout
        )
    print(f"[INFO] Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}")
    return QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        timeout=timeout
    )


# Singleton instances - initialized at import time
_embedding_model: Optional[EmbeddingModel] = None
_image_describer: Optional[ImageDescriber] = None
_qdrant_client: Optional[QdrantClient] = None


def get_models() -> Tuple[EmbeddingModel, ImageDescriber, QdrantClient]:
    """
    Get or initialize singleton model instances.
    Models are initialized once at first call (import time).
    """
    global _embedding_model, _image_describer, _qdrant_client
    
    if _embedding_model is None:
        _embedding_model = EmbeddingModel(MODEL_NAME, VECTOR_SIZE)
    
    if _image_describer is None:
        _image_describer = ImageDescriber()
    
    if _qdrant_client is None:
        _qdrant_client = create_qdrant_client()
    
    return _embedding_model, _image_describer, _qdrant_client

