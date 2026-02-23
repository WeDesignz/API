from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.core.files.storage import default_storage
from common.relations import attach_relation
from common.avif_converter import create_avif_from_media_file
import logging
import os
import tempfile

from Catalog.models import Product, Category, Tags, PDFDownload
from MediaFiles.models import Media

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='Catalog.tasks.process_single_design_upload')
def process_single_design_upload(
    self,
    product_id,
    design_files_data,
    tag_ids,
    platform_id
):
    """
    Celery task to process single design upload asynchronously.
    Processes files and attaches them to the product.
    
    Args:
        product_id: ID of the Product that was created
        design_files_data: List of dicts with file info: [{'path': '...', 'name': '...', 'size': ...}, ...]
        tag_ids: List of tag IDs to attach
        platform_id: Platform ID for the product
    """
    try:
        logger.info(f'Starting single design upload task for product {product_id}')
        
        # Get the product
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            logger.error(f'Product {product_id} not found')
            return {'status': 'failed', 'error': 'Product not found'}
        
        # Ensure product_number is available
        if not product.product_number:
            logger.warning(f'Product {product_id} has no product_number, refreshing from DB...')
            product.refresh_from_db()
            if not product.product_number:
                logger.error(f'Product {product_id} still has no product_number after refresh')
                return {'status': 'failed', 'error': 'Product has no product_number'}
        
        product_number = product.product_number
        
        # Process files
        from django.conf import settings
        from django.core.files.storage import default_storage
        from django.core.files import File
        
        processed_files = 0
        for file_data in design_files_data:
            try:
                file_path = file_data['path']
                file_name = file_data['name']
                file_size = file_data.get('size', 0)
                
                # Use default_storage to check if file exists and open it
                # This works with both local and cloud storage backends
                if not default_storage.exists(file_path):
                    logger.warning(f'File not found in storage: {file_path}')
                    continue
                
                # Determine media type
                file_name_lower = file_name.lower()
                if file_name_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.eps', '.cdr', '.ai', '.svg')):
                    media_type = 'image'
                elif file_name_lower.endswith(('.mp4', '.avi', '.mov', '.wmv')):
                    media_type = 'video'
                else:
                    media_type = 'image'
                
                # Detect if this is a mockup file (filename must be exactly "mockup" or contains "mockup")
                base_name = os.path.splitext(os.path.basename(file_name_lower))[0]
                is_mockup = base_name == 'mockup' or 'mockup' in file_name_lower
                
                # Generate new filename using product_number
                file_ext = os.path.splitext(file_name)[1].lower()
                if is_mockup:
                    new_filename = f'{product_number}_MOCKUP{file_ext}'
                else:
                    new_filename = f'{product_number}{file_ext}'
                
                # Set product context for file path generation
                # #region agent log
                import json
                import os
                log_path = os.getenv('DEBUG_LOG_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', 'debug.log'))
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"Catalog/tasks.py:process_single_design_upload","message":"Setting product context before Media.create","data":{"product_id":product.id,"filename":new_filename,"file_name":file_name},"timestamp":int(__import__('time').time()*1000)})+'\n')
                except: pass
                # #endregion
                Media.set_product_context(product.id)
                try:
                    # Open file from storage and create Media object with new filename
                    with default_storage.open(file_path, 'rb') as storage_file:
                        django_file = File(storage_file, name=new_filename)
                        # Create Media instance and set temp product_id as additional fallback
                        media_obj = Media(
                            file=django_file,
                            media_type=media_type,
                            created_by=product.created_by
                        )
                        # Set instance-level product_id as fallback
                        media_obj.set_temp_product_id(product.id)
                        # Save the instance
                        media_obj.save()
                        # #region agent log
                        try:
                            with open(log_path, 'a') as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"Catalog/tasks.py:process_single_design_upload","message":"Media object created","data":{"media_id":media_obj.id,"saved_path":media_obj.file.name,"product_id":product.id},"timestamp":int(__import__('time').time()*1000)})+'\n')
                        except: pass
                        # #endregion
                        
                        # Validate file location - ensure it's in the correct product design folder
                        expected_path_prefix = f'{product.created_by.id}/designs/{product.id}/'
                        if not media_obj.file.name.startswith(expected_path_prefix):
                            error_msg = f'Media file saved to wrong location! Expected: {expected_path_prefix}*, Got: {media_obj.file.name}'
                            logger.error(error_msg)
                            # #region agent log
                            try:
                                with open(log_path, 'a') as f:
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"Catalog/tasks.py:process_single_design_upload","message":"VALIDATION ERROR: File in wrong location","data":{"media_id":media_obj.id,"saved_path":media_obj.file.name,"expected_prefix":expected_path_prefix,"product_id":product.id},"timestamp":int(__import__('time').time()*1000)})+'\n')
                            except: pass
                            # #endregion
                finally:
                    # Clear product context
                    Media.clear_product_context()
                    # #region agent log
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"Catalog/tasks.py:process_single_design_upload","message":"Product context cleared","data":{"product_id":product.id},"timestamp":int(__import__('time').time()*1000)})+'\n')
                    except: pass
                    # #endregion
                
                # Delete temporary file after processing
                try:
                    default_storage.delete(file_path)
                    logger.info(f'Deleted temp file: {file_path}')
                except Exception as e:
                    logger.warning(f'Failed to delete temp file {file_path}: {str(e)}')
                
                # Attach metadata
                upload_metadata = {
                    'timestamp': timezone.now().isoformat(),
                    'platform_id': platform_id,
                    'original_filename': file_name,
                    'file_size': file_size,
                    'file_type': file_name_lower.split('.')[-1] if '.' in file_name_lower else 'unknown',
                    'is_mockup': is_mockup  # Mark mockup files for easy detection
                }
                
                # Also add type field for compatibility
                if is_mockup:
                    upload_metadata['type'] = 'mockup'
                
                # Attach media to product
                product.attach_media(media_obj, meta=upload_metadata, created_by=product.created_by)
                processed_files += 1
                logger.info(f'Processed file {file_name} -> {new_filename} for product {product_id}')
                
                # Create AVIF version for JPG and PNG files
                if file_name_lower.endswith(('.jpg', '.jpeg', '.png')):
                    try:
                        media_file_path = media_obj.file.name
                        avif_path, avif_media_obj = create_avif_from_media_file(
                            media_file_path,
                            product_number,
                            is_mockup=is_mockup,
                            product=product,
                            created_by=product.created_by
                        )
                        if avif_path:
                            logger.info(f'Created AVIF version for {file_name}: {avif_path}')
                            if avif_media_obj:
                                logger.info(f'Linked AVIF Media object {avif_media_obj.id} to product {product_id}')
                    except Exception as avif_error:
                        logger.warning(f'Failed to create AVIF for {file_name}: {avif_error}')
                
            except Exception as e:
                logger.error(f'Failed to process file {file_data.get("name", "unknown")}: {str(e)}', exc_info=True)
        
        logger.info(f'Successfully processed {processed_files} files for product {product_id}')
        return {'status': 'success', 'processed_files': processed_files}
        
    except Exception as e:
        logger.error(f'Failed to process single design upload for product {product_id}: {str(e)}', exc_info=True)
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, name='Catalog.tasks.generate_pdf_task', max_retries=3)
def generate_pdf_task(self, pdf_download_id):
    """
    Generate PDF for a PDF download request.
    """
    try:
        pdf_download = PDFDownload.objects.get(id=pdf_download_id)
        
        # Update status to processing if not already
        if pdf_download.status != 'processing':
            pdf_download.status = 'processing'
            pdf_download.save()
        
        # Get products based on selection type
        products = []
        
        if pdf_download.selection_type == 'specific':
            # Use selected products - preserve order from selected_products list
            selected_ids = pdf_download.selected_products or []
            if not selected_ids:
                raise ValueError('No products selected for PDF generation')
            
            # Log the received order for debugging
            logger.info(f'Received product IDs in order: {selected_ids}')
            
            # Create a dict to preserve order
            products_dict = {p.id: p for p in Product.objects.filter(
                id__in=selected_ids,
                status='active',
                visibility_status='show'
            )}
            
            # Preserve order from selected_products list - this is critical for sequence
            products = [products_dict[pid] for pid in selected_ids if pid in products_dict]
            
            # Log the final order
            product_ids_ordered = [p.id for p in products]
            logger.info(f'Products in final order: {product_ids_ordered}')
            
            if len(products) != len(selected_ids):
                missing_ids = set(selected_ids) - set(product_ids_ordered)
                logger.warning(f'Some products not found or inactive. Expected {len(selected_ids)}, got {len(products)}. Missing: {missing_ids}')
        else:
            # Use search filters to get products
            search_filters = pdf_download.search_filters or {}
            query = search_filters.get('q', '')
            category_id = search_filters.get('category')
            
            products_qs = Product.objects.filter(
                status='active',
                visibility_status='show'
            )
            
            if query:
                from django.db.models import Q
                products_qs = products_qs.filter(
                    Q(title__icontains=query) | Q(description__icontains=query)
                )
            
            if category_id:
                products_qs = products_qs.filter(category_id=category_id)
            
            # When exclude_designs_from_previous_pdfs: exclude designs from user's previous PDFs
            if getattr(pdf_download, 'exclude_designs_from_previous_pdfs', False):
                user = pdf_download.get_user()
                if user:
                    from common.relations import get_related_ids_for_right
                    pdf_ids = list(get_related_ids_for_right(user, 'User:PDFDownload'))
                    if pdf_ids:
                        exclude_ids = set()
                        for row in PDFDownload.objects.filter(id__in=pdf_ids).exclude(id=pdf_download_id).values('selected_products', 'included_products'):
                            for pid in (row.get('selected_products') or []):
                                if isinstance(pid, (int, float)):
                                    exclude_ids.add(int(pid))
                            for item in (row.get('included_products') or []):
                                if isinstance(item, dict) and 'product_id' in item:
                                    exclude_ids.add(int(item['product_id']))
                        if exclude_ids:
                            products_qs = products_qs.exclude(id__in=exclude_ids)
            
            products = list(products_qs[:pdf_download.total_pages])
        
        if not products:
            raise ValueError('No products found for PDF generation')
        
        logger.info(f'Generating PDF for {len(products)} products')
        
        # Get mockup images for each product
        from MediaFiles.models import Relation
        from django.conf import settings
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        from PIL import Image
        
        # Supported image formats for PDF generation
        SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        UNSUPPORTED_EXTENSIONS = {'.cdr', '.eps', '.ai', '.svg', '.pdf'}
        
        # Get user from PDFDownload
        user = pdf_download.get_user()
        if not user:
            logger.warning(f'PDF download {pdf_download_id} has no associated user, using fallback location')
            # Fallback to old location if user not found
            pdf_dir = os.path.join(settings.MEDIA_ROOT, 'pdfs')
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_filename = f'pdf_download_{pdf_download_id}.pdf'
            pdf_file_path = os.path.join(pdf_dir, pdf_filename)
            relative_path = f'pdfs/{pdf_filename}'
        else:
            # Create PDF file path in user-specific folder
            user_id = user.id
            pdf_filename = f'pdf_download_{pdf_download_id}.pdf'
            pdf_dir = os.path.join(settings.MEDIA_ROOT, str(user_id), 'pdfs')
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_file_path = os.path.join(pdf_dir, pdf_filename)
            relative_path = f'{user_id}/pdfs/{pdf_filename}'
        
        # Update PDF download with included products
        # Only include products that have valid mockup images
        # IMPORTANT: Maintain the exact sequence from the original products list
        # Create a mapping of product_id to original index to preserve order
        original_order = {product.id: idx for idx, product in enumerate(products)}
        included_products = []
        mockup_paths = []  # Store paths to mockup images for PDF generation
        skipped_products = []  # Track products without mockups for logging
        
        # Process products in their original order to maintain sequence
        for idx, product in enumerate(products, 1):
            # Get all media for this product
            media_list = product.get_media()
            mockup_media = None
            
            # Find mockup image by checking Relation metadata and filename
            for media in media_list:
                try:
                    # Skip if no file
                    if not hasattr(media, 'file') or not media.file:
                        continue
                    
                    file_name = media.file.name if hasattr(media.file, 'name') else ''
                    if not file_name:
                        continue
                    
                    # Check file extension - skip unsupported formats
                    file_name_lower = file_name.lower()
                    file_ext = os.path.splitext(file_name_lower)[1]
                    
                    if file_ext in UNSUPPORTED_EXTENSIONS:
                        logger.debug(f'Skipping unsupported file type {file_ext} for product {product.id}: {file_name}')
                        continue
                    
                    # Check if filename contains "mockup" (case-insensitive)
                    base_name = os.path.splitext(os.path.basename(file_name_lower))[0]
                    is_mockup_by_name = base_name == 'mockup' or 'mockup' in base_name
                    
                    # Check Relation metadata
                    is_mockup_by_meta = False
                    try:
                        relation = Relation.objects.filter(
                            relation_type='Product:Media',
                            id_1=product.pk,
                            id_2=media.pk
                        ).first()
                        
                        if relation and relation.meta:
                            meta_data = relation.meta
                            if isinstance(meta_data, dict):
                                is_mockup_by_meta = meta_data.get('is_mockup', False) or meta_data.get('type') == 'mockup'
                            elif isinstance(meta_data, str):
                                meta_lower = str(meta_data).lower()
                                is_mockup_by_meta = 'mockup' in meta_lower or '"is_mockup":true' in meta_lower
                    except Exception as e:
                        logger.debug(f'Error checking relation metadata for media {getattr(media, "id", "unknown")}: {e}')
                    
                    # Only use if it's a mockup AND a supported image format
                    if (is_mockup_by_name or is_mockup_by_meta) and file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                        mockup_media = media
                        logger.info(f'Found mockup image for product {product.id}: {file_name}')
                        break
                except Exception as e:
                    logger.warning(f'Error checking media {getattr(media, "id", "unknown")} for product {product.id}: {e}')
                    continue
            
            # If no mockup found, use first available supported image so every design gets a page
            if not mockup_media or not hasattr(mockup_media, 'file') or not mockup_media.file:
                for media in media_list:
                    try:
                        if not hasattr(media, 'file') or not media.file:
                            continue
                        file_name = media.file.name if hasattr(media.file, 'name') else ''
                        if not file_name:
                            continue
                        file_name_lower = file_name.lower()
                        file_ext = os.path.splitext(file_name_lower)[1]
                        if file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                            mockup_media = media
                            logger.info(f'Using first available image for product {product.id} (no mockup): {file_name}')
                            break
                    except Exception:
                        continue
                if not mockup_media or not hasattr(mockup_media, 'file') or not mockup_media.file:
                    logger.warning(f'Skipping product {product.id} ({product.title}) - no image found')
                    skipped_products.append(product.id)
                    continue
            
            # Get image path for the mockup (or fallback image) - use local path or copy from storage to temp file
            image_path = None
            temp_files_to_cleanup = getattr(self, '_pdf_temp_files', None)
            if temp_files_to_cleanup is None:
                self._pdf_temp_files = []
                temp_files_to_cleanup = self._pdf_temp_files
            try:
                # Try absolute path first (local filesystem)
                if hasattr(mockup_media.file, 'path'):
                    image_path = mockup_media.file.path
                else:
                    image_path = os.path.join(settings.MEDIA_ROOT, mockup_media.file.name)
                
                if not os.path.exists(image_path) and mockup_media.file.name:
                    # File may be on remote storage (S3 etc.) - copy to temp file so reportlab can read it
                    try:
                        if default_storage.exists(mockup_media.file.name):
                            with default_storage.open(mockup_media.file.name, 'rb') as src:
                                suffix = os.path.splitext(mockup_media.file.name)[1].lower()
                                if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
                                    suffix = '.jpg'
                                fd, image_path = tempfile.mkstemp(suffix=suffix, prefix='pdf_img_')
                                os.close(fd)
                                with open(image_path, 'wb') as dst:
                                    dst.write(src.read())
                                temp_files_to_cleanup.append(image_path)
                                logger.info(f'Copied media to temp file for product {product.id}: {image_path}')
                        else:
                            image_path = None
                    except Exception as e:
                        logger.warning(f'Could not open storage file for product {product.id}: {e}')
                        image_path = None
                
                if not image_path or not os.path.exists(image_path):
                    logger.warning(f'Image not found for product {product.id} at {getattr(image_path, "path", image_path)}')
                    skipped_products.append(product.id)
                    continue
                file_ext = os.path.splitext(image_path.lower())[1]
                if file_ext not in SUPPORTED_IMAGE_EXTENSIONS:
                    logger.warning(f'Image has unsupported format {file_ext} for product {product.id}')
                    skipped_products.append(product.id)
                    continue
            except Exception as e:
                logger.warning(f'Error getting image path for product {product.id}: {e}')
                skipped_products.append(product.id)
                continue
            
            # Only add products with valid mockup images
            # Maintain original position index for sequence tracking
            original_position = original_order.get(product.id, idx)
            included_products.append({
                'product_id': product.id,
                'page_number': len(included_products) + 1,  # Use actual count for PDF pages
                'original_position': original_position,  # Track original position in sequence
                'title': product.title,
                'product_number': product.product_number or f"WD{product.id}",  # Add product number with fallback
                'image_path': image_path
            })
            mockup_paths.append(image_path)
        
        # Log skipped products
        if skipped_products:
            logger.warning(f'Skipped {len(skipped_products)} products without images: {skipped_products}')
        
        if not included_products:
            raise ValueError(
                f'No products with usable images for PDF. All {len(products)} product(s) were skipped. '
                'Ensure each design has at least one image (JPG, PNG, etc.).'
            )
        
        pdf_download.included_products = included_products
        pdf_download.products_count = len(included_products)  # Use actual count of included products
        
        # Generate PDF with reportlab - one page per design
        try:
            logger.info(f'Creating PDF file at: {pdf_file_path}')
            
            # Create PDF canvas
            c = canvas.Canvas(pdf_file_path, pagesize=letter)
            page_width, page_height = letter
            margin = 50  # Define margin outside the loop
            
            # Only generate PDF pages for products with valid mockup images
            # included_products already contains only products with valid mockups
            # Get customer information from PDF download - refresh from DB to ensure we have latest values
            pdf_download.refresh_from_db()
            customer_name = pdf_download.customer_name or ''
            customer_mobile = pdf_download.customer_mobile or ''
            
            # Resolve logo path: customer logo or default WeDesignz logo (no boxes around any text)
            logo_path = None
            if pdf_download.customer_logo and hasattr(pdf_download.customer_logo, 'path') and pdf_download.customer_logo.path:
                if os.path.exists(pdf_download.customer_logo.path):
                    logo_path = pdf_download.customer_logo.path
            if not logo_path:
                # Default WeDesignz logo: set PDF_DEFAULT_LOGO_PATH in settings, or place wedesignz_logo.png in media/defaults/
                default_logo = getattr(settings, 'PDF_DEFAULT_LOGO_PATH', None)
                if default_logo and os.path.exists(default_logo):
                    logo_path = default_logo
                else:
                    alt_default = os.path.join(settings.MEDIA_ROOT, 'defaults', 'wedesignz_logo.png')
                    if os.path.exists(alt_default):
                        logo_path = alt_default
            
            logger.info(f'PDF generation for download {pdf_download_id}: customer_name="{customer_name}", customer_mobile="{customer_mobile}", logo={bool(logo_path)}')
            
            for idx, product_info in enumerate(included_products, 1):
                if idx > 1:
                    c.showPage()
                
                product_id = product_info['product_id']
                product_title = product_info['title']
                product_number = product_info.get('product_number', f"WD{product_id}")
                image_path = product_info['image_path']
                
                # --- Layout: top-left logo, top-center name+number (no boxes), center design, bottom design number ---
                page_w, page_h = page_width, page_height
                m = margin
                
                # 1) Top-left: logo (optional; no box)
                logo_size = 56
                if logo_path and os.path.exists(logo_path):
                    try:
                        c.drawImage(logo_path, m, page_h - m - logo_size, width=logo_size, height=logo_size, preserveAspectRatio=True)
                    except Exception as e:
                        logger.warning(f'Could not draw logo for page {idx}: {e}')
                
                # 2) Top-center: name, then number below (plain text, no boxes)
                name_text = customer_name or ''
                number_text = customer_mobile or ''
                c.setFillColorRGB(0.2, 0.2, 0.25)
                c.setFont("Helvetica-Bold", 14)
                name_width = c.stringWidth(name_text or ' ', "Helvetica-Bold", 14)
                center_x = page_w / 2
                c.drawString(center_x - name_width / 2, page_h - m - 28, name_text[:60] or ' ')
                c.setFont("Helvetica", 12)
                num_width = c.stringWidth(number_text or ' ', "Helvetica", 12)
                c.drawString(center_x - num_width / 2, page_h - m - 46, number_text[:20] or ' ')
                
                # 3) Bottom: design number (plain text, no box)
                c.setFont("Helvetica", 11)
                c.setFillColorRGB(0.35, 0.35, 0.4)
                c.drawString(m, m + 8, f"Design: {product_number}")
                
                # 4) Center: design image (with margins for header and footer)
                header_used = 70
                footer_used = 36
                available_width = page_w - (2 * m)
                available_height = page_h - (2 * m) - header_used - footer_used
                
                if image_path and os.path.exists(image_path):
                    try:
                        img = Image.open(image_path)
                        iw, ih = img.size
                        scale_x = available_width / iw
                        scale_y = available_height / ih
                        scale = min(scale_x, scale_y)
                        sw = iw * scale
                        sh = ih * scale
                        img_x = (page_w - sw) / 2
                        img_y = m + footer_used + (available_height - sh) / 2
                        c.drawImage(image_path, img_x, img_y, width=sw, height=sh, preserveAspectRatio=True)
                        logger.info(f'Added image for product {product_id} on page {idx}')
                    except Exception as e:
                        logger.error(f'Error adding image for product {product_id}: {e}', exc_info=True)
                        c.setFont("Helvetica", 12)
                        c.setFillColorRGB(0.5, 0.5, 0.55)
                        c.drawString(center_x - 60, page_h / 2 - 20, "Image not available")
                else:
                    c.setFont("Helvetica", 12)
                    c.setFillColorRGB(0.5, 0.5, 0.55)
                    c.drawString(center_x - 60, page_h / 2 - 20, "Image not available")
            
            # Save PDF (we already validated included_products is non-empty before this try block)
            c.save()
            
            # Clean up any temp files we created for remote storage images
            temp_files_to_cleanup = getattr(self, '_pdf_temp_files', [])
            for tmp in temp_files_to_cleanup:
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception as e:
                    logger.warning(f'Could not remove temp file {tmp}: {e}')
            if hasattr(self, '_pdf_temp_files'):
                self._pdf_temp_files = []
            
            logger.info(f'PDF file created successfully at {pdf_file_path}')
            
            # Verify file was created
            if not os.path.exists(pdf_file_path):
                raise Exception(f'PDF file was not created at {pdf_file_path}')
            
            # Get file size
            file_size = os.path.getsize(pdf_file_path)
            if file_size == 0:
                raise Exception(f'PDF file was created but is empty (0 bytes) at {pdf_file_path}')
            
            logger.info(f'PDF file size: {file_size} bytes')
            
            # Store relative path (without MEDIA_ROOT)
            pdf_download.pdf_file_path = relative_path
            pdf_download.file_size = file_size
            
            # Update status to completed
            pdf_download.status = 'completed'
            pdf_download.completed_at = timezone.now()
            pdf_download.save()
            
            # Check if this was a subscription mock PDF download
            # We can check by looking at the order linked to this PDF download
            from Orders.models import Order
            try:
                order = Order.objects.filter(
                    pdf_download=pdf_download,
                    order_type='mock_pdf',
                    subscription__isnull=False
                ).select_related('subscription').first()
                
                if order and order.subscription:
                    # This was a subscription mock PDF download
                    # Counter was already incremented when order was created,
                    # but we can verify it here as a safety measure
                    logger.info(
                        f"Subscription mock PDF download completed. "
                        f"Subscription: {order.subscription.id}, "
                        f"Remaining: {order.subscription.get_remaining_mock_pdf_downloads()}"
                    )
            except Exception as e:
                logger.warning(f"Could not verify subscription mock PDF usage: {str(e)}")
            
            logger.info(f'PDF generation completed for download {pdf_download_id}')
        except Exception as e:
            logger.error(f'Error creating PDF file for download {pdf_download_id}: {str(e)}', exc_info=True)
            # Clean up temp files on failure
            temp_files_to_cleanup = getattr(self, '_pdf_temp_files', [])
            for tmp in temp_files_to_cleanup:
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass
            if hasattr(self, '_pdf_temp_files'):
                self._pdf_temp_files = []
            # Don't mark as completed if file creation failed
            pdf_download.status = 'failed'
            pdf_download.save()
            raise
        return {'status': 'completed', 'download_id': pdf_download_id}
        
    except PDFDownload.DoesNotExist:
        logger.error(f'PDF download {pdf_download_id} not found')
        raise
    except Exception as e:
        logger.error(f'Error generating PDF for download {pdf_download_id}: {str(e)}', exc_info=True)
        # Update status to failed
        try:
            pdf_download = PDFDownload.objects.get(id=pdf_download_id)
            pdf_download.status = 'failed'
            pdf_download.save()
        except:
            pass
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(name='Catalog.tasks.cleanup_design_pdf_files')
def cleanup_design_pdf_files():
    """
    Delete design PDF files from disk (PDFDownload only).
    PDFs are generated on-demand when user clicks download; this task runs every 4 hours
    to remove old files and free disk space. If user downloads again, PDF is regenerated.
    Only deletes files under pdfs/ or {user_id}/pdfs/ - never touches invoices or other PDFs.
    """
    from django.conf import settings
    deleted_count = 0
    error_count = 0
    media_root = getattr(settings, 'MEDIA_ROOT', None)
    if not media_root or not os.path.isdir(media_root):
        logger.warning('[cleanup_design_pdf_files] MEDIA_ROOT not set or not a directory')
        return {'deleted': 0, 'errors': 0}
    qs = PDFDownload.objects.filter(pdf_file_path__isnull=False).exclude(pdf_file_path='')
    for pdf_download in qs:
        rel_path = pdf_download.pdf_file_path
        if not rel_path or not rel_path.strip():
            continue
        full_path = os.path.join(media_root, rel_path)
        if not os.path.isabs(rel_path):
            full_path = os.path.normpath(os.path.join(media_root, rel_path))
        if not full_path.startswith(os.path.normpath(media_root)):
            logger.warning(f'[cleanup_design_pdf_files] Skipping path outside MEDIA_ROOT: {rel_path}')
            continue
        if not os.path.isfile(full_path):
            continue
        try:
            os.unlink(full_path)
            deleted_count += 1
            logger.info(f'[cleanup_design_pdf_files] Deleted {rel_path}')
        except Exception as e:
            error_count += 1
            logger.warning(f'[cleanup_design_pdf_files] Failed to delete {rel_path}: {e}')
    logger.info(f'[cleanup_design_pdf_files] Deleted {deleted_count} files, {error_count} errors')
    return {'deleted': deleted_count, 'errors': error_count}


