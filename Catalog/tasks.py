from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.core.files.storage import default_storage
from common.relations import attach_relation
from common.avif_converter import create_avif_from_media_file
import json
import logging
import os
import tempfile

from Catalog.models import (
    Product,
    Category,
    Tags,
    PDFDownload,
    PDFClient,
    PDFClientJob,
)
from MediaFiles.models import Media

logger = logging.getLogger(__name__)


# Image extensions for admin client PDFs.
# For client PDFs we ONLY use JPG mockups.
# Designs without a usable JPG are skipped entirely.
CLIENT_PDF_IMAGE_EXTENSIONS = (".jpg", ".jpeg")
CLIENT_PDF_JPG_EXTENSIONS = (".jpg", ".jpeg")


def generate_client_pdf_for_products(
    pdf_file_path,
    products,
    customer_name,
    customer_mobile,
    logo_path=None,
):
    """
    Generate a PDF file for a given list of products for admin PDF clients.
    Layout matches the customer mock PDF style (logo + name/number + design image).
    Uses only *_MOCKUP.jpg images (e.g. WDG00000001_MOCKUP.jpg); one image per product per page.
    Supports remote storage (S3 etc.) via default_storage fallback.

    Returns the created file size in bytes.
    """
    from django.conf import settings
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from PIL import Image

    # Prepare page
    page_width, page_height = letter
    margin = 50

    # Create PDF canvas
    c = canvas.Canvas(pdf_file_path, pagesize=letter)
    temp_files_to_cleanup = []

    # Generate one page per product that has a JPG mockup.
    page_index = 0
    for product in products:

        product_number = product.product_number or f"WD{product.id}"
        product_number_lower = product_number.lower()

        # Only use *_MOCKUP.jpg images (e.g. WDG00000001_MOCKUP.jpg).
        chosen_media = None
        try:
            media_list = product.get_media()
            for media in media_list:
                if not hasattr(media, "file") or not media.file:
                    continue
                file_name = getattr(media.file, "name", "") or ""
                if not file_name:
                    continue
                file_name_lower = file_name.lower()
                base_name_with_ext = os.path.basename(file_name_lower)
                base_no_ext, ext = os.path.splitext(base_name_with_ext)

                # Handle AVIF wrappers like WDG00000001_JPG.avif
                logical_ext = ext
                core_base = base_no_ext
                if ext == ".avif":
                    if base_no_ext.endswith("_jpg"):
                        logical_ext = ".jpg"
                        core_base = base_no_ext[:-4]

                if logical_ext not in CLIENT_PDF_JPG_EXTENSIONS:
                    continue
                base_name = core_base
                # Only accept *_MOCKUP.jpg (base name ends with _mockup)
                if not base_name.endswith("_mockup"):
                    continue
                # Prefer exact match: PRODUCT_NUMBER_MOCKUP.jpg
                if base_name == f"{product_number_lower}_mockup":
                    chosen_media = media
                    break
                if chosen_media is None:
                    chosen_media = media
        except Exception:
            chosen_media = None

        # Resolve image path (local or via default_storage for remote/S3)
        image_path = None
        if chosen_media and getattr(chosen_media, "file", None):
            try:
                file_name = getattr(chosen_media.file, "name", "") or ""
                if hasattr(chosen_media.file, "path"):
                    candidate = chosen_media.file.path
                else:
                    candidate = os.path.join(settings.MEDIA_ROOT, file_name)
                if os.path.exists(candidate):
                    image_path = candidate
                elif file_name and default_storage.exists(file_name):
                    # Derive logical suffix for temp file (respect _JPG AVIF wrappers)
                    base_name_with_ext = os.path.basename(file_name.lower())
                    base_no_ext, ext = os.path.splitext(base_name_with_ext)
                    suffix = ext
                    if ext == ".avif":
                        if base_no_ext.endswith("_jpg"):
                            suffix = ".jpg"
                    if suffix not in CLIENT_PDF_JPG_EXTENSIONS:
                        suffix = ".jpg"
                    with default_storage.open(file_name, "rb") as src:
                        fd, image_path = tempfile.mkstemp(suffix=suffix, prefix="pdf_img_")
                        os.close(fd)
                        with open(image_path, "wb") as dst:
                            dst.write(src.read())
                        temp_files_to_cleanup.append(image_path)
            except Exception:
                image_path = None

        # Prefer on-disk *_MOCKUP.jpg in the design folder if present:
        # MEDIA_ROOT/{user_id}/designs/{product_id}/PRODUCT_NUMBER_MOCKUP.jpg
        try:
            from django.conf import settings as _settings

            user_id = getattr(product, "created_by_id", None)
            if user_id:
                base_dir = os.path.join(
                    getattr(_settings, "MEDIA_ROOT", ""), str(user_id), "designs", str(product.id)
                )
                if os.path.isdir(base_dir):
                    preferred_names = [
                        f"{product_number}_MOCKUP.jpg",
                        f"{product_number}_MOCKUP.jpeg",
                        f"{product_number}_mockup.jpg",
                        f"{product_number}_mockup.jpeg",
                    ]
                    for fname in preferred_names:
                        candidate = os.path.join(base_dir, fname)
                        if os.path.exists(candidate):
                            image_path = candidate
                            break
        except Exception:
            pass

        # Final guard: we only allow real JPG files.
        # If there is no JPG on disk for this design, skip it.
        if not image_path or not os.path.exists(image_path):
            continue
        _, final_ext = os.path.splitext(image_path.lower())
        if final_ext not in CLIENT_PDF_JPG_EXTENSIONS:
            continue

        # Start a new page only when we actually render a design.
        if page_index > 0:
            c.showPage()
        page_index += 1

        page_w, page_h = page_width, page_height
        m = margin
        center_x = page_w / 2

        # Top-left logo
        logo_size = 56
        if logo_path and os.path.exists(logo_path):
            try:
                c.drawImage(
                    logo_path,
                    m,
                    page_h - m - logo_size,
                    width=logo_size,
                    height=logo_size,
                    preserveAspectRatio=True,
                )
            except Exception:
                pass

        # Top-center customer name and mobile
        name_text = customer_name or ""
        number_text = customer_mobile or ""
        c.setFillColorRGB(0.2, 0.2, 0.25)
        c.setFont("Helvetica-Bold", 14)
        name_width = c.stringWidth(name_text or " ", "Helvetica-Bold", 14)
        c.drawString(center_x - name_width / 2, page_h - m - 28, name_text[:60] or " ")
        c.setFont("Helvetica", 12)
        num_width = c.stringWidth(number_text or " ", "Helvetica", 12)
        c.drawString(center_x - num_width / 2, page_h - m - 46, number_text[:20] or " ")

        # Bottom design number
        c.setFont("Helvetica", 11)
        c.setFillColorRGB(0.35, 0.35, 0.4)
        c.drawString(m, m + 8, f"Design: {product_number}")

        # Center design image
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
                c.drawImage(
                    image_path,
                    img_x,
                    img_y,
                    width=sw,
                    height=sh,
                    preserveAspectRatio=True,
                )
            except Exception:
                c.setFont("Helvetica", 12)
                c.setFillColorRGB(0.5, 0.5, 0.55)
                c.drawString(center_x - 60, page_h / 2 - 20, "Image not available")
        else:
            c.setFont("Helvetica", 12)
            c.setFillColorRGB(0.5, 0.5, 0.55)
            c.drawString(center_x - 60, page_h / 2 - 20, "Image not available")

    c.save()

    for tmp in temp_files_to_cleanup:
        try:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass

    if not os.path.exists(pdf_file_path):
        raise Exception(f"PDF file was not created at {pdf_file_path}")
    file_size = os.path.getsize(pdf_file_path)
    if file_size == 0:
        raise Exception(f"PDF file was created but is empty (0 bytes) at {pdf_file_path}")
    return file_size

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
    logger.info(f"process_single_design_upload: starting for product_id={product_id}")
    try:
        # Get the product
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return {'status': 'failed', 'error': 'Product not found'}
        
        # Ensure product_number is available
        if not product.product_number:
            product.refresh_from_db()
            if not product.product_number:
                return {'status': 'failed', 'error': 'Product has no product_number'}
        
        product_number = product.product_number

        # Precompute log_path once (use module-level os) so no inner import shadows os in the loop
        _debug_log_path = os.getenv('DEBUG_LOG_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', 'debug.log'))

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

                _exists = default_storage.exists(file_path)
                # Use default_storage to check if file exists and open it
                # This works with both local and cloud storage backends
                if not _exists:
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
                try:
                    with open(_debug_log_path, 'a') as f:
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
                            with open(_debug_log_path, 'a') as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"Catalog/tasks.py:process_single_design_upload","message":"Media object created","data":{"media_id":media_obj.id,"saved_path":media_obj.file.name,"product_id":product.id},"timestamp":int(__import__('time').time()*1000)})+'\n')
                        except: pass
                        # #endregion
                        
                        # Validate file location - ensure it's in the correct product design folder
                        expected_path_prefix = f'{product.created_by.id}/designs/{product.id}/'
                        if not media_obj.file.name.startswith(expected_path_prefix):
                            error_msg = f'Media file saved to wrong location! Expected: {expected_path_prefix}*, Got: {media_obj.file.name}'
                            # #region agent log
                            try:
                                with open(_debug_log_path, 'a') as f:
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"Catalog/tasks.py:process_single_design_upload","message":"VALIDATION ERROR: File in wrong location","data":{"media_id":media_obj.id,"saved_path":media_obj.file.name,"expected_prefix":expected_path_prefix,"product_id":product.id},"timestamp":int(__import__('time').time()*1000)})+'\n')
                            except: pass
                            # #endregion
                finally:
                    # Clear product context
                    Media.clear_product_context()
                    # #region agent log
                    try:
                        with open(_debug_log_path, 'a') as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"Catalog/tasks.py:process_single_design_upload","message":"Product context cleared","data":{"product_id":product.id},"timestamp":int(__import__('time').time()*1000)})+'\n')
                    except: pass
                    # #endregion
                
                # Delete temporary file after processing
                try:
                    default_storage.delete(file_path)
                except Exception as e:
                    pass
                
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
                            pass
                    except Exception as avif_error:
                        pass
                
            except Exception as e:
                pass
        
        logger.info(f"process_single_design_upload: completed for product_id={product_id}, processed_files={processed_files}")
        return {'status': 'success', 'processed_files': processed_files}
        
    except Exception as e:
        logger.info(f"process_single_design_upload: failed for product_id={product_id}, error={e}")
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, name='Catalog.tasks.generate_pdf_task', max_retries=3)
def generate_pdf_task(self, pdf_download_id):
    """
    Generate PDF for a PDF download request.
    """
    logger.info(f"generate_pdf_task: starting for download_id={pdf_download_id}")
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
            
            
            # Create a dict to preserve order
            products_dict = {p.id: p for p in Product.objects.filter(
                id__in=selected_ids,
                status='active',
                visibility_status='show'
            )}
            
            # Preserve order from selected_products list - this is critical for sequence
            products = [products_dict[pid] for pid in selected_ids if pid in products_dict]
            
            product_ids_ordered = [p.id for p in products]
            
            if len(products) != len(selected_ids):
                missing_ids = set(selected_ids) - set(product_ids_ordered)
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
        
        # Get mockup images for each product and generate PDF
        from django.conf import settings
        from MediaFiles.models import Relation
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from PIL import Image

        # Supported image formats for PDF generation
        SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        UNSUPPORTED_EXTENSIONS = {".cdr", ".eps", ".ai", ".svg", ".pdf"}

        # Get user from PDFDownload
        user = pdf_download.get_user()
        if not user:
            pdf_dir = os.path.join(settings.MEDIA_ROOT, "pdfs")
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_filename = f"pdf_download_{pdf_download_id}.pdf"
            pdf_file_path = os.path.join(pdf_dir, pdf_filename)
            relative_path = f"pdfs/{pdf_filename}"
        else:
            user_id = user.id
            pdf_filename = f"pdf_download_{pdf_download_id}.pdf"
            pdf_dir = os.path.join(settings.MEDIA_ROOT, str(user_id), "pdfs")
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_file_path = os.path.join(pdf_dir, pdf_filename)
            relative_path = f"{user_id}/pdfs/{pdf_filename}"

        original_order = {product.id: idx for idx, product in enumerate(products)}
        included_products = []
        skipped_products = []
        temp_files_to_cleanup = []

        for idx, product in enumerate(products, 1):
            media_list = product.get_media()
            mockup_media = None

            for media in media_list:
                try:
                    if not hasattr(media, "file") or not media.file:
                        continue
                    file_name = media.file.name if hasattr(media.file, "name") else ""
                    if not file_name:
                        continue
                    file_name_lower = file_name.lower()
                    file_ext = os.path.splitext(file_name_lower)[1]
                    if file_ext in UNSUPPORTED_EXTENSIONS:
                        continue
                    base_name = os.path.splitext(os.path.basename(file_name_lower))[0]
                    is_mockup_by_name = base_name == "mockup" or "mockup" in base_name
                    is_mockup_by_meta = False
                    try:
                        relation = Relation.objects.filter(
                            relation_type="Product:Media",
                            id_1=product.pk,
                            id_2=media.pk,
                        ).first()
                        if relation and relation.meta:
                            meta_data = relation.meta
                            if isinstance(meta_data, dict):
                                is_mockup_by_meta = meta_data.get("is_mockup", False) or meta_data.get("type") == "mockup"
                            elif isinstance(meta_data, str):
                                meta_lower = str(meta_data).lower()
                                is_mockup_by_meta = "mockup" in meta_lower or '"is_mockup":true' in meta_lower
                    except Exception:
                        pass
                    if (is_mockup_by_name or is_mockup_by_meta) and file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                        mockup_media = media
                        break
                except Exception:
                    continue

            if not mockup_media or not hasattr(mockup_media, "file") or not mockup_media.file:
                for media in media_list:
                    try:
                        if not hasattr(media, "file") or not media.file:
                            continue
                        file_name = media.file.name if hasattr(media.file, "name") else ""
                        if not file_name:
                            continue
                        file_name_lower = file_name.lower()
                        file_ext = os.path.splitext(file_name_lower)[1]
                        if file_ext in SUPPORTED_IMAGE_EXTENSIONS:
                            mockup_media = media
                            break
                    except Exception:
                        continue
                if not mockup_media or not hasattr(mockup_media, "file") or not mockup_media.file:
                    skipped_products.append(product.id)
                    continue

            image_path = None
            try:
                if hasattr(mockup_media.file, "path"):
                    image_path = mockup_media.file.path
                else:
                    image_path = os.path.join(settings.MEDIA_ROOT, mockup_media.file.name)
                if not os.path.exists(image_path) and mockup_media.file.name:
                    try:
                        if default_storage.exists(mockup_media.file.name):
                            with default_storage.open(mockup_media.file.name, "rb") as src:
                                suffix = os.path.splitext(mockup_media.file.name)[1].lower()
                                if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
                                    suffix = ".jpg"
                                fd, image_path = tempfile.mkstemp(suffix=suffix, prefix="pdf_img_")
                                os.close(fd)
                                with open(image_path, "wb") as dst:
                                    dst.write(src.read())
                                temp_files_to_cleanup.append(image_path)
                        else:
                            image_path = None
                    except Exception:
                        image_path = None
                if not image_path or not os.path.exists(image_path):
                    skipped_products.append(product.id)
                    continue
                file_ext = os.path.splitext(image_path.lower())[1]
                if file_ext not in SUPPORTED_IMAGE_EXTENSIONS:
                    skipped_products.append(product.id)
                    continue
            except Exception:
                skipped_products.append(product.id)
                continue

            original_position = original_order.get(product.id, idx)
            included_products.append(
                {
                    "product_id": product.id,
                    "page_number": len(included_products) + 1,
                    "original_position": original_position,
                    "title": product.title,
                    "product_number": product.product_number or f"WD{product.id}",
                    "image_path": image_path,
                }
            )

        if not included_products:
            raise ValueError(
                f"No products with usable images for PDF. All {len(products)} product(s) were skipped. "
                "Ensure each design has at least one image (JPG, PNG, etc.)."
            )

        pdf_download.included_products = included_products
        pdf_download.products_count = len(included_products)

        try:
            # Refresh customer data
            pdf_download.refresh_from_db()
            customer_name = pdf_download.customer_name or ""
            customer_mobile = pdf_download.customer_mobile or ""

            logo_path = None
            if (
                pdf_download.customer_logo
                and hasattr(pdf_download.customer_logo, "path")
                and pdf_download.customer_logo.path
                and os.path.exists(pdf_download.customer_logo.path)
            ):
                logo_path = pdf_download.customer_logo.path
            if not logo_path:
                from django.conf import settings as dj_settings

                default_logo = getattr(dj_settings, "PDF_DEFAULT_LOGO_PATH", None)
                if default_logo and os.path.exists(default_logo):
                    logo_path = default_logo
                else:
                    alt_default = os.path.join(dj_settings.MEDIA_ROOT, "defaults", "wedesignz_logo.png")
                    if os.path.exists(alt_default):
                        logo_path = alt_default

            # Generate PDF pages
            page_width, page_height = letter
            margin = 50
            c = canvas.Canvas(pdf_file_path, pagesize=letter)

            for idx, product_info in enumerate(included_products, 1):
                if idx > 1:
                    c.showPage()

                product_id = product_info["product_id"]
                product_number = product_info.get("product_number", f"WD{product_id}")
                image_path = product_info["image_path"]

                page_w, page_h = page_width, page_height
                m = margin
                center_x = page_w / 2

                logo_size = 56
                if logo_path and os.path.exists(logo_path):
                    try:
                        c.drawImage(
                            logo_path,
                            m,
                            page_h - m - logo_size,
                            width=logo_size,
                            height=logo_size,
                            preserveAspectRatio=True,
                        )
                    except Exception:
                        pass

                name_text = customer_name or ""
                number_text = customer_mobile or ""
                c.setFillColorRGB(0.2, 0.2, 0.25)
                c.setFont("Helvetica-Bold", 14)
                name_width = c.stringWidth(name_text or " ", "Helvetica-Bold", 14)
                c.drawString(center_x - name_width / 2, page_h - m - 28, name_text[:60] or " ")
                c.setFont("Helvetica", 12)
                num_width = c.stringWidth(number_text or " ", "Helvetica", 12)
                c.drawString(center_x - num_width / 2, page_h - m - 46, number_text[:20] or " ")

                c.setFont("Helvetica", 11)
                c.setFillColorRGB(0.35, 0.35, 0.4)
                c.drawString(m, m + 8, f"Design: {product_number}")

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
                        c.drawImage(
                            image_path,
                            img_x,
                            img_y,
                            width=sw,
                            height=sh,
                            preserveAspectRatio=True,
                        )
                    except Exception:
                        c.setFont("Helvetica", 12)
                        c.setFillColorRGB(0.5, 0.5, 0.55)
                        c.drawString(center_x - 60, page_h / 2 - 20, "Image not available")
                else:
                    c.setFont("Helvetica", 12)
                    c.setFillColorRGB(0.5, 0.5, 0.55)
                    c.drawString(center_x - 60, page_h / 2 - 20, "Image not available")

            c.save()

            for tmp in temp_files_to_cleanup:
                try:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
                except Exception:
                    pass

            if not os.path.exists(pdf_file_path):
                raise Exception(f"PDF file was not created at {pdf_file_path}")

            file_size = os.path.getsize(pdf_file_path)
            if file_size == 0:
                raise Exception(f"PDF file was created but is empty (0 bytes) at {pdf_file_path}")

            pdf_download.pdf_file_path = relative_path
            pdf_download.file_size = file_size

            pdf_download.status = "completed"
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
                    pass
            except Exception as e:
                pass
            
        except Exception as e:
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
        logger.info(f"generate_pdf_task: completed for download_id={pdf_download_id}")
        return {'status': 'completed', 'download_id': pdf_download_id}
        
    except PDFDownload.DoesNotExist:
        raise
    except Exception as e:
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
        logger.info("cleanup_design_pdf_files: MEDIA_ROOT not set or not a directory, skipping")
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
            continue
        if not os.path.isfile(full_path):
            continue
        try:
            os.unlink(full_path)
            deleted_count += 1
        except Exception as e:
            error_count += 1
    result = {'deleted': deleted_count, 'errors': error_count}
    logger.info(f"cleanup_design_pdf_files: {result}")
    return result


