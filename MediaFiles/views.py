from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Count
from .models import Media
from .serializers import MediaSerializer


@swagger_auto_schema(
    method='post',
    operation_summary='Upload Media Files',
    operation_description='Upload media files (images, videos, documents) to the platform.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'file': openapi.Schema(
                type=openapi.TYPE_FILE,
                description='Media file to upload',
                example='image.jpg'
            ),
            'title': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Media title',
                example='Product Image'
            ),
            'description': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Media description',
                example='High-quality product image'
            ),
            'media_type': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Type of media',
                example='image',
                enum=['image', 'video', 'document', 'audio']
            ),
            'visibility': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='File visibility access policy',
                example='private',
                enum=['public', 'private']
            )
        },
        required=['file']
    ),
    responses={
        201: openapi.Response(
            description='Media uploaded successfully',
            examples={
                'application/json': {
                    'message': 'Media uploaded successfully',
                    'media': {
                        'id': 1,
                        'title': 'Product Image',
                        'description': 'High-quality product image',
                        'file_url': 'https://example.com/media/image.jpg',
                        'media_type': 'image',
                        'file_size': 1024000,
                        'created_at': '2024-01-01T00:00:00Z'
                    }
                }
            }
        ),
        400: openapi.Response(description='Bad request - invalid file or validation errors'),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Media Files']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_media(request):
    """
    Upload media files.
    """
    serializer = MediaSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(created_by=request.user)
        return Response({
            'message': 'Media uploaded successfully',
            'media': serializer.data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_summary='My Media',
    operation_description='My Media endpoint',
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
def my_media(request):
    """
    Get user's media files.
    """
    media_files = Media.objects.filter(created_by=request.user).order_by('-created_at')
    return Response({
        'media_files': MediaSerializer(media_files, many=True).data,
        'total_media': media_files.count()
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Media Detail',
    operation_description='Media Detail endpoint',
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
def media_detail(request, media_id):
    """
    Get, update, or delete specific media file.
    """
    try:
        media = Media.objects.get(id=media_id, created_by=request.user)
    except Media.DoesNotExist:
        return Response({
            'error': 'Media file not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        return Response({
            'media': MediaSerializer(media).data
        })
    
    elif request.method == 'PUT':
        serializer = MediaSerializer(media, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response({
                'message': 'Media updated successfully',
                'media': serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        media.delete()
        return Response({
            'message': 'Media deleted successfully'
        })


@swagger_auto_schema(
    method='delete',
    operation_summary='Delete Media',
    operation_description='Delete Media endpoint',
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

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_media(request, media_id):
    """
    Delete a media file.
    """
    try:
        media = Media.objects.get(id=media_id, created_by=request.user)
        media.delete()
        return Response({
            'message': 'Media deleted successfully'
        })
    except Media.DoesNotExist:
        return Response({
            'error': 'Media file not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='get',
    operation_summary='Search Media',
    operation_description='Search Media endpoint',
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
def search_media(request):
    """
    Search media files.
    """
    search_query = request.GET.get('search', '')
    media_type = request.GET.get('media_type')
    
    media_files = Media.objects.filter(created_by=request.user)
    
    if search_query:
        media_files = media_files.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    if media_type:
        media_files = media_files.filter(media_type=media_type)
    
    media_files = media_files.order_by('-created_at')
    
    return Response({
        'media_files': MediaSerializer(media_files, many=True).data,
        'total_media': media_files.count()
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Media Stats',
    operation_description='Media Stats endpoint',
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
def media_stats(request):
    """
    Get media statistics for user.
    """
    user_media = Media.objects.filter(created_by=request.user)
    
    total_media = user_media.count()
    total_size = sum([float(media.file_size) for media in user_media if media.file_size])
    
    media_type_stats = {}
    for media_type, _ in Media.MEDIA_TYPE_CHOICES:
        count = user_media.filter(media_type=media_type).count()
        media_type_stats[media_type] = count
    
    return Response({
        'total_media': total_media,
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'media_type_distribution': media_type_stats
    })
