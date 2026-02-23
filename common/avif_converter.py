from PIL import Image
import os
from pathlib import Path
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import logging

# Try to import pillow-avif-plugin to register AVIF support
try:
    import pillow_avif
    # Register AVIF plugin
    pillow_avif.register_avif_opener()
except ImportError:
    pass  # Plugin not installed or not available
except Exception as e:
    # Plugin might be installed but not working
    pass

logger = logging.getLogger(__name__)

# Check if AVIF support is available
def check_avif_support():
    """Check if Pillow has AVIF support"""
    try:
        # First, try to import and register the plugin
        try:
            import pillow_avif
            pillow_avif.register_avif_opener()
        except ImportError:
            # Plugin not installed

        except Exception as e:

        # Try to save a test image to see if AVIF works
        # This is the most reliable way to check
        test_img = Image.new('RGB', (1, 1), color='red')
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.avif', delete=True) as tmp:
            test_img.save(tmp.name, format='AVIF')
            return True
    except (KeyError, ValueError, OSError) as e:
        # AVIF format is not supported

        return False
    except Exception as e:
        # Other error - likely missing system libraries

        return False

# Cache the AVIF support check
_avif_supported = None

def is_avif_supported():
    """Check if AVIF is supported, with caching"""
    global _avif_supported
    if _avif_supported is None:
        _avif_supported = check_avif_support()
        if not _avif_supported:

    return _avif_supported

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
    # Check if AVIF is supported
    if not is_avif_supported():

        return None
    
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

                else:

                return saved_path
                
    except Exception as e:

        return None

def convert_avif_to_jpeg(avif_file_path, quality=85):
    """
    Convert AVIF image to JPEG format for platforms that don't support AVIF (e.g., Pinterest).
    
    Args:
        avif_file_path: Path to the AVIF file in storage
        quality: JPEG quality (1-100, default: 85)
    
    Returns:
        Tuple of (jpeg_file_path_in_storage, jpeg_url), or (None, None) if conversion failed
    """
    try:
        # Check if AVIF support is available
        if not is_avif_supported():

            return None, None
        
        # Check if file exists
        if not default_storage.exists(avif_file_path):

            return None, None
        
        # Read AVIF file from storage to temporary location
        import tempfile
        temp_avif_path = None
        temp_jpeg_path = None
        
        with default_storage.open(avif_file_path, 'rb') as storage_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.avif') as temp_avif:
                temp_avif.write(storage_file.read())
                temp_avif_path = temp_avif.name
        
        try:
            # Open and convert AVIF to RGB
            img = Image.open(temp_avif_path).convert("RGB")
            
            # Save as JPEG to temporary location
            base_name = os.path.splitext(os.path.basename(avif_file_path))[0]
            # Convert AVIF filename to JPEG: WDG00000001_MOCKUP.avif -> WDG00000001_MOCKUP.jpg
            # Keep the base name but change extension to .jpg
            jpeg_filename = base_name + '.jpg'
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_jpeg:
                temp_jpeg_path = temp_jpeg.name
                img.save(temp_jpeg_path, format='JPEG', quality=quality, optimize=True)
            
            # Read JPEG content
            with open(temp_jpeg_path, 'rb') as jpeg_file:
                jpeg_content = jpeg_file.read()
            
            # Determine where to save JPEG (same directory as AVIF)
            jpeg_dir = os.path.dirname(avif_file_path)
            jpeg_storage_path = os.path.join(jpeg_dir, jpeg_filename).replace('\\', '/')
            
            # Save JPEG to storage
            jpeg_file_obj = ContentFile(jpeg_content, name=jpeg_filename)
            saved_jpeg_path = default_storage.save(jpeg_storage_path, jpeg_file_obj)
            
            # Get the URL for the JPEG file
            from django.conf import settings
            media_domain = getattr(settings, 'MEDIA_DOMAIN', 'devapi.wedesignz.com')
            if not media_domain.startswith('http'):
                media_domain = f"https://{media_domain}"
            media_url = getattr(settings, 'MEDIA_URL', '/media/')
            if not media_url.endswith('/'):
                media_url += '/'
            
            jpeg_url = f"{media_domain}{media_url}{saved_jpeg_path}"

            return saved_jpeg_path, jpeg_url
            
        finally:
            # Clean up temporary files
            for temp_path in [temp_avif_path, temp_jpeg_path]:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                        
    except Exception as e:

        return None, None