@shared_task(bind=True, name="Catalog.tasks.generate_client_pdfs_task", max_retries=0)
def generate_client_pdfs_task(self, job_id):
    """
    Monolithic admin PDF client job.

    - Each PDF contains up to 100 designs.
    - A single job can generate at most 10 PDFs.
    - Designs are selected from all active/visible products, ordered by design number,
      and rendered using JPG-only logic inside generate_client_pdf_for_products.
    - All generated PDFs are stored under MEDIA_ROOT/admin_pdf_clients/<client_id>/jobs/<job_id>/
      and downloaded together as a ZIP.
    """
    from django.conf import settings
    from zipfile import ZipFile

    logger.info(f"generate_client_pdfs_task: starting for job_id={job_id}")

    MAX_DESIGNS_PER_PDF = 100
    MAX_PDFS_PER_JOB = 10

    try:
        # Lock the job row and mark it as processing.
        with transaction.atomic():
            job = (
                PDFClientJob.objects.select_for_update()
                .select_related("client")
                .get(id=job_id)
            )

            # Enforce per-client concurrency
            if PDFClientJob.objects.filter(
                client=job.client,
                status__in=["pending", "processing"],
            ).exclude(id=job.id).exists():
                job.status = "failed"
                job.error_message = "Another PDF generation job is already running for this client."
                job.progress_percent = 0
                job.save()
                return {"status": "failed", "reason": "concurrent_job"}

            job.status = "processing"
            job.progress_percent = 0

            # Normalize designs_per_pdf and requested_pdfs to enforce monolithic rules.
            requested_pdfs = max(1, min(int(job.requested_pdfs or 1), MAX_PDFS_PER_JOB))
            job.requested_pdfs = requested_pdfs
            job.designs_per_pdf = MAX_DESIGNS_PER_PDF
            job.total_designs_requested = requested_pdfs * MAX_DESIGNS_PER_PDF
            job.generated_pdfs = 0
            job.pdf_file_paths = []
            job.included_product_ids_by_pdf = []
            job.total_designs_used = 0
            job.save()

        media_root = getattr(settings, "MEDIA_ROOT", None)
        if not media_root or not os.path.isdir(media_root):
            job.status = "failed"
            job.error_message = "MEDIA_ROOT is not configured correctly."
            job.progress_percent = 0
            job.save()
            return {"status": "failed", "reason": "no_media_root"}

        client_id = job.client.id
        base_dir = os.path.join(
            media_root, "admin_pdf_clients", str(client_id), "jobs", str(job.id)
        )
        os.makedirs(base_dir, exist_ok=True)

        # Select products globally for this job:
        # active, visible, with a non-empty design number, ordered by product_number.
        max_products = MAX_DESIGNS_PER_PDF * requested_pdfs
        products_qs = (
            Product.objects.filter(status="active", visibility_status="show")
            .exclude(product_number__isnull=True)
            .exclude(product_number="")
            .order_by("product_number")
        )
        products = list(products_qs[:max_products])

        if not products:
            job.status = "failed"
            job.error_message = "No designs available to generate PDFs for this client."
            job.progress_percent = 0
            job.total_designs_requested = 0
            job.total_designs_used = 0
            job.save()
            return {"status": "failed", "reason": "no_designs"}

        pdf_paths = []
        included_lists = []

        # Chunk products into sequential groups of 100 designs.
        for index in range(requested_pdfs):
            start = index * MAX_DESIGNS_PER_PDF
            end = start + MAX_DESIGNS_PER_PDF
            chunk = products[start:end]
            if not chunk:
                break

            pdf_filename = f"client_{client_id}_job_{job.id}_part_{index + 1}.pdf"
            pdf_path = os.path.join(base_dir, pdf_filename)

            # Resolve logo path (customer_logo or default)
            logo_path = None
            if job.customer_logo and hasattr(job.customer_logo, "path") and job.customer_logo.path:
                if os.path.exists(job.customer_logo.path):
                    logo_path = job.customer_logo.path
            if not logo_path:
                default_logo = getattr(settings, "PDF_DEFAULT_LOGO_PATH", None)
                if default_logo and os.path.exists(default_logo):
                    logo_path = default_logo
                else:
                    alt_default = os.path.join(
                        media_root, "defaults", "wedesignz_logo.png"
                    )
                    if os.path.exists(alt_default):
                        logo_path = alt_default

            # This helper uses only JPG mockups and skips designs without a usable JPG.
            file_size = generate_client_pdf_for_products(
                pdf_file_path=pdf_path,
                products=chunk,
                customer_name=job.customer_name,
                customer_mobile=job.customer_mobile,
                logo_path=logo_path,
            )

            # If the PDF is empty or invalid, skip counting it.
            if not os.path.exists(pdf_path) or file_size <= 0:
                continue

            rel_path = os.path.relpath(pdf_path, media_root)
            pdf_paths.append(rel_path)
            included_lists.append([p.id for p in chunk])

            job.generated_pdfs += 1
            job.progress_percent = int(
                100 * job.generated_pdfs / max(1, requested_pdfs)
            )
            job.total_designs_used = sum(len(ids) for ids in included_lists)
            job.save()

        if not pdf_paths:
            job.status = "failed"
            job.error_message = "No PDFs could be generated for this job."
            job.progress_percent = 0
            job.total_designs_requested = 0
            job.total_designs_used = 0
            job.save()
            return {"status": "failed", "reason": "no_pdfs"}

        # Create ZIP archive containing all PDFs
        zip_filename = f"client_{client_id}_job_{job.id}_pdfs.zip"
        zip_path = os.path.join(base_dir, zip_filename)
        with ZipFile(zip_path, "w") as zip_file:
            for rel_path in pdf_paths:
                abs_path = os.path.join(media_root, rel_path)
                if os.path.exists(abs_path):
                    arcname = os.path.basename(abs_path)
                    zip_file.write(abs_path, arcname=arcname)

        job.pdf_file_paths = pdf_paths
        job.zip_file_path = os.path.relpath(zip_path, media_root)
        job.included_product_ids_by_pdf = included_lists
        job.total_designs_used = sum(len(ids) for ids in included_lists)
        job.status = "completed"
        job.progress_percent = 100
        job.save()

        logger.info(
            f"generate_client_pdfs_task: completed for job_id={job_id}, pdfs={len(pdf_paths)}"
        )
        return {
            "status": "completed",
            "job_id": job_id,
            "pdfs": len(pdf_paths),
            "zip_file_path": job.zip_file_path,
        }
    except PDFClientJob.DoesNotExist:
        logger.info(f"generate_client_pdfs_task: job_id={job_id} does not exist")
        return {"status": "not_found", "job_id": job_id}
    except Exception as exc:
        try:
            job = PDFClientJob.objects.get(id=job_id)
            job.status = "failed"
            job.error_message = str(exc)
            job.progress_percent = 0
            job.save()
        except Exception:
            pass
        logger.info(f"generate_client_pdfs_task: failed for job_id={job_id}, error={exc}")
        return {"status": "failed", "job_id": job_id, "error": str(exc)}


# Only index PNG for visual search (per design media storage)
VISUAL_SEARCH_IMAGE_EXTENSIONS = ('.png',)


def _set_huggingface_timeout_for_visual_search(timeout_seconds=300):
    """Set longer HTTP timeout for Hugging Face Hub when loading visual_search models."""
    try:
        from huggingface_hub import set_client_factory
        import httpx
        set_client_factory(lambda: httpx.Client(timeout=httpx.Timeout(float(timeout_seconds))))
    except Exception as e:
        logger.warning(f"Could not set Hugging Face timeout: {e}")


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
            return {'status': 'skipped', 'reason': 'product_not_found'}

        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if not media_root or not os.path.isdir(media_root):
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
                continue
            images_data.append({
                'ProductId': str(product.product_number),
                'MediaFileId': str(media.id),
                'image': img,
            })

        if not images_data:
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
        return {'status': 'ok', 'indexed': success_count, 'total': len(images_data)}
    except Exception as e:
        return {'status': 'failed', 'error': str(e)}

