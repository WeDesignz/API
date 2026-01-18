"""
Configuration settings for Visual Search package.
Can be overridden via environment variables.
"""
import os


# Fashion CLIP model - better for fashion/garment pattern matching
MODEL_NAME = os.environ.get("VISUAL_SEARCH_MODEL_NAME", "patrickjohncyh/fashion-clip")
VECTOR_SIZE = 512  # Fashion CLIP uses same vector size as standard CLIP
DESCRIPTION_MODEL = os.environ.get(
    "VISUAL_SEARCH_DESCRIPTION_MODEL", "Salesforce/blip-image-captioning-base"
)
BATCH_SIZE = int(os.environ.get("VISUAL_SEARCH_BATCH_SIZE", "200"))

# Qdrant Configuration
QDRANT_URL = os.environ.get("VISUAL_SEARCH_QDRANT_URL", None)
QDRANT_API_KEY = os.environ.get("VISUAL_SEARCH_QDRANT_API_KEY", None)
QDRANT_HOST = os.environ.get("VISUAL_SEARCH_QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("VISUAL_SEARCH_QDRANT_PORT", "6333"))
COLLECTION_NAME = os.environ.get("VISUAL_SEARCH_COLLECTION_NAME", "patterns")
DISTANCE_FUNCTION = "Cosine"

# Search Configuration
NUM_RESULTS = int(os.environ.get("VISUAL_SEARCH_NUM_RESULTS", "20"))
HNSW_EF = int(os.environ.get("VISUAL_SEARCH_HNSW_EF", "128"))  # Higher = more accurate, slower

