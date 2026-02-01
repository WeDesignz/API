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

# Qdrant Configuration - default to local Qdrant on same machine as API (e.g. VPS)
# - API on VPS (gunicorn on host): use localhost; ensure Qdrant Docker publishes -p 6333:6333.
# - API in Docker on same VPS: set VISUAL_SEARCH_QDRANT_HOST to reach Qdrant:
#   - Same docker-compose: use service name, e.g. VISUAL_SEARCH_QDRANT_HOST=qdrant
#   - Separate containers: use host.docker.internal (Linux: add extra_hosts) or host IP, port 6333.
# Do not set VISUAL_SEARCH_QDRANT_URL unless using Qdrant Cloud.
QDRANT_URL = os.environ.get("VISUAL_SEARCH_QDRANT_URL", "").strip() or None
QDRANT_API_KEY = os.environ.get("VISUAL_SEARCH_QDRANT_API_KEY", "")
QDRANT_HOST = os.environ.get("VISUAL_SEARCH_QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("VISUAL_SEARCH_QDRANT_PORT", "6333"))
COLLECTION_NAME = os.environ.get("VISUAL_SEARCH_COLLECTION_NAME", "patterns")
DISTANCE_FUNCTION = "Cosine"

# Search Configuration
NUM_RESULTS = int(os.environ.get("VISUAL_SEARCH_NUM_RESULTS", "20"))
HNSW_EF = int(os.environ.get("VISUAL_SEARCH_HNSW_EF", "128"))  # Higher = more accurate, slower

