#!/usr/bin/env python3
"""
Script to train/index images from the media directory.

Usage:
    python train_media_images.py

Make sure to run this from the project root directory.
"""
import os
import sys
import re
from pathlib import Path
from PIL import Image

# Add project root to path if needed
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from visual_search import train_images
except ImportError as e:
    print(f"[ERROR] Failed to import visual_search: {e}")
    print("[ERROR] Make sure you're running from the project root directory")
    print("[ERROR] And that visual_search package is properly installed")
    sys.exit(1)

# Get absolute path to media directory
MEDIA_ROOT = project_root / "media"


if not MEDIA_ROOT.exists():
    print(f"[ERROR] Media directory not found: {MEDIA_ROOT}")
    print("[ERROR] Make sure the path is correct")
    sys.exit(1)

# Pattern to match WDG followed by digits and .jpg extension
# This will match: WDG00000001.jpg, WDG123.jpg, etc.
# But will exclude files with _MOCKUP, _JPG, etc. in the name
pattern = re.compile(r"^WDG\d+\.jpg$", re.IGNORECASE)

images_data = []

print(f"[INFO] Scanning media directory: {MEDIA_ROOT}")
print(f"[INFO] Looking for files matching pattern: WDG<digits>.jpg (excluding mockups)")

file_count = 0
for root, _, files in os.walk(str(MEDIA_ROOT)):
    for fname in files:
        file_count += 1
        # Skip files that don't match the pattern
        if not pattern.match(fname):
            continue
        
        # Skip mockups (though pattern should already exclude them)
        if "_mockup" in fname.lower():
            continue
        
        path = os.path.join(root, fname)
        
        try:
            img = Image.open(path)
            product_id = os.path.splitext(fname)[0]  # WDG00000001
            
            images_data.append({
                "ProductId": product_id,
                "MediaFileId": fname,
                "image": img
            })
            print(f"[INFO] Added: {fname} (ProductId: {product_id})")
        except Exception as e:
            print(f"[WARN] Failed to load {path}: {e}")
            continue

print(f"\n[INFO] Scanned {file_count} total files")
print(f"[INFO] Collected {len(images_data)} images matching criteria")

if len(images_data) == 0:
    print("\n[ERROR] No images found matching the pattern!")
    print("[ERROR] Possible issues:")
    print("  1. The MEDIA_ROOT path is incorrect")
    print("  2. Files don't match the pattern: WDG<digits>.jpg")
    print("  3. All matching files are mockups")
    print("\n[INFO] Example of files that would match: WDG00000001.jpg, WDG123.jpg")
    print("[INFO] Example of files that would NOT match: WDG00000001_MOCKUP.jpg, WDG00000001_JPG.jpg")
    sys.exit(1)

print(f"\n[INFO] Starting training/indexing of {len(images_data)} images...")
try:
    results = train_images(images_data)
except Exception as e:
    print(f"[ERROR] Training failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\n[INFO] Training completed!")
print(f"[INFO] Results:")
indexed_count = sum(1 for r in results if r.get('isIndexed', False))
failed_count = len(results) - indexed_count

print(f"  Total: {len(results)}")
print(f"  Successfully indexed: {indexed_count}")
print(f"  Failed: {failed_count}")

# Print detailed results (limit to first 20 to avoid spam)
print(f"\n[INFO] Detailed results (showing first 20):")
for i, result in enumerate(results[:20]):
    status = "✓" if result.get('isIndexed', False) else "✗"
    print(f"  {status} {result.get('ProductId', 'unknown')}")

if len(results) > 20:
    print(f"  ... and {len(results) - 20} more")