"""Collection utility functions for Qdrant."""
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, HnswConfigDiff

from visual_search.config import (
    COLLECTION_NAME, VECTOR_SIZE, DISTANCE_FUNCTION
)


def ensure_collection_exists(client: QdrantClient):
    """
    Ensure the collection exists with optimized HNSW configuration.
    Creates it if it doesn't exist.
    
    Args:
        client: QdrantClient instance
    """
    try:
        collections = client.get_collections()
        collection_names = [col.name for col in collections.collections]
        
        if COLLECTION_NAME in collection_names:
            print(f"[INFO] Collection '{COLLECTION_NAME}' already exists")
            return
    except Exception as e:
        print(f"[INFO] Could not verify collection existence ({e}), will attempt to create")
    
    # Create collection with optimized HNSW configuration (also if get_collections failed, e.g. 404)
    distance = Distance.COSINE if DISTANCE_FUNCTION.lower() == "cosine" else Distance.EUCLID
    
    hnsw_config = HnswConfigDiff(
        m=16,  # Good balance: 16 connections per node
        ef_construct=200,  # Higher quality index (default is 100)
        full_scan_threshold=10000,  # Use full scan for collections < 10k points
    )
    
    print("[INFO] Creating collection with optimized HNSW configuration...")
    print(f"[INFO] HNSW Config: m=16, ef_construct=200, full_scan_threshold=10000")
    
    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=distance,
                hnsw_config=hnsw_config,
            ),
        )
        print("[INFO] Collection created successfully with optimized HNSW configuration.")
    except Exception as e:
        error_str = str(e).lower()
        if (
            "already exists" in error_str
            or "409" in error_str
            or "conflict" in error_str
        ):
            print(f"[INFO] Collection '{COLLECTION_NAME}' already exists (possibly created concurrently)")
            return
        print(f"[ERROR] Failed to create collection: {e}")
        raise

