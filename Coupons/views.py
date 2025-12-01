from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Q, Count
from django.utils import timezone
from .models import Coupon, CouponUsage
from .serializers import CouponSerializer, CouponUsageSerializer
from CoreAdmin.auth import admin_required
@swagger_auto_schema(
    method='get',
    operation_summary='Admin Coupon List',
    operation_description='List all coupons for admin management.',
    manual_parameters=[
        openapi.Parameter(
            'search',
            openapi.IN_QUERY,
            description='Search by coupon name or code',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'status',
            openapi.IN_QUERY,
            description='Filter by coupon status',
            type=openapi.TYPE_STRING,
            enum=[choice[0] for choice in Coupon.STATUS_CHOICES]
        ),
    ],
    responses={
        200: openapi.Response(description='Coupons retrieved successfully'),
        403: openapi.Response(description='Access denied'),
    },
    tags=['Coupons']
)
@swagger_auto_schema(
    method='post',
    operation_summary='Create Coupon (Admin)',
    operation_description='Create a new coupon from the admin dashboard.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'name': openapi.Schema(type=openapi.TYPE_STRING, description='Coupon name'),
            'code': openapi.Schema(type=openapi.TYPE_STRING, description='Unique coupon code'),
            'applied_to_base': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            'applied_to_prime': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            'applied_to_premium': openapi.Schema(type=openapi.TYPE_BOOLEAN),
            'description': openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
            'coupon_discount_type': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=[choice[0] for choice in Coupon.DISCOUNT_TYPE_CHOICES]
            ),
            'discount_value': openapi.Schema(type=openapi.TYPE_NUMBER, format=openapi.FORMAT_FLOAT),
            'max_usage': openapi.Schema(type=openapi.TYPE_INTEGER),
            'max_usage_per_user': openapi.Schema(type=openapi.TYPE_INTEGER),
            'min_order_value': openapi.Schema(type=openapi.TYPE_NUMBER, format=openapi.FORMAT_FLOAT),
            'start_date_time': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME),
            'end_date_time': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME),
            'status': openapi.Schema(
                type=openapi.TYPE_STRING,
                enum=[choice[0] for choice in Coupon.STATUS_CHOICES]
            ),
        },
        required=[
            'name',
            'code',
            'coupon_discount_type',
            'discount_value',
            'max_usage_per_user',
            'start_date_time',
            'end_date_time',
            'status',
        ]
    ),
    responses={
        201: openapi.Response(description='Coupon created successfully'),
        400: openapi.Response(description='Validation error'),
        403: openapi.Response(description='Access denied'),
    },
    tags=['Coupons']
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@admin_required()
def admin_coupons(request):
    """
    Admin endpoint for listing and creating coupons.
    """
    if request.method == 'GET':
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status')
        
        coupons = Coupon.objects.all().order_by('-created_at')
        
        if search:
            coupons = coupons.filter(
                Q(name__icontains=search) | Q(code__icontains=search)
            )
        
        if status_filter:
            coupons = coupons.filter(status=status_filter)
        
        serializer = CouponSerializer(coupons, many=True)
        return Response({
            'coupons': serializer.data,
            'total': coupons.count(),
        })
    
    # POST - create coupon
    serializer = CouponSerializer(data=request.data)
    if serializer.is_valid():
        coupon = serializer.save(created_by=request.user, updated_by=request.user)
        return Response({
            'message': 'Coupon created successfully',
            'coupon': CouponSerializer(coupon).data,
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'error': 'Validation error',
        'details': serializer.errors,
    }, status=status.HTTP_400_BAD_REQUEST)



@swagger_auto_schema(
    method='get',
    operation_summary='Get Available Coupons',
    operation_description='Get all active coupons available for users.',
    responses={
        200: openapi.Response(
            description='Available coupons retrieved successfully',
            examples={
                'application/json': {
                    'coupons': [
                        {
                            'id': 1,
                            'code': 'SAVE10',
                            'description': '10% off on all purchases',
                            'discount_type': 'percentage',
                            'discount_value': 10.0,
                            'min_order_amount': 100.0,
                            'max_discount': 50.0,
                            'usage_limit': 100,
                            'used_count': 25,
                            'start_date_time': '2024-01-01T00:00:00Z',
                            'end_date_time': '2024-12-31T23:59:59Z'
                        }
                    ],
                    'total_coupons': 1
                }
            }
        )
    },
    tags=['Coupons']
)

