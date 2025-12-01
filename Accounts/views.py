from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.db.models import Q, Count
from django.contrib.auth.models import User
from .serializers import UserSerializer


@swagger_auto_schema(
    method='get',
    operation_summary='Users List',
    operation_description='Users List endpoint',
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
@permission_classes([IsAdminUser])
def users_list(request):
    """
    Get all users (admin only).
    """
    users = User.objects.all().order_by('-date_joined')
    return Response({
        'users': UserSerializer(users, many=True).data,
        'total_users': users.count()
    })


@swagger_auto_schema(
    method='get',
    operation_summary='User Detail',
    operation_description='User Detail endpoint',
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
@permission_classes([IsAdminUser])
def user_detail(request, user_id):
    """
    Get specific user details (admin only).
    """
    try:
        user = User.objects.get(id=user_id)
        return Response({
            'user': UserSerializer(user).data
        })
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='post',
    operation_summary='Activate User',
    operation_description='Activate User endpoint',
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
@permission_classes([IsAdminUser])
def activate_user(request, user_id):
    """
    Activate a user account (admin only).
    """
    try:
        user = User.objects.get(id=user_id)
        user.is_active = True
        user.save()
        return Response({
            'message': 'User activated successfully',
            'user': UserSerializer(user).data
        })
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='post',
    operation_summary='Deactivate User',
    operation_description='Deactivate User endpoint',
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
@permission_classes([IsAdminUser])
def deactivate_user(request, user_id):
    """
    Deactivate a user account (admin only).
    """
    try:
        user = User.objects.get(id=user_id)
        user.is_active = False
        user.save()
        return Response({
            'message': 'User deactivated successfully',
            'user': UserSerializer(user).data
        })
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='delete',
    operation_summary='Delete User',
    operation_description='Delete User endpoint',
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
@permission_classes([IsAdminUser])
def delete_user(request, user_id):
    """
    Delete a user account (admin only).
    """
    try:
        user = User.objects.get(id=user_id)
        user.delete()
        return Response({
            'message': 'User deleted successfully'
        })
    except User.DoesNotExist:
        return Response({
            'error': 'User not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='get',
    operation_summary='User Stats',
    operation_description='User Stats endpoint',
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
@permission_classes([IsAdminUser])
def user_stats(request):
    """
    Get user statistics (admin only).
    """
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    inactive_users = User.objects.filter(is_active=False).count()
    staff_users = User.objects.filter(is_staff=True).count()
    superusers = User.objects.filter(is_superuser=True).count()
    
    return Response({
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'staff_users': staff_users,
        'superusers': superusers
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Search Users',
    operation_description='Search Users endpoint',
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
@permission_classes([IsAdminUser])
def search_users(request):
    """
    Search users (admin only).
    """
    search_query = request.GET.get('search', '')
    is_active = request.GET.get('is_active')
    is_staff = request.GET.get('is_staff')
    
    users = User.objects.all()
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    if is_active is not None:
        users = users.filter(is_active=is_active.lower() == 'true')
    
    if is_staff is not None:
        users = users.filter(is_staff=is_staff.lower() == 'true')
    
    users = users.order_by('-date_joined')
    
    return Response({
        'users': UserSerializer(users, many=True).data,
        'total_users': users.count()
    })