# Only index PNG for visual search (per design media storage)
VISUAL_SEARCH_IMAGE_EXTENSIONS = ('.png',)


def _set_huggingface_timeout_for_visual_search(timeout_seconds=300):
    """Set longer HTTP timeout for Hugging Face Hub when loading visual_search models."""
    try:
        from huggingface_hub import set_client_factory
        import httpx
        set_client_factory(lambda: httpx.Client(timeout=httpx.Timeout(float(timeout_seconds))))
    except Exception as e:
        logger.warning("Could not set Hugging Face client timeout for visual search: %s", e)


@shared_task(bind=True, name='Catalog.tasks.index_product_visual_search')
def index_product_visual_search(self, product_id):
    """
    Index a single product's PNG images into Qdrant for visual search (async).
    Called when a design is approved so new designs are searchable without blocking admin.
    Only PNG images are indexed.
    """
    import sys
    from django.conf import settings
    from PIL import Image
    from common.relations import get_related
    from MediaFiles.models import Media

    try:
        product = Product.objects.filter(pk=product_id).first()
        if not product or not product.product_number:
            logger.warning(f'[index_product_visual_search] Product {product_id} not found or has no product_number')
            return {'status': 'skipped', 'reason': 'product_not_found'}

        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if not media_root or not os.path.isdir(media_root):
            logger.warning(f'[index_product_visual_search] MEDIA_ROOT not set or not a directory')
            return {'status': 'skipped', 'reason': 'no_media_root'}

        media_list = get_related(product, 'Product:Media', Media).filter(media_type='image')
        images_data = []
        for media in media_list:
            if not media.file:
                continue
            ext = os.path.splitext(media.file.name)[1].lower()
            if ext not in VISUAL_SEARCH_IMAGE_EXTENSIONS:
                continue
            path = getattr(media.file, 'path', None) or os.path.join(media_root, media.file.name)
            if not os.path.isfile(path):
                continue
            try:
                img = Image.open(path)
                img.load()
            except Exception as e:
                logger.warning(f'[index_product_visual_search] Skip open failed product {product_id} {path}: {e}')
                continue
            images_data.append({
                'ProductId': str(product.product_number),
                'MediaFileId': str(media.id),
                'image': img,
            })

        if not images_data:
            logger.debug(f'[index_product_visual_search] No PNG images for product {product_id}')
            return {'status': 'skipped', 'reason': 'no_png_images'}

        _set_huggingface_timeout_for_visual_search(300)
        api_root = str(settings.BASE_DIR)
        if api_root not in sys.path:
            sys.path.insert(0, api_root)
        from visual_search import train_images

        results = train_images(images_data)
        success_count = sum(1 for r in results if r.get('isIndexed'))
        if success_count and hasattr(Product, 'is_indexed'):
            Product.objects.filter(product_number=product.product_number).update(is_indexed=True)
        logger.info(f'[index_product_visual_search] Product {product_id} ({product.product_number}): indexed {success_count}/{len(images_data)} PNG images')
        return {'status': 'ok', 'indexed': success_count, 'total': len(images_data)}
    except Exception as e:
        logger.exception(f'[index_product_visual_search] Failed for product {product_id}: {e}')
        return {'status': 'failed', 'error': str(e)}

