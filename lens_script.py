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

    sys.exit(1)

# Get absolute path to media directory
MEDIA_ROOT = project_root / "media"

if not MEDIA_ROOT.exists():

    sys.exit(1)

# Pattern to match WDG followed by digits and .jpg extension
# This will match: WDG00000001.jpg, WDG123.jpg, etc.
# But will exclude files with _MOCKUP, _JPG, etc. in the name
pattern = re.compile(r"^WDG\d+\.jpg$", re.IGNORECASE)

images_data = []

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

        except Exception as e:

            continue

if len(images_data) == 0:

    sys.exit(1)

try:
    results = train_images(images_data)
except Exception as e:

    import traceback
    traceback.print_exc()
    sys.exit(1)

indexed_count = sum(1 for r in results if r.get('isIndexed', False))
failed_count = len(results) - indexed_count

# Print detailed results (limit to first 20 to avoid spam)

for i, result in enumerate(results[:20]):
    status = "✓" if result.get('isIndexed', False) else "✗"

if len(results) > 20:
