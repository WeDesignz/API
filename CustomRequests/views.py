from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.core.files.storage import default_storage
from .models import CustomOrderRequest
from .serializers import (
    CustomOrderRequestSerializer
)
import io
import zipfile
from MediaFiles.models import Media, Relation
from common.relations import get_related

@swagger_auto_schema(
    method='get',
    operation_summary='Get Custom Requests',
    operation_description='Get user custom order requests with filtering and pagination.',
    manual_parameters=[
        openapi.Parameter('status', openapi.IN_QUERY, description='Filter by status', type=openapi.TYPE_STRING, enum=['pending', 'in_progress', 'completed', 'cancelled']),
        openapi.Parameter('search', openapi.IN_QUERY, description='Search by title or description', type=openapi.TYPE_STRING),
        openapi.Parameter('page', openapi.IN_QUERY, description='Page number', type=openapi.TYPE_INTEGER)
    ],
    responses={
        200: openapi.Response(
            description='Custom requests retrieved successfully',
            examples={
                'application/json': {
                    'requests': [
                        {
                            'id': 1,
                            'title': 'Custom Logo Design',
                            'description': 'Need a modern logo for my startup',
                            'status': 'pending',
                            'budget': 500.00,
                            'delivery_time': '3 days',
                            'created_at': '2024-01-01T00:00:00Z'
                        }
                    ],
                    'total_requests': 1,
                    'current_page': 1,
                    'total_pages': 1
                }
            }
        ),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Custom Requests']
)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def custom_requests_list(request):
    """
    Get user's custom requests or create a new one.
    """
    if request.method == 'GET':
        status_filter = request.GET.get('status')
        search = request.GET.get('search')
        
        requests = CustomOrderRequest.objects.filter(created_by=request.user)
        
        if status_filter:
            requests = requests.filter(status=status_filter)
        
        if search:
            requests = requests.filter(
                Q(title__icontains=search) | 
                Q(description__icontains=search)
            )
        
        requests = requests.order_by('-created_at')
        
        return Response({
            'custom_requests': CustomOrderRequestSerializer(requests, many=True).data,
            'total_requests': requests.count()
        })
    
    elif request.method == 'POST':
        serializer = CustomOrderRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response({
                'message': 'Custom request created successfully',
                'custom_request': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_summary='Custom Request Detail',
    operation_description='Custom Request Detail endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def custom_request_detail(request, request_id):
    """
    Get, update, or delete a specific custom request.
    """
    try:
        custom_request = CustomOrderRequest.objects.get(
            id=request_id,
            created_by=request.user
        )
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom request not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = CustomOrderRequestSerializer(custom_request, context={'request': request})
        return Response({
            'custom_request': serializer.data
        })
    
    elif request.method == 'PUT':
        # Only allow updates if status is pending
        if custom_request.status != 'pending':
            return Response({
                'error': 'Cannot update request that is not pending'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = CustomOrderRequestSerializer(custom_request, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response({
                'message': 'Custom request updated successfully',
                'custom_request': serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # Only allow deletion if status is pending
        if custom_request.status != 'pending':
            return Response({
                'error': 'Cannot delete request that is not pending'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        custom_request.delete()
        return Response({
            'message': 'Custom request deleted successfully'
        })

@swagger_auto_schema(
    method='post',
    operation_summary='Submit Custom Request',
    operation_description='Submit Custom Request endpoint',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'data': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Request data'
            )
        }
    ),
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_custom_request(request):
    """
    Submit a custom request with payment.
    """
    from Orders.models import Order
    from common.business_config import BusinessConfig
    from decimal import Decimal
    import os
    
    title = request.data.get('title', '').strip() or 'Custom Order'
    description = request.data.get('description', '').strip() or 'No description provided'
    # Get default price from system config
    default_price = float(BusinessConfig.get_custom_order_price())
    
    # Get budget and convert to float (FormData sends strings)
    budget_str = request.data.get('budget', default_price)
    try:
        budget = float(budget_str) if budget_str is not None else default_price
    except (ValueError, TypeError):
        budget = default_price
    
    # Validate budget
    if budget is None or budget <= 0:
        return Response({
            'error': 'Budget must be a positive amount'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate against minimum price from config
    if budget < default_price:
        return Response({
            'error': f'Minimum budget is ₹{default_price}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create custom request
    custom_request = CustomOrderRequest.objects.create(
        title=title,
        description=description,
        budget=budget,
        created_by=request.user
    )
    
    # Handle file uploads (reference files)
    uploaded_files = []
    if request.FILES:
        # Get all files from request.FILES
        files = []
        # Check for 'files' key (multiple files with same key)
        if 'files' in request.FILES:
            files_list = request.FILES.getlist('files')
            files.extend(files_list)
        # Also check for individual file keys
        for key in request.FILES:
            if key != 'files':  # Skip 'files' as we already handled it
                file_obj = request.FILES[key]
                files.append(file_obj)
        
        # Helper function to determine media_type from filename
        def get_media_type_from_filename(filename):
            """Determine media_type from file extension."""
            if not filename:
                return 'other'
            filename_lower = filename.lower()
            ext = os.path.splitext(filename_lower)[1]
            
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']:
                return 'image'
            elif ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv']:
                return 'video'
            elif ext == '.cdr':
                return 'cdr'
            elif ext == '.eps':
                return 'eps'
            elif ext == '.pdf':
                return 'pdf'
            elif ext in ['.doc']:
                return 'doc'
            elif ext in ['.docx']:
                return 'docx'
            elif ext in ['.xls']:
                return 'xls'
            elif ext in ['.xlsx']:
                return 'xlsx'
            else:
                return 'other'
        
        # Upload files and attach to custom request
        for file_obj in files:
            try:
                # Determine media_type from filename
                media_type = get_media_type_from_filename(file_obj.name)
                
                # Create Media object
                media_obj = Media.objects.create(
                    file=file_obj,
                    media_type=media_type,
                    created_by=request.user
                )
                
                # Attach to custom request (without 'delivery_file' meta, so it's a reference file)
                custom_request.attach_media(media_obj, meta=None, created_by=request.user)
                uploaded_files.append(media_obj.id)
            except Exception as e:
                # Log error but don't fail the entire request
                import logging
                logger = logging.getLogger(__name__)

                continue
    
    # Create corresponding Order record with order_type='custom'
    order = Order.objects.create(
        order_type='custom',
        product_ids='',  # Custom orders don't have product IDs
        total_amount=budget,
        status='pending',  # Will be updated to 'success' after payment
        custom_order_request=custom_request,
        created_by=request.user
    )
    
    # Here you would integrate with Razorpay for payment
    # For now, we'll just return the request details
    
    return Response({
        'message': 'Custom request submitted successfully',
        'custom_request': CustomOrderRequestSerializer(custom_request).data,
        'order_id': order.id,
        'payment_required': True,
        'amount': float(budget),
        'payment_message': 'Please complete payment to process your custom request',
        'uploaded_files': uploaded_files
    }, status=status.HTTP_201_CREATED)

@swagger_auto_schema(
    method='get',
    operation_summary='Custom Request Status',
    operation_description='Custom Request Status endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def custom_request_status(request, request_id):
    """
    Get status of a specific custom request.
    """
    try:
        custom_request = CustomOrderRequest.objects.get(
            id=request_id,
            created_by=request.user
        )
        
        return Response({
            'custom_request': CustomOrderRequestSerializer(custom_request).data,
            'status': custom_request.get_status_display(),
            'created_at': custom_request.created_at,
            'updated_at': custom_request.updated_at
        })
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom request not found'
        }, status=status.HTTP_404_NOT_FOUND)

@swagger_auto_schema(
    method='post',
    operation_summary='Cancel Custom Request',
    operation_description='Cancel Custom Request endpoint',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'data': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Request data'
            )
        }
    ),
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_custom_request(request, request_id):
    """
    Cancel a custom request.
    """
    try:
        custom_request = CustomOrderRequest.objects.get(
            id=request_id,
            created_by=request.user
        )
        
        if custom_request.status in ['completed', 'cancelled']:
            return Response({
                'error': 'Cannot cancel request that is already completed or cancelled'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        custom_request.status = 'cancelled'
        custom_request.save()
        
        return Response({
            'message': 'Custom request cancelled successfully',
            'custom_request': CustomOrderRequestSerializer(custom_request).data
        })
    
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom request not found'
        }, status=status.HTTP_404_NOT_FOUND)

@swagger_auto_schema(
    method='get',
    operation_summary='Custom Request Timer',
    operation_description='Custom Request Timer endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def custom_request_timer(request, request_id):
    """
    Get timer information for a custom request (1 hour delivery promise).
    """
    try:
        custom_request = CustomOrderRequest.objects.get(
            id=request_id,
            created_by=request.user
        )
        
        if custom_request.status != 'in_progress':
            return Response({
                'error': 'Request is not in progress'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Calculate time remaining from settings
        from common.business_config import BusinessConfig
        time_remaining = custom_request.created_at + timezone.timedelta(hours=BusinessConfig.get_custom_order_time_slot_hours()) - timezone.now()
        
        if time_remaining.total_seconds() <= 0:
            time_remaining = timezone.timedelta(seconds=0)
        
        return Response({
            'custom_request': CustomOrderRequestSerializer(custom_request).data,
            'timer': {
                'time_remaining_seconds': int(time_remaining.total_seconds()),
                'time_remaining_formatted': str(time_remaining),
                'is_expired': time_remaining.total_seconds() <= 0,
                'delivery_promise': BusinessConfig.get_delivery_promise_text()
            }
        })
    
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom request not found'
        }, status=status.HTTP_404_NOT_FOUND)

@swagger_auto_schema(
    method='get',
    operation_summary='Custom Request History',
    operation_description='Custom Request History endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def custom_request_history(request):
    """
    Get user's custom request history with filtering.
    """
    status_filter = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    requests = CustomOrderRequest.objects.filter(created_by=request.user)
    
    if status_filter:
        requests = requests.filter(status=status_filter)
    
    if date_from:
        requests = requests.filter(created_at__gte=date_from)
    
    if date_to:
        requests = requests.filter(created_at__lte=date_to)
    
    requests = requests.order_by('-created_at')
    
    # Get statistics
    total_requests = requests.count()
    pending_requests = requests.filter(status='pending').count()
    completed_requests = requests.filter(status='completed').count()
    cancelled_requests = requests.filter(status='cancelled').count()
    
    return Response({
        'custom_requests': CustomOrderRequestSerializer(requests, many=True).data,
        'statistics': {
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'completed_requests': completed_requests,
            'cancelled_requests': cancelled_requests
        }
    })

@swagger_auto_schema(
    method='get',
    operation_summary='Custom Request Media',
    operation_description='Custom Request Media endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def custom_request_media(request, request_id):
    """
    Get media files associated with a custom request.
    """
    try:
        custom_request = CustomOrderRequest.objects.get(
            id=request_id,
            created_by=request.user
        )
        
        # Get associated media files
        media_files = custom_request.get_media()
        
        serializer = CustomOrderRequestSerializer(custom_request, context={'request': request})
        
        return Response({
            'custom_request': serializer.data,
            'media_files': media_files,
            'total_media': len(media_files)
        })
    
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom request not found'
        }, status=status.HTTP_404_NOT_FOUND)

@swagger_auto_schema(
    method='get',
    operation_summary='Download Custom Order Reference Files ZIP',
    operation_description='Download all reference files for a custom order as a zip file.',
    responses={
        200: openapi.Response(description='Zip file download'),
        400: openapi.Response(description='Bad request - order not found or no reference files'),
        401: openapi.Response(description='Unauthorized - authentication required'),
        403: openapi.Response(description='Forbidden - order belongs to another user')
    },
    tags=['Custom Requests']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_custom_order_reference_files_zip(request, request_id):
    """
    Download all reference files for a custom order as a zip file.
    """
    try:
        custom_request = CustomOrderRequest.objects.get(id=request_id)
        # For admin users, allow access to any order
        # For regular users, only allow access to their own orders
        from CoreAdmin.models import AdminUserProfile
        is_admin = AdminUserProfile.objects.filter(user=request.user).exists()
        if not is_admin and custom_request.created_by != request.user:
            return Response({
                'error': 'You do not have permission to access this order'
            }, status=status.HTTP_403_FORBIDDEN)
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom order not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get all media files for this custom order
    media_files = custom_request.get_media()
    reference_files = []
    delivery_file_ids = set()
    
    # First, collect all delivery file IDs
    for m in media_files:
        try:
            relation = Relation.objects.filter(
                relation_type='CustomRequest:Media',
                id_1=custom_request.pk,
                id_2=m.pk
            ).first()
            
            if relation and relation.meta:
                meta_data = relation.meta
                is_delivery_file = False
                if isinstance(meta_data, dict):
                    is_delivery_file = meta_data.get('type') == 'delivery_file'
                elif isinstance(meta_data, str):
                    is_delivery_file = 'delivery_file' in str(meta_data).lower()
                
                if is_delivery_file:
                    delivery_file_ids.add(m.pk)
        except Exception:
            continue
    
    # Now collect all non-delivery files as reference files
    for m in media_files:
        if m.pk not in delivery_file_ids:
            reference_files.append(m)
    
    if not reference_files:
        return Response({
            'error': 'No reference files found for this order'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create zip file in memory
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for media in reference_files:
                if media.file:
                    try:
                        # Get file path
                        file_path = media.file.name
                        
                        # Read file from storage
                        if default_storage.exists(file_path):
                            with default_storage.open(file_path, 'rb') as storage_file:
                                file_content = storage_file.read()
                                
                                # Get original filename or use a default
                                file_name = media.file.name.split('/')[-1] if '/' in media.file.name else media.file.name
                                
                                # Add to zip with sanitized filename
                                zip_file.writestr(file_name, file_content)
                    except Exception as e:
                        # Log error but continue with other files
                        import logging
                        logger = logging.getLogger(__name__)

                        continue
        
        # Prepare response
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        # Sanitize title for filename
        safe_title = custom_request.title.replace(" ", "_").replace("/", "_").replace("\\", "_")
        safe_title = ''.join(c for c in safe_title if c.isalnum() or c in ('_', '-'))[:50]
        response['Content-Disposition'] = f'attachment; filename="order_{request_id}_reference_files.zip"'
        response['Content-Length'] = zip_buffer.tell()
        
        return response
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': f'Failed to create zip file: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary='Download Custom Order Deliverables ZIP',
    operation_description='Download all deliverable files for a custom order as a zip file. Only available for completed orders with deliverables.',
    responses={
        200: openapi.Response(description='Zip file download'),
        400: openapi.Response(description='Bad request - order not found or no deliverables'),
        401: openapi.Response(description='Unauthorized - authentication required'),
        403: openapi.Response(description='Forbidden - order belongs to another user')
    },
    tags=['Custom Requests']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_custom_order_deliverables_zip(request, request_id):
    """
    Download all deliverable files for a custom order as a zip file.
    """
    try:
        custom_request = CustomOrderRequest.objects.get(
            id=request_id,
            created_by=request.user
        )
    except CustomOrderRequest.DoesNotExist:
        return Response({
            'error': 'Custom order not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if order has deliverables
    if not custom_request.delivery_files_uploaded:
        return Response({
            'error': 'No deliverables available for this order yet'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get all media files for this custom order
    media_files = custom_request.get_media()
    deliverables = []
    
    # Filter media files that are delivery files
    for m in media_files:
        try:
            # Check if this media has delivery_file in relation meta
            relation = Relation.objects.filter(
                relation_type='CustomRequest:Media',
                id_1=custom_request.pk,
                id_2=m.pk
            ).first()
            
            if relation and relation.meta:
                meta_data = relation.meta
                # Check if metadata indicates this is a delivery file
                is_delivery_file = False
                if isinstance(meta_data, dict):
                    is_delivery_file = meta_data.get('type') == 'delivery_file'
                elif isinstance(meta_data, str):
                    is_delivery_file = 'delivery_file' in str(meta_data).lower()
                
                if is_delivery_file:
                    deliverables.append(m)
        except Exception:
            continue
    
    if not deliverables:
        return Response({
            'error': 'No deliverable files found for this order'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create zip file in memory
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for media in deliverables:
                if media.file:
                    try:
                        # Get file path
                        file_path = media.file.name
                        
                        # Read file from storage
                        if default_storage.exists(file_path):
                            with default_storage.open(file_path, 'rb') as storage_file:
                                file_content = storage_file.read()
                                
                                # Get original filename or use a default
                                file_name = media.file.name.split('/')[-1] if '/' in media.file.name else media.file.name
                                
                                # Add to zip with sanitized filename
                                zip_file.writestr(file_name, file_content)
                    except Exception as e:
                        # Log error but continue with other files
                        import logging
                        logger = logging.getLogger(__name__)

                        continue
        
        # Prepare response
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        # Sanitize title for filename
        safe_title = custom_request.title.replace(" ", "_").replace("/", "_").replace("\\", "_")
        safe_title = ''.join(c for c in safe_title if c.isalnum() or c in ('_', '-'))[:50]
        response['Content-Disposition'] = f'attachment; filename="{safe_title}_deliverables_{request_id}.zip"'
        response['Content-Length'] = zip_buffer.tell()
        
        return response
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': f'Failed to create zip file: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== COMMENT SYSTEM VIEWS ====================

# Comment endpoints removed - use OrderComment via Order model instead
# Comments are accessed through /api/orders/{order_id}/comments/