@api_view(['GET'])
@permission_classes([AllowAny])
def available_coupons(request):
    """
    Get all available coupons for users.
    """
    current_time = timezone.now()
    
    coupons = Coupon.objects.filter(
        status='active',
        start_date_time__lte=current_time,
        end_date_time__gte=current_time
    ).order_by('-created_at')
    
    return Response({
        'coupons': CouponSerializer(coupons, many=True).data,
        'total_coupons': coupons.count()
    })


@swagger_auto_schema(
    method='post',
    operation_summary='Validate Coupon Code',
    operation_description='Validate a coupon code for a user and calculate discount.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'coupon_code': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Coupon code to validate',
                example='SAVE10'
            ),
            'order_amount': openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description='Order amount for validation',
                example=150.00
            )
        },
        required=['coupon_code']
    ),
    responses={
        200: openapi.Response(
            description='Coupon validated successfully',
            examples={
                'application/json': {
                    'valid': True,
                    'coupon': {
                        'id': 1,
                        'code': 'SAVE10',
                        'description': '10% off on all purchases',
                        'discount_type': 'percentage',
                        'discount_value': 10.0,
                        'discount_amount': 15.0,
                        'final_amount': 135.0
                    }
                }
            }
        ),
        400: openapi.Response(description='Bad request - invalid coupon or validation failed'),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Coupons']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_coupon(request):
    """
    Validate a coupon code for a user.
    """
    coupon_code = request.data.get('coupon_code')
    order_amount = request.data.get('order_amount', 0)
    
    if not coupon_code:
        return Response({
            'error': 'Coupon code is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        coupon = Coupon.objects.get(
            code__iexact=coupon_code,
            status='active',
            start_date_time__lte=timezone.now(),
            end_date_time__gte=timezone.now()
        )
    except Coupon.DoesNotExist:
        return Response({
            'error': 'Invalid or expired coupon code'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check minimum order value
    if float(order_amount) < float(coupon.min_order_value):
        return Response({
            'error': f'Minimum order value of {coupon.min_order_value} required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check max usage
    if coupon.max_usage > 0:
        total_usages = CouponUsage.objects.filter(coupon=coupon).count()
        if total_usages >= coupon.max_usage:
            return Response({
                'error': 'Coupon usage limit exceeded'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check max usage per user
    user_usages = CouponUsage.objects.filter(
        coupon=coupon,
        created_by=request.user
    ).count()
    
    if user_usages >= coupon.max_usage_per_user:
        return Response({
            'error': 'You have already used this coupon maximum times'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Calculate discount
    if coupon.coupon_discount_type == 'flat':
        discount_amount = float(coupon.discount_value)
    else:  # percentage
        discount_amount = (float(order_amount) * float(coupon.discount_value)) / 100
    
    # Ensure discount doesn't exceed order amount
    discount_amount = min(discount_amount, float(order_amount))
    
    return Response({
        'valid': True,
        'coupon': CouponSerializer(coupon).data,
        'discount_amount': discount_amount,
        'final_amount': float(order_amount) - discount_amount
    })


@swagger_auto_schema(
    method='post',
    operation_summary='Apply Coupon',
    operation_description='Apply Coupon endpoint',
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
def apply_coupon(request):
    """
    Apply a coupon to an order.
    """
    coupon_code = request.data.get('coupon_code')
    order_id = request.data.get('order_id')
    order_amount = request.data.get('order_amount', 0)
    
    if not all([coupon_code, order_id]):
        return Response({
            'error': 'Coupon code and order ID are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        coupon = Coupon.objects.get(
            code__iexact=coupon_code,
            status='active',
            start_date_time__lte=timezone.now(),
            end_date_time__gte=timezone.now()
        )
    except Coupon.DoesNotExist:
        return Response({
            'error': 'Invalid or expired coupon code'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if coupon is already applied to this order
    try:
        from Orders.models import Order
        order = Order.objects.get(id=order_id, created_by=request.user)
        
        if CouponUsage.objects.filter(coupon=coupon, order=order).exists():
            return Response({
                'error': 'Coupon already applied to this order'
            }, status=status.HTTP_400_BAD_REQUEST)
    except Order.DoesNotExist:
        return Response({
            'error': 'Order not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Validate coupon (reuse validation logic)
    validation_response = validate_coupon(request)
    if validation_response.status_code != 200:
        return validation_response
    
    # Calculate discount
    if coupon.coupon_discount_type == 'flat':
        discount_amount = float(coupon.discount_value)
    else:  # percentage
        discount_amount = (float(order_amount) * float(coupon.discount_value)) / 100
    
    discount_amount = min(discount_amount, float(order_amount))
    
    # Create coupon usage
    coupon_usage = CouponUsage.objects.create(
        coupon=coupon,
        order=order,
        discount_applied=discount_amount,
        order_amount=order_amount,
        created_by=request.user
    )
    
    # Update order with discount
    order.total_amount = float(order_amount) - discount_amount
    order.save()
    
    return Response({
        'message': 'Coupon applied successfully',
        'coupon_usage': CouponUsageSerializer(coupon_usage).data,
        'discount_applied': discount_amount,
        'final_amount': order.total_amount
    }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='get',
    operation_summary='My Coupon Usage',
    operation_description='My Coupon Usage endpoint',
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
def my_coupon_usage(request):
    """
    Get user's coupon usage history.
    """
    usages = CouponUsage.objects.filter(
        created_by=request.user
    ).order_by('-created_at')
    
    return Response({
        'coupon_usages': CouponUsageSerializer(usages, many=True).data,
        'total_usages': usages.count()
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Coupon Details',
    operation_description='Coupon Details endpoint',
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
def coupon_details(request, coupon_id):
    """
    Get detailed information about a specific coupon.
    """
    try:
        coupon = Coupon.objects.get(id=coupon_id)
        
        # Get usage statistics
        total_usages = CouponUsage.objects.filter(coupon=coupon).count()
        user_usages = CouponUsage.objects.filter(
            coupon=coupon,
            created_by=request.user
        ).count()
        
        return Response({
            'coupon': CouponSerializer(coupon).data,
            'usage_stats': {
                'total_usages': total_usages,
                'user_usages': user_usages,
                'remaining_usages': max(0, coupon.max_usage - total_usages) if coupon.max_usage > 0 else 'Unlimited',
                'user_remaining_usages': max(0, coupon.max_usage_per_user - user_usages)
            }
        })
    except Coupon.DoesNotExist:
        return Response({
            'error': 'Coupon not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='get',
    operation_summary='Search Coupons',
    operation_description='Search Coupons endpoint',
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
@permission_classes([AllowAny])
def search_coupons(request):
    """
    Search coupons by name or code.
    """
    search_query = request.GET.get('search', '')
    plan_type = request.GET.get('plan_type')
    
    coupons = Coupon.objects.filter(
        status='active',
        start_date_time__lte=timezone.now(),
        end_date_time__gte=timezone.now()
    )
    
    if search_query:
        coupons = coupons.filter(
            Q(name__icontains=search_query) | 
            Q(code__icontains=search_query)
        )
    
    if plan_type:
        if plan_type == 'base':
            coupons = coupons.filter(applied_to_base=True)
        elif plan_type == 'prime':
            coupons = coupons.filter(applied_to_prime=True)
        elif plan_type == 'premium':
            coupons = coupons.filter(applied_to_premium=True)
    
    coupons = coupons.order_by('-created_at')
    
    return Response({
        'coupons': CouponSerializer(coupons, many=True).data,
        'total_coupons': coupons.count()
    })


@swagger_auto_schema(
    method='post',
    operation_summary='Remove Coupon',
    operation_description='Remove Coupon endpoint',
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
def remove_coupon(request):
    """
    Remove a coupon from an order.
    """
    order_id = request.data.get('order_id')
    
    if not order_id:
        return Response({
            'error': 'Order ID is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from Orders.models import Order
        order = Order.objects.get(id=order_id, created_by=request.user)
        
        # Find coupon usage for this order
        coupon_usage = CouponUsage.objects.filter(
            order=order,
            created_by=request.user
        ).first()
        
        if not coupon_usage:
            return Response({
                'error': 'No coupon applied to this order'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Remove coupon usage
        coupon_usage.delete()
        
        # Recalculate order total (this would need to be implemented based on your order logic)
        # For now, we'll just return success
        
        return Response({
            'message': 'Coupon removed successfully',
            'order_id': order_id
        })
    
    except Order.DoesNotExist:
        return Response({
            'error': 'Order not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='get',
    operation_summary='Featured Coupons',
    operation_description='Featured Coupons endpoint',
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
@permission_classes([AllowAny])
def featured_coupons(request):
    """
    Get featured/trending coupons.
    """
    # Get coupons with most usage
    featured_coupons = Coupon.objects.filter(
        status='active',
        start_date_time__lte=timezone.now(),
        end_date_time__gte=timezone.now()
    ).annotate(
        usage_count=Count('usages')
    ).order_by('-usage_count', '-created_at')[:10]
    
    return Response({
        'featured_coupons': CouponSerializer(featured_coupons, many=True).data,
        'total_featured': featured_coupons.count()
    })
