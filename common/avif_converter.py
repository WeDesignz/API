from PIL import Image
import os
from pathlib import Path
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)

def convert_to_avif(input_path, output_dir, base_name, is_mockup=False):
    """
    Convert image to AVIF format with aggressive compression for web display.
    
    Args:
        input_path: Path to the input image file
        output_dir: Directory where AVIF file should be saved
        base_name: Base name for the output file (without extension)
        is_mockup: Whether this is a MOCKUP file (uses more aggressive compression)
    
    Returns:
        Path to the created AVIF file, or None if conversion failed
    """
    try:
        # Open and convert to RGB
        img = Image.open(input_path).convert("RGB")
        
        # Resize for web display - max dimension 1200px for better compression
        # For MOCKUP files, use smaller size (800px) to ensure KBs
        max_dimension = 800 if is_mockup else 1200
        
        # Calculate new dimensions maintaining aspect ratio
        width, height = img.size
        if width > max_dimension or height > max_dimension:
            if width > height:
                new_width = max_dimension
                new_height = int(height * (max_dimension / width))
            else:
                new_height = max_dimension
                new_width = int(width * (max_dimension / height))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Determine AVIF filename
        # For MOCKUP files: WDG00000001_MOCKUP.avif
        # For JPG files: WDG00000001_JPG.avif
        # For PNG files: WDG00000001_PNG.avif
        if is_mockup:
            avif_filename = f"{base_name}_MOCKUP.avif"
        else:
            # Determine original format from input_path
            input_lower = input_path.lower()
            if '.jpg' in input_lower or '.jpeg' in input_lower:
                avif_filename = f"{base_name}_JPG.avif"
            elif '.png' in input_lower:
                avif_filename = f"{base_name}_PNG.avif"
            else:
                avif_filename = f"{base_name}.avif"
        
        avif_path = os.path.join(output_dir, avif_filename)

        # AVIF - very aggressive compression for web
        # Lower quality for MOCKUP files to ensure KBs
        avif_quality = 25 if is_mockup else 35
        
        # Save AVIF to a temporary location first
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.avif', delete=False) as temp_file:
            temp_avif_path = temp_file.name
            img.save(
                temp_avif_path,
                format="AVIF",
                quality=avif_quality,
                speed=4  # Faster encoding, slightly larger file but still small
            )
            
            # Read the AVIF file and save to storage
            with open(temp_avif_path, 'rb') as avif_file:
                avif_content = avif_file.read()
                avif_file_obj = ContentFile(avif_content, name=avif_filename)
                
                # Save to storage using default_storage
                saved_path = default_storage.save(avif_path, avif_file_obj)
                
                # Clean up temp file
                os.unlink(temp_avif_path)
                
                # Check file size and report
                avif_size = len(avif_content) / 1024  # Size in KB
                
                if is_mockup:
                    logger.info(f"  MOCKUP: AVIF={avif_size:.1f}KB saved to {saved_path}")
                else:
                    logger.info(f"  AVIF conversion: {avif_size:.1f}KB saved to {saved_path}")

                return saved_path
                
    except Exception as e:
        logger.error(f"Error converting {input_path} to AVIF: {e}", exc_info=True)
        return None


def create_avif_from_media_file(media_file_path, product_number, is_mockup=False):
    """
    Create AVIF version of a media file.
    
    Args:
        media_file_path: Path to the media file in storage
        product_number: Product number for naming (e.g., WDG00000001)
        is_mockup: Whether this is a MOCKUP file
    
    Returns:
        Path to the created AVIF file in storage, or None if conversion failed
    """
    try:
        # Get the directory where the original file is located
        file_dir = os.path.dirname(media_file_path)
        
        # Get base name without extension
        base_name = product_number
        
        # Open file from storage
        if not default_storage.exists(media_file_path):
            logger.warning(f"Media file not found for AVIF conversion: {media_file_path}")
            return None
        
        # Read file to temporary location for PIL processing
        import tempfile
        with default_storage.open(media_file_path, 'rb') as storage_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(media_file_path)[1]) as temp_file:
                temp_file.write(storage_file.read())
                temp_input_path = temp_file.name
        
        try:
            # Convert to AVIF
            avif_path = convert_to_avif(temp_input_path, file_dir, base_name, is_mockup=is_mockup)
            return avif_path
        finally:
            # Clean up temp file
            if os.path.exists(temp_input_path):
                os.unlink(temp_input_path)
                
    except Exception as e:
        logger.error(f"Error creating AVIF from media file {media_file_path}: {e}", exc_info=True)
        return None