def create_avif_from_media_file(media_file_path, product_number, is_mockup=False, product=None, created_by=None):
    """
    Create AVIF version of a media file and optionally link it to the product.
    
    Args:
        media_file_path: Path to the media file in storage
        product_number: Product number for naming (e.g., WDG00000001)
        is_mockup: Whether this is a MOCKUP file
        product: Product instance to link the AVIF file to (optional)
        created_by: User who created the AVIF file (optional)
    
    Returns:
        Tuple of (path to the created AVIF file in storage, Media object), or (None, None) if conversion failed
        If product is not provided, returns (avif_path, None) for backward compatibility
    """
    try:
        # Determine the correct directory for AVIF file
        # If product is provided, ALWAYS use the product's design folder, not the original file's directory
        # This ensures AVIF files are always in the correct location even if original file is in wrong location
        if product and hasattr(product, 'created_by') and product.created_by:
            file_dir = f"{product.created_by.id}/designs/{product.id}"
        else:
            # Fallback: use the directory where the original file is located
            file_dir = os.path.dirname(media_file_path)
        
        # #region agent log
        import json
        import os
        log_path = os.getenv('DEBUG_LOG_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', 'debug.log'))
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"common/avif_converter.py:create_avif_from_media_file","message":"AVIF conversion starting","data":{"media_file_path":media_file_path,"file_dir":file_dir,"product_id":product.id if product else None,"product_number":product_number,"using_product_dir":product is not None},"timestamp":int(__import__('time').time()*1000)})+'\n')
        except: pass
        # #endregion
        
        # Get base name without extension
        base_name = product_number
        
        # Open file from storage
        if not default_storage.exists(media_file_path):

            return None, None
        
        # Read file to temporary location for PIL processing
        import tempfile
        with default_storage.open(media_file_path, 'rb') as storage_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(media_file_path)[1]) as temp_file:
                temp_file.write(storage_file.read())
                temp_input_path = temp_file.name
        
        try:
            # Convert to AVIF
            avif_path = convert_to_avif(temp_input_path, file_dir, base_name, is_mockup=is_mockup)
            
            # #region agent log
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"common/avif_converter.py:create_avif_from_media_file","message":"AVIF file created","data":{"avif_path":avif_path,"file_dir":file_dir,"expected_dir":f"{product.created_by.id}/designs/{product.id}/" if product else None},"timestamp":int(__import__('time').time()*1000)})+'\n')
            except: pass
            # #endregion
            
            if not avif_path:
                return None, None
            
            # Create Media object and link to product if provided
            media_obj = None
            if product and default_storage.exists(avif_path):
                try:
                    from MediaFiles.models import Media
                    from django.core.files import File
                    
                    # Get created_by from product if not provided
                    creator = created_by or (product.created_by if hasattr(product, 'created_by') else None)
                    
                    if not creator:

                    else:
                        # The AVIF file is already saved at avif_path (in the product's design folder: {user_id}/designs/{product_id}/)
                        # We need to create a Media object that references this existing file without Django trying to save it again
                        # Set product context so if Django processes the file, it uses the correct path
                        Media.set_product_context(product.id)
                        try:
                            # Get the filename from the avif_path
                            avif_filename = os.path.basename(avif_path)
                            
                            # Create Media object with a temporary dummy file to satisfy the required field
                            # We'll update the file path directly in the database to point to the existing AVIF file
                            from django.core.files.base import ContentFile
                            from io import BytesIO
                            import uuid
                            
                            # Create a minimal dummy file with a unique temporary name
                            # This ensures it won't overwrite the AVIF file we already saved
                            temp_filename = f'.temp_avif_{uuid.uuid4().hex[:8]}.tmp'
                            dummy_content = BytesIO(b'')
                            dummy_file = ContentFile(dummy_content.read(), name=temp_filename)
                            
                            # Create Media instance and set temp product_id as additional fallback
                            # Django will save the dummy file using upload_to
                            # It will be saved to {user_id}/designs/{product_id}/.temp_avif_xxxxx.tmp
                            media_obj = Media(
                                file=dummy_file,
                                media_type='image',
                                created_by=creator
                            )
                            # Set instance-level product_id as fallback
                            media_obj.set_temp_product_id(product.id)
                            # Save the instance
                            media_obj.save()
                            
                            # Store the dummy file path to delete it later
                            dummy_file_path = media_obj.file.name
                            
                            # Now update the file field to point to the already-saved AVIF file
                            # Use update() to directly update the database without triggering file save
                            Media.objects.filter(pk=media_obj.pk).update(file=avif_path)
                            # Refresh from database
                            media_obj.refresh_from_db()
                            
                            # Delete the dummy file if it was created
                            if dummy_file_path and default_storage.exists(dummy_file_path):
                                try:
                                    default_storage.delete(dummy_file_path)

                                except Exception as e:

                            # Verify the AVIF file exists at the correct location
                            if not default_storage.exists(avif_path):

                            else:

                            # Validate AVIF file location - ensure it's in the correct product design folder
                            expected_path_prefix = f'{creator.id}/designs/{product.id}/'
                            if not avif_path.startswith(expected_path_prefix):
                                error_msg = f'AVIF file saved to wrong location! Expected: {expected_path_prefix}*, Got: {avif_path}'

                                # #region agent log
                                try:
                                    with open(log_path, 'a') as f:
                                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"common/avif_converter.py:create_avif_from_media_file","message":"VALIDATION ERROR: AVIF file in wrong location","data":{"avif_path":avif_path,"expected_prefix":expected_path_prefix,"product_id":product.id},"timestamp":int(__import__('time').time()*1000)})+'\n')
                                except: pass
                                # #endregion
                            
                            # Link AVIF file to product
                            avif_metadata = {
                                'is_avif': True,
                                'is_mockup': is_mockup,
                                'original_media_path': media_file_path,
                                'source': 'avif_conversion'
                            }
                            product.attach_media(media_obj, meta=avif_metadata, created_by=creator)

                        finally:
                            Media.clear_product_context()
                except Exception as e:

                    # Don't fail the whole operation if linking fails
            
            return avif_path, media_obj
        finally:
            # Clean up temp file
            if os.path.exists(temp_input_path):
                os.unlink(temp_input_path)
                
    except Exception as e:

        return None, None

