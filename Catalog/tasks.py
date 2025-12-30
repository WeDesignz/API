from celery import shared_task
from django.db import transaction
from django.utils import timezone
from common.relations import attach_relation
import logging
import os

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
                Media.set_product_context(product.id)
                try:
                    # Open file from storage and create Media object with new filename
                    with default_storage.open(file_path, 'rb') as storage_file:
                        django_file = File(storage_file, name=new_filename)
                        media_obj = Media.objects.create(
                            file=django_file,
                            media_type=media_type,
                            created_by=product.created_by
                        )
                finally:
                    # Clear product context
                    Media.clear_product_context()
                
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
            
            # If no mockup found, skip this product entirely (don't include in PDF)
            if not mockup_media or not hasattr(mockup_media, 'file') or not mockup_media.file:
                logger.warning(f'Skipping product {product.id} ({product.title}) - no mockup image found')
                skipped_products.append(product.id)
                continue  # Skip this product entirely
            
            # Get image path for the mockup
            image_path = None
            try:
                # Get absolute path to the media file
                if hasattr(mockup_media.file, 'path'):
                    image_path = mockup_media.file.path
                else:
                    # Fallback: construct path from file name
                    image_path = os.path.join(settings.MEDIA_ROOT, mockup_media.file.name)
                
                # Verify file exists and is a supported format
                if not os.path.exists(image_path):
                    logger.warning(f'Mockup image not found at {image_path} for product {product.id}')
                    skipped_products.append(product.id)
                    continue  # Skip this product
                else:
                    # Verify it's a supported image format
                    file_ext = os.path.splitext(image_path.lower())[1]
                    if file_ext not in SUPPORTED_IMAGE_EXTENSIONS:
                        logger.warning(f'Mockup image has unsupported format {file_ext} for product {product.id}: {image_path}')
                        skipped_products.append(product.id)
                        continue  # Skip this product
            except Exception as e:
                logger.warning(f'Error getting image path for product {product.id}: {e}')
                skipped_products.append(product.id)
                continue  # Skip this product
            
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
            logger.warning(f'Skipped {len(skipped_products)} products without mockup images: {skipped_products}')
        
        pdf_download.included_products = included_products
        pdf_download.products_count = len(included_products)  # Use actual count of included products
        
        # Generate PDF with reportlab
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
            
            # Log customer information for debugging
            logger.info(f'PDF generation for download {pdf_download_id}: customer_name="{customer_name}", customer_mobile="{customer_mobile}"')
            
            for idx, product_info in enumerate(included_products, 1):
                # Add a new page for each product
                if idx > 1:
                    c.showPage()
                
                product_id = product_info['product_id']
                product_title = product_info['title']
                product_number = product_info.get('product_number', f"WD{product_id}")  # Get product number from dict
                image_path = product_info['image_path']
                
                if image_path and os.path.exists(image_path):
                    try:
                        # Open and get image dimensions
                        img = Image.open(image_path)
                        img_width, img_height = img.size
                        
                        # Calculate scaling to fit page (with margins)
                        # Reserve space at top for header (60 points - compact three boxes)
                        available_width = page_width - (2 * margin)
                        available_height = page_height - (2 * margin) - 60
                        
                        # Calculate scale to fit image within available space
                        scale_x = available_width / img_width
                        scale_y = available_height / img_height
                        scale = min(scale_x, scale_y)
                        
                        # Calculate centered position for image (below header)
                        scaled_width = img_width * scale
                        scaled_height = img_height * scale
                        x = (page_width - scaled_width) / 2
                        y = (page_height - scaled_height) / 2 - 30  # Offset down to make room for compact header
                        
                        # Draw compact header with 3 boxes in horizontal line
                        header_height = 55  # Compact height
                        header_y = page_height - margin - header_height
                        header_rect_width = page_width - (2 * margin)
                        
                        # Calculate box dimensions
                        box_spacing = 10  # Space between boxes
                        box_width = (header_rect_width - (2 * box_spacing)) / 3  # Three equal boxes
                        box_height = header_height - 10  # Slightly smaller than header
                        box_y = header_y + 5  # Small margin from top
                        
                        # Box 1 - For / Customer Name
                        box1_x = margin + 10
                        c.setFillColorRGB(1, 1, 1)  # White background for box
                        c.setStrokeColorRGB(0.85, 0.85, 0.9)
                        c.setLineWidth(0.5)
                        c.roundRect(box1_x, box_y, box_width, box_height, 4, fill=1, stroke=1)
                        
                        # Label
                        c.setFillColorRGB(0.5, 0.5, 0.55)
                        c.setFont("Helvetica", 9)
                        c.drawString(box1_x + 8, box_y + box_height - 12, "For")
                        
                        # Separator line inside box
                        c.setStrokeColorRGB(0.9, 0.9, 0.95)
                        c.setLineWidth(0.3)
                        c.line(box1_x + 6, box_y + box_height - 15, box1_x + box_width - 6, box_y + box_height - 15)
                        
                        # Value
                        c.setFillColorRGB(0.2, 0.2, 0.25)
                        c.setFont("Helvetica-Bold", 12)
                        if customer_name:
                            name_text = customer_name
                            # Truncate if too long
                            name_width = c.stringWidth(name_text, "Helvetica-Bold", 12)
                            max_name_width = box_width - 16
                            if name_width > max_name_width:
                                char_width = name_width / len(name_text)
                                max_chars = int(max_name_width / char_width) - 3
                                name_text = name_text[:max_chars] + "..."
                        else:
                            name_text = "[Not Provided]"
                        c.drawString(box1_x + 8, box_y + 8, name_text)
                        
                        # Box 2 - Contact / Mobile Number
                        box2_x = box1_x + box_width + box_spacing
                        c.setFillColorRGB(1, 1, 1)
                        c.roundRect(box2_x, box_y, box_width, box_height, 4, fill=1, stroke=1)
                        
                        # Label
                        c.setFillColorRGB(0.5, 0.5, 0.55)
                        c.setFont("Helvetica", 9)
                        c.drawString(box2_x + 8, box_y + box_height - 12, "Contact")
                        
                        # Separator line inside box
                        c.setStrokeColorRGB(0.9, 0.9, 0.95)
                        c.setLineWidth(0.3)
                        c.line(box2_x + 6, box_y + box_height - 15, box2_x + box_width - 6, box_y + box_height - 15)
                        
                        # Value
                        c.setFillColorRGB(0.2, 0.2, 0.25)
                        c.setFont("Helvetica-Bold", 12)
                        if customer_mobile:
                            contact_text = customer_mobile
                        else:
                            contact_text = "[Not Provided]"
                        c.drawString(box2_x + 8, box_y + 8, contact_text)
                        
                        # Box 3 - Design ID
                        box3_x = box2_x + box_width + box_spacing
                        c.setFillColorRGB(1, 1, 1)
                        c.roundRect(box3_x, box_y, box_width, box_height, 4, fill=1, stroke=1)
                        
                        # Label
                        c.setFillColorRGB(0.5, 0.5, 0.55)
                        c.setFont("Helvetica", 9)
                        c.drawString(box3_x + 8, box_y + box_height - 12, "Design ID")
                        
                        # Separator line inside box
                        c.setStrokeColorRGB(0.9, 0.9, 0.95)
                        c.setLineWidth(0.3)
                        c.line(box3_x + 6, box_y + box_height - 15, box3_x + box_width - 6, box_y + box_height - 15)
                        
                        # Value
                        c.setFillColorRGB(0.2, 0.2, 0.25)
                        c.setFont("Helvetica-Bold", 12)
                        design_id_text = product_number
                        c.drawString(box3_x + 8, box_y + 8, design_id_text)
                        
                        # Draw image below header
                        c.drawImage(image_path, x, y, width=scaled_width, height=scaled_height, preserveAspectRatio=True)
                        logger.info(f'Added metadata and image for product {product_id} on page {idx}')
                    except Exception as e:
                        logger.error(f'Error adding image for product {product_id}: {e}', exc_info=True)
                        # Draw header even if image fails
                        header_height = 55
                        header_y = page_height - margin - header_height
                        header_rect_width = page_width - (2 * margin)
                        box_spacing = 10
                        box_width = (header_rect_width - (2 * box_spacing)) / 3
                        box_height = header_height - 10
                        box_y = header_y + 5
                        
                        # Box 1 - For
                        box1_x = margin + 10
                        c.setFillColorRGB(1, 1, 1)
                        c.setStrokeColorRGB(0.85, 0.85, 0.9)
                        c.setLineWidth(0.5)
                        c.roundRect(box1_x, box_y, box_width, box_height, 4, fill=1, stroke=1)
                        c.setFillColorRGB(0.5, 0.5, 0.55)
                        c.setFont("Helvetica", 9)
                        c.drawString(box1_x + 8, box_y + box_height - 12, "For")
                        c.setStrokeColorRGB(0.9, 0.9, 0.95)
                        c.setLineWidth(0.3)
                        c.line(box1_x + 6, box_y + box_height - 15, box1_x + box_width - 6, box_y + box_height - 15)
                        c.setFillColorRGB(0.2, 0.2, 0.25)
                        c.setFont("Helvetica-Bold", 12)
                        if customer_name:
                            name_text = customer_name
                            name_width = c.stringWidth(name_text, "Helvetica-Bold", 12)
                            max_name_width = box_width - 16
                            if name_width > max_name_width:
                                char_width = name_width / len(name_text)
                                max_chars = int(max_name_width / char_width) - 3
                                name_text = name_text[:max_chars] + "..."
                        else:
                            name_text = "[Not Provided]"
                        c.drawString(box1_x + 8, box_y + 8, name_text)
                        
                        # Box 2 - Contact
                        box2_x = box1_x + box_width + box_spacing
                        c.setFillColorRGB(1, 1, 1)
                        c.roundRect(box2_x, box_y, box_width, box_height, 4, fill=1, stroke=1)
                        c.setFillColorRGB(0.5, 0.5, 0.55)
                        c.setFont("Helvetica", 9)
                        c.drawString(box2_x + 8, box_y + box_height - 12, "Contact")
                        c.setStrokeColorRGB(0.9, 0.9, 0.95)
                        c.setLineWidth(0.3)
                        c.line(box2_x + 6, box_y + box_height - 15, box2_x + box_width - 6, box_y + box_height - 15)
                        c.setFillColorRGB(0.2, 0.2, 0.25)
                        c.setFont("Helvetica-Bold", 12)
                        if customer_mobile:
                            contact_text = customer_mobile
                        else:
                            contact_text = "[Not Provided]"
                        c.drawString(box2_x + 8, box_y + 8, contact_text)
                        
                        # Box 3 - Design ID
                        box3_x = box2_x + box_width + box_spacing
                        c.setFillColorRGB(1, 1, 1)
                        c.roundRect(box3_x, box_y, box_width, box_height, 4, fill=1, stroke=1)
                        c.setFillColorRGB(0.5, 0.5, 0.55)
                        c.setFont("Helvetica", 9)
                        c.drawString(box3_x + 8, box_y + box_height - 12, "Design ID")
                        c.setStrokeColorRGB(0.9, 0.9, 0.95)
                        c.setLineWidth(0.3)
                        c.line(box3_x + 6, box_y + box_height - 15, box3_x + box_width - 6, box_y + box_height - 15)
                        c.setFillColorRGB(0.2, 0.2, 0.25)
                        c.setFont("Helvetica-Bold", 12)
                        design_id_text = product_number
                        c.drawString(box3_x + 8, box_y + 8, design_id_text)
                        
                        c.setFont("Helvetica", 16)
                        c.drawString(margin, page_height - margin - 100, "Image not available")
                else:
                    # Handle missing image case with header
                    logger.warning(f'No image path for product {product_id} in included_products')
                    header_height = 55
                    header_y = page_height - margin - header_height
                    header_rect_width = page_width - (2 * margin)
                    box_spacing = 10
                    box_width = (header_rect_width - (2 * box_spacing)) / 3
                    box_height = header_height - 10
                    box_y = header_y + 5
                    
                    # Box 1 - For
                    box1_x = margin + 10
                    c.setFillColorRGB(1, 1, 1)
                    c.setStrokeColorRGB(0.85, 0.85, 0.9)
                    c.setLineWidth(0.5)
                    c.roundRect(box1_x, box_y, box_width, box_height, 4, fill=1, stroke=1)
                    c.setFillColorRGB(0.5, 0.5, 0.55)
                    c.setFont("Helvetica", 9)
                    c.drawString(box1_x + 8, box_y + box_height - 12, "For")
                    c.setStrokeColorRGB(0.9, 0.9, 0.95)
                    c.setLineWidth(0.3)
                    c.line(box1_x + 6, box_y + box_height - 15, box1_x + box_width - 6, box_y + box_height - 15)
                    c.setFillColorRGB(0.2, 0.2, 0.25)
                    c.setFont("Helvetica-Bold", 12)
                    if customer_name:
                        name_text = customer_name
                        name_width = c.stringWidth(name_text, "Helvetica-Bold", 12)
                        max_name_width = box_width - 16
                        if name_width > max_name_width:
                            char_width = name_width / len(name_text)
                            max_chars = int(max_name_width / char_width) - 3
                            name_text = name_text[:max_chars] + "..."
                    else:
                        name_text = "[Not Provided]"
                    c.drawString(box1_x + 8, box_y + 8, name_text)
                    
                    # Box 2 - Contact
                    box2_x = box1_x + box_width + box_spacing
                    c.setFillColorRGB(1, 1, 1)
                    c.roundRect(box2_x, box_y, box_width, box_height, 4, fill=1, stroke=1)
                    c.setFillColorRGB(0.5, 0.5, 0.55)
                    c.setFont("Helvetica", 9)
                    c.drawString(box2_x + 8, box_y + box_height - 12, "Contact")
                    c.setStrokeColorRGB(0.9, 0.9, 0.95)
                    c.setLineWidth(0.3)
                    c.line(box2_x + 6, box_y + box_height - 15, box2_x + box_width - 6, box_y + box_height - 15)
                    c.setFillColorRGB(0.2, 0.2, 0.25)
                    c.setFont("Helvetica-Bold", 12)
                    if customer_mobile:
                        contact_text = customer_mobile
                    else:
                        contact_text = "[Not Provided]"
                    c.drawString(box2_x + 8, box_y + 8, contact_text)
                    
                    # Box 3 - Design ID
                    box3_x = box2_x + box_width + box_spacing
                    c.setFillColorRGB(1, 1, 1)
                    c.roundRect(box3_x, box_y, box_width, box_height, 4, fill=1, stroke=1)
                    c.setFillColorRGB(0.5, 0.5, 0.55)
                    c.setFont("Helvetica", 9)
                    c.drawString(box3_x + 8, box_y + box_height - 12, "Design ID")
                    c.setStrokeColorRGB(0.9, 0.9, 0.95)
                    c.setLineWidth(0.3)
                    c.line(box3_x + 6, box_y + box_height - 15, box3_x + box_width - 6, box_y + box_height - 15)
                    c.setFillColorRGB(0.2, 0.2, 0.25)
                    c.setFont("Helvetica-Bold", 12)
                    design_id_text = product_number
                    c.drawString(box3_x + 8, box_y + 8, design_id_text)
                    
                    c.setFont("Helvetica", 16)
                    c.drawString(margin, page_height - margin - 100, "No mockup image available")
            
            # Save PDF
            c.save()
            
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

