from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Sum
from django.utils import timezone
from .models import Cart, Order, OrderTransaction, OrderComment, OrderCommentReadReceipt, Invoice
from .serializers import (
    CartSerializer, OrderSerializer, OrderTransactionSerializer,
    OrderCommentSerializer, OrderCommentCreateSerializer, OrderCommentListSerializer,
    InvoiceSerializer
)
from Catalog.models import Product, CollectionBundle
from Plans.models import Plan, Subscription
from Coupons.models import Coupon, CouponUsage


def check_user_has_purchased_product(user, product_id):
    """
    Check if a user has purchased a specific product.
    Returns True if the product is in a successful order (cart or subscription type).
    Also checks if product is free (price=0 or product_plan_type='free').
    """
    try:
        product = Product.objects.get(id=product_id, status='active')
        
        # Check if product is free
        from decimal import Decimal
        is_free = False
        if product.product_plan_type == 'free':
            is_free = True
        elif product.price is None or product.price == Decimal('0.00') or product.price == 0:
            is_free = True
        
        # If product is free, user has access (they can download it)
        if is_free:
            return True
        
        # Check if user has purchased this product in a successful order
        successful_orders = Order.objects.filter(
            created_by=user,
            status='success',
            order_type__in=['cart', 'subscription']
        ).exclude(product_ids__isnull=True).exclude(product_ids='')
        
        for order in successful_orders:
            if order.product_ids:
                try:
                    product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
                    if product_id in product_ids:
                        return True
                except (ValueError, AttributeError):
                    continue
        
        return False
    except Product.DoesNotExist:
        return False


@swagger_auto_schema(
    method='get',
    operation_summary='Get Cart Items',
    operation_description='Get all items in user cart.',
    responses={
        200: openapi.Response(
            description='Cart items retrieved successfully',
            examples={
                'application/json': {
                    'cart_items': [
                        {
                            'id': 1,
                            'product_id': 1,
                            'product_title': 'Sample Design',
                            'product_price': 29.99,
                            'cart_type': 'cart',
                            'created_at': '2024-01-01T00:00:00Z'
                        }
                    ],
                    'total_items': 1
                }
            }
        ),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Orders']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cart_list(request):
    """
    Get user's cart items.
    """
    cart_items = Cart.objects.filter(
        created_by=request.user,
        cart_type='cart'
    ).select_related('product')
    
    return Response({
        'cart_items': CartSerializer(cart_items, many=True).data,
        'total_items': cart_items.count()
    })


@swagger_auto_schema(
    method='post',
    operation_summary='Add Product to Cart',
    operation_description='Add a product to user cart or wishlist.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'product_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Product ID to add to cart',
                example=1
            ),
            'cart_type': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Type of cart',
                example='cart',
                enum=['cart', 'wishlist']
            )
        },
        required=['product_id']
    ),
    responses={
        201: openapi.Response(
            description='Product added to cart successfully',
            examples={
                'application/json': {
                    'message': 'Product added to cart successfully',
                    'cart_item': {
                        'id': 1,
                        'product_id': 1,
                        'product_title': 'Sample Design',
                        'cart_type': 'cart',
                        'created_at': '2024-01-01T00:00:00Z'
                    }
                }
            }
        ),
        400: openapi.Response(description='Bad request - product already in cart or validation errors'),
        404: openapi.Response(description='Product not found'),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Orders']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_cart(request):
    """
    Add product to cart.
    """
    product_id = request.data.get('product_id')
    cart_type = request.data.get('cart_type', 'cart')  # 'cart' or 'wishlist'
    
    try:
        product = Product.objects.get(id=product_id, status='active')
    except Product.DoesNotExist:
        return Response({
            'error': 'Product not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if item already exists in cart
    existing_item = Cart.objects.filter(
        product=product,
        created_by=request.user,
        cart_type=cart_type
    ).first()
    
    if existing_item:
        return Response({
            'message': 'Item already in cart',
            'cart_item': CartSerializer(existing_item).data
        })
    
    # If adding to cart (not wishlist), check if user has already purchased this product
    if cart_type == 'cart':
        has_purchased = check_user_has_purchased_product(request.user, product_id)
        if has_purchased:
            return Response({
                'error': 'You have already purchased this product. You can find it in your Downloads.',
                'already_purchased': True,
                'product_id': product_id
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create new cart item
    cart_item = Cart.objects.create(
        product=product,
        cart_type=cart_type,
        created_by=request.user
    )
    
    return Response({
        'message': 'Item added to cart successfully',
        'cart_item': CartSerializer(cart_item).data
    }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='delete',
    operation_summary='Remove From Cart',
    operation_description='Remove From Cart endpoint',
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
def remove_from_cart(request, cart_item_id):
    """
    Remove item from cart.
    """
    try:
        cart_item = Cart.objects.get(
            id=cart_item_id,
            created_by=request.user
        )
        cart_item.delete()
        
        return Response({
            'message': 'Item removed from cart successfully'
        })
    except Cart.DoesNotExist:
        return Response({
            'error': 'Cart item not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='post',
    operation_summary='Move To Wishlist',
    operation_description='Move To Wishlist endpoint',
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
def move_to_wishlist(request, cart_item_id):
    """
    Move item from cart to wishlist.
    """
    try:
        cart_item = Cart.objects.get(
            id=cart_item_id,
            created_by=request.user,
            cart_type='cart'
        )
        cart_item.cart_type = 'wishlist'
        cart_item.save()
        
        return Response({
            'message': 'Item moved to wishlist successfully',
            'cart_item': CartSerializer(cart_item).data
        })
    except Cart.DoesNotExist:
        return Response({
            'error': 'Cart item not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='post',
    operation_summary='Move To Cart',
    operation_description='Move To Cart endpoint',
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
def move_to_cart(request, cart_item_id):
    """
    Move item from wishlist to cart.
    """
    try:
        cart_item = Cart.objects.get(
            id=cart_item_id,
            created_by=request.user,
            cart_type='wishlist'
        )
        
        # Check if user has already purchased this product
        has_purchased = check_user_has_purchased_product(request.user, cart_item.product_id)
        if has_purchased:
            return Response({
                'error': 'You have already purchased this product. You can find it in your Downloads.',
                'already_purchased': True,
                'product_id': cart_item.product_id
            }, status=status.HTTP_400_BAD_REQUEST)
        
        cart_item.cart_type = 'cart'
        cart_item.save()
        
        return Response({
            'message': 'Item moved to cart successfully',
            'cart_item': CartSerializer(cart_item).data
        })
    except Cart.DoesNotExist:
        return Response({
            'error': 'Wishlist item not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='get',
    operation_summary='Wishlist List',
    operation_description='Wishlist List endpoint',
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
def wishlist_list(request):
    """
    Get user's wishlist items with purchase status.
    """
    wishlist_items = Cart.objects.filter(
        created_by=request.user,
        cart_type='wishlist'
    ).select_related('product')
    
    # Serialize items and add purchase status
    wishlist_data = CartSerializer(wishlist_items, many=True).data
    
    # Add purchase status to each item
    for item in wishlist_data:
        product_id = item.get('product', {}).get('id') if isinstance(item.get('product'), dict) else None
        if not product_id and 'product_id' in item:
            product_id = item['product_id']
        
        if product_id:
            item['is_purchased'] = check_user_has_purchased_product(request.user, product_id)
        else:
            item['is_purchased'] = False
    
    return Response({
        'wishlist_items': wishlist_data,
        'total_items': wishlist_items.count()
    })


@swagger_auto_schema(
    method='post',
    operation_summary='Purchase Cart Items',
    operation_description='Purchase all items in user cart and create order.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'payment_method': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Payment method',
                example='razorpay',
                enum=['razorpay', 'wallet']
            ),
            'address_id': openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description='Shipping address ID (optional - not required for digital products)',
                example=1
            ),
            'coupon_code': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Coupon code for discount',
                example='SAVE10'
            )
        },
        required=['payment_method']
    ),
    responses={
        201: openapi.Response(
            description='Order created successfully',
            examples={
                'application/json': {
                    'message': 'Order created successfully',
                    'order': {
                        'id': 1,
                        'total_amount': 99.99,
                        'status': 'pending',
                        'created_at': '2024-01-01T00:00:00Z'
                    },
                    'payment_url': 'https://razorpay.com/pay/...'
                }
            }
        ),
        400: openapi.Response(description='Bad request - cart empty or validation errors'),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Orders']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_cart(request):
    """
    Purchase items in cart. Check for active subscription and handle payment.
    This endpoint is kept for backward compatibility but is deprecated.
    Use create_order + create_payment_order + capture_payment flow instead.
    """
    cart_items = Cart.objects.filter(
        created_by=request.user,
        cart_type='cart'
    )
    
    if not cart_items.exists():
        return Response({
            'error': 'Cart is empty'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check for active subscription
    active_subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).first()
    
    total_amount = 0
    items_to_purchase = []
    
    for item in cart_items:
        if item.product.price:
            total_amount += float(item.product.price)
        items_to_purchase.append(item)
    
    # Handle coupon if provided
    coupon_code = request.data.get('coupon_code')
    discount_amount = 0
    coupon = None
    
    if coupon_code:
        try:
            coupon = Coupon.objects.get(
                code__iexact=coupon_code,
                status='active',
                start_date_time__lte=timezone.now(),
                end_date_time__gte=timezone.now()
            )
            
            # Check minimum order value
            if float(total_amount) < float(coupon.min_order_value):
                return Response({
                    'error': f'Minimum order value of {coupon.min_order_value} required for this coupon'
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
                discount_amount = (float(total_amount) * float(coupon.discount_value)) / 100
            
            # Ensure discount doesn't exceed order amount
            discount_amount = min(discount_amount, float(total_amount))
            
        except Coupon.DoesNotExist:
            return Response({
                'error': 'Invalid or expired coupon code'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Apply discount to total
    final_amount = float(total_amount) - discount_amount
    
    # Create order first (before payment processing)
    # Get product IDs from cart items
    product_ids = ','.join([str(item.product_id) for item in items_to_purchase])
    number_of_products = len(items_to_purchase)
    
    # Determine order type and status based on subscription
    free_downloads_used = 0
    if active_subscription:
        # Check if user has enough free downloads
        remaining_free = active_subscription.get_remaining_free_downloads()
        
        if remaining_free >= number_of_products:
            # User has enough free downloads - use them
            try:
                active_subscription.use_free_downloads(number_of_products)
                free_downloads_used = number_of_products
                final_amount = 0
                order_status = 'success'
                order_type = 'subscription'
            except ValueError as e:
                return Response({
                    'error': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Not enough free downloads - apply plan discount instead
            # Apply plan discount if available
            plan_discount = 0.0
            if active_subscription.plan and hasattr(active_subscription.plan, 'discount'):
                plan_discount = float(active_subscription.plan.discount) if active_subscription.plan.discount else 0.0
            
            if plan_discount > 0:
                discount_from_plan = (final_amount * plan_discount) / 100
                final_amount = final_amount - discount_from_plan
            
            order_status = 'pending'
            order_type = 'cart'
    else:
        # Payment will be processed via Razorpay, order starts as pending
        order_status = 'pending'
        order_type = 'cart'
    
    # Create order
    order = Order.objects.create(
        order_type=order_type,
        product_ids=product_ids,
        total_amount=final_amount,
        status=order_status,
        subscription=active_subscription if (active_subscription and free_downloads_used > 0) else None,
        created_by=request.user
    )
    
    # Create coupon usage if coupon was applied
    if coupon and discount_amount > 0:
        CouponUsage.objects.create(
            coupon=coupon,
            order=order,
            discount_applied=discount_amount,
            order_amount=total_amount,
            created_by=request.user
        )
    
    # If successful (free with subscription), remove items from cart
    if order_status == 'success':
        cart_items.delete()
        # Products are now available in downloads (via order_type='subscription' in my_downloads)
    
    return Response({
        'message': 'Purchase completed successfully',
        'order': OrderSerializer(order).data,
        'order_id': order.id,  # Return order_id so frontend can associate with payment
        'total_amount': final_amount,
        'original_amount': total_amount,
        'discount_applied': discount_amount,
        'free_purchase': bool(free_downloads_used > 0),
        'free_downloads_used': free_downloads_used,
        'remaining_free_downloads': active_subscription.get_remaining_free_downloads() if active_subscription else 0
    })
    
    return Response({
        'message': 'Purchase completed successfully',
        'order': OrderSerializer(order).data,
        'order_id': order.id,  # Return order_id so frontend can associate with payment
        'total_amount': final_amount,
        'original_amount': total_amount,
        'discount_applied': discount_amount,
        'free_purchase': bool(active_subscription)
    })


@swagger_auto_schema(
    method='post',
    operation_summary='Create Order',
    operation_description='Create a new order from cart items. Returns order_id for payment processing.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'product_ids': openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                description='List of product IDs',
                example=[1, 2, 3]
            ),
            'total_amount': openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description='Total order amount',
                example=99.99
            ),
            'coupon_code': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Coupon code for discount',
                example='SAVE10'
            )
        },
        required=['product_ids', 'total_amount']
    ),
    responses={
        201: openapi.Response(description='Order created successfully'),
        400: openapi.Response(description='Bad request - validation errors'),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Orders']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """
    Create a new order from product IDs. This is called before payment processing.
    Now supports using free downloads from subscription.
    """
    product_ids = request.data.get('product_ids', [])
    total_amount = request.data.get('total_amount')
    coupon_code = request.data.get('coupon_code')
    use_free_downloads = request.data.get('use_free_downloads', False)  # New parameter
    
    if not product_ids or not isinstance(product_ids, list):
        return Response({
            'error': 'product_ids is required and must be a list'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not total_amount:
        return Response({
            'error': 'total_amount is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate products exist
    try:
        # Convert product_ids to integers if they're strings
        product_ids = [int(pid) for pid in product_ids]
        
        products = Product.objects.filter(id__in=product_ids, status='active')
        found_product_ids = set(products.values_list('id', flat=True))
        requested_product_ids = set(product_ids)
        missing_product_ids = requested_product_ids - found_product_ids
        
        if missing_product_ids:
            # Check if products exist but are inactive
            inactive_products = Product.objects.filter(id__in=missing_product_ids, status='inactive')
            inactive_ids = set(inactive_products.values_list('id', flat=True))
            not_found_ids = missing_product_ids - inactive_ids
            
            error_details = []
            if not_found_ids:
                error_details.append(f"Products not found: {sorted(not_found_ids)}")
            if inactive_ids:
                error_details.append(f"Inactive products: {sorted(inactive_ids)}")
            
            return Response({
                'error': 'One or more products not found or inactive',
                'details': '; '.join(error_details) if error_details else f'Missing product IDs: {sorted(missing_product_ids)}'
            }, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError) as e:
        return Response({
            'error': f'Invalid product_ids format: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'error': f'Error validating products: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Calculate total from products
    calculated_total = sum([float(p.price) if p.price else 0 for p in products])
    number_of_products = len(products)
    
    # Check for active subscription
    active_subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).select_related('plan').first()
    
    # Handle free downloads - calculate but don't decrement until payment succeeds
    free_downloads_used = 0
    if active_subscription:
        remaining_free = active_subscription.get_remaining_free_downloads()
        
        # Check monthly limit for annual plans
        if active_subscription.plan.plan_duration == 'annually':
            remaining_monthly = active_subscription.get_remaining_monthly_downloads()
            monthly_limit = active_subscription.get_monthly_download_limit()
            current_period_used = active_subscription.get_current_period_downloads_used()
            period_start, period_end = active_subscription.get_current_settlement_period()
            
            if use_free_downloads:
                # Check monthly limit
                if remaining_monthly is not None and remaining_monthly < number_of_products:
                    return Response({
                        'error': f'Monthly download limit reached. You have used {current_period_used} downloads this month (limit: {monthly_limit}). '
                                f'You can download {remaining_monthly} more design(s) this month. Next period starts on {period_end.strftime("%B %d, %Y")}.',
                        'remaining_free_downloads': remaining_free,
                        'remaining_monthly_downloads': remaining_monthly,
                        'current_period_used': current_period_used,
                        'monthly_limit': monthly_limit,
                        'next_period_reset_date': period_end.strftime('%Y-%m-%d') if period_end else None,
                        'requested_count': number_of_products
                    }, status=status.HTTP_400_BAD_REQUEST)
        
        if use_free_downloads:
            # Explicitly requested - must have enough for all
            if remaining_free >= number_of_products:
                # Also check monthly limit for annual plans
                if active_subscription.plan.plan_duration == 'annually':
                    if remaining_monthly is not None and remaining_monthly < number_of_products:
                        return Response({
                            'error': f'Monthly download limit reached. You have used {current_period_used} downloads this month (limit: {monthly_limit}). '
                                    f'You can download {remaining_monthly} more design(s) this month. Next period starts on {period_end.strftime("%B %d, %Y")}.',
                            'remaining_free_downloads': remaining_free,
                            'remaining_monthly_downloads': remaining_monthly,
                            'current_period_used': current_period_used,
                            'monthly_limit': monthly_limit,
                            'next_period_reset_date': period_end.strftime('%Y-%m-%d') if period_end else None,
                            'requested_count': number_of_products
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                # Don't decrement yet - just store for later (decremented on payment success)
                free_downloads_used = number_of_products
                final_amount = 0
                order_status = 'success'
                order_type = 'subscription'
            else:
                return Response({
                    'error': f'Not enough free downloads. You have {remaining_free} remaining, but need {number_of_products}.',
                    'remaining_free_downloads': remaining_free,
                    'requested_count': number_of_products
                }, status=status.HTTP_400_BAD_REQUEST)
        elif remaining_free > 0:
            # Partial free downloads available - calculate how many will be used
            free_downloads_to_use = min(remaining_free, number_of_products)
            
            # For annual plans, also respect monthly limit
            if active_subscription.plan.plan_duration == 'annually':
                remaining_monthly = active_subscription.get_remaining_monthly_downloads()
                if remaining_monthly is not None:
                    free_downloads_to_use = min(free_downloads_to_use, remaining_monthly)
            
            # Don't decrement yet - just store for later (decremented on payment success)
            free_downloads_used = free_downloads_to_use
            
            # Use the total_amount from frontend (already calculated correctly by cart_summary)
            # If not provided, calculate based on paid items only
            if total_amount is not None:
                final_amount = float(total_amount)
            else:
                # Calculate amount for paid items only
                paid_items_count = number_of_products - free_downloads_used
                if paid_items_count > 0:
                    # Calculate price for paid items proportionally
                    paid_items_amount = calculated_total * (paid_items_count / number_of_products) if number_of_products > 0 else 0
                    
                    # Apply plan discount to paid items only
                    plan_discount = 0.0
                    if active_subscription.plan and hasattr(active_subscription.plan, 'discount'):
                        plan_discount = float(active_subscription.plan.discount) if active_subscription.plan.discount else 0.0
                    
                    if plan_discount > 0:
                        discount_from_plan = (paid_items_amount * plan_discount) / 100
                        paid_items_amount = paid_items_amount - discount_from_plan
                    
                    final_amount = paid_items_amount
                else:
                    # All items are free
                    final_amount = 0
                    order_status = 'success'
                    order_type = 'subscription'
            
            order_type = 'cart'
            order_status = 'pending'
        else:
            # No free downloads available - regular checkout with plan discount
            plan_discount = 0.0
            if active_subscription.plan and hasattr(active_subscription.plan, 'discount'):
                plan_discount = float(active_subscription.plan.discount) if active_subscription.plan.discount else 0.0
            
            # Apply plan discount first
            if plan_discount > 0:
                discount_from_plan = (calculated_total * plan_discount) / 100
                calculated_total = calculated_total - discount_from_plan
            
            # Use the total_amount from frontend if provided, otherwise use calculated_total
            final_amount = float(total_amount) if total_amount is not None else calculated_total
            order_type = 'cart'
            order_status = 'pending'
    elif use_free_downloads and not active_subscription:
        return Response({
            'error': 'No active subscription found. Cannot use free downloads.'
        }, status=status.HTTP_400_BAD_REQUEST)
    else:
        # No subscription - regular checkout
        # Use the total_amount from frontend if provided, otherwise use calculated_total
        final_amount = float(total_amount) if total_amount is not None else calculated_total
        order_type = 'cart'
        order_status = 'pending'
    
    # Handle coupon if provided (only if not already using free downloads for all items)
    discount_amount = 0
    coupon = None
    
    if coupon_code:
        # Don't apply coupon if order is completely free
        if final_amount > 0:
            try:
                coupon = Coupon.objects.get(
                    code__iexact=coupon_code,
                    status='active',
                    start_date_time__lte=timezone.now(),
                    end_date_time__gte=timezone.now()
                )
                
                # For coupon validation, use calculated_total (original amount before free downloads)
                coupon_base_amount = calculated_total
                
                # Check minimum order value
                if float(coupon_base_amount) < float(coupon.min_order_value):
                    return Response({
                        'error': f'Minimum order value of {coupon.min_order_value} required for this coupon'
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
                
                # If total_amount was provided from frontend, it already includes coupon discount
                # Calculate discount for CouponUsage record (for record-keeping)
                if total_amount is not None:
                    # Frontend already applied coupon, estimate discount for CouponUsage record
                    # For flat coupons, discount is the coupon value
                    # For percentage coupons, estimate based on the amount that would be paid before coupon
                    # Since we don't have the exact pre-coupon amount, we'll use an approximation
                    if coupon.coupon_discount_type == 'flat':
                        discount_amount = float(coupon.discount_value)
                    else:  # percentage
                        # Estimate: if final_amount is after coupon, reverse calculate
                        # final_amount = pre_coupon_amount * (1 - discount_percent/100)
                        # pre_coupon_amount = final_amount / (1 - discount_percent/100)
                        # discount = pre_coupon_amount - final_amount
                        discount_percent = float(coupon.discount_value) / 100
                        if discount_percent < 1:  # Avoid division by zero
                            estimated_pre_coupon = float(final_amount) / (1 - discount_percent)
                            discount_amount = estimated_pre_coupon - float(final_amount)
                        else:
                            discount_amount = 0
                    # Don't modify final_amount - it's already correct from frontend
                else:
                    # Calculate and apply coupon discount
                    if coupon.coupon_discount_type == 'flat':
                        discount_amount = float(coupon.discount_value)
                    else:  # percentage
                        discount_amount = (float(final_amount) * float(coupon.discount_value)) / 100
                    
                    # Ensure discount doesn't exceed final amount
                    discount_amount = min(discount_amount, float(final_amount))
                    
                    # Apply coupon discount to final amount
                    final_amount = float(final_amount) - discount_amount
                
            except Coupon.DoesNotExist:
                return Response({
                    'error': 'Invalid or expired coupon code'
                }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create order
    product_ids_str = ','.join([str(pid) for pid in product_ids])
    order = Order.objects.create(
        order_type=order_type,
        product_ids=product_ids_str,
        total_amount=final_amount,
        status=order_status,
        subscription=active_subscription if (active_subscription and free_downloads_used > 0) else None,
        free_downloads_used=free_downloads_used,  # Store count - will be decremented on payment success
        created_by=request.user
    )
    
    # Create coupon usage if coupon was applied
    if coupon and discount_amount > 0:
        CouponUsage.objects.create(
            coupon=coupon,
            order=order,
            discount_applied=discount_amount,
            order_amount=calculated_total,
            created_by=request.user
        )
    
    # If successful (free with subscription), remove items from cart
    if order_status == 'success':
        Cart.objects.filter(
            created_by=request.user,
            cart_type='cart',
            product_id__in=product_ids
        ).delete()
    
    return Response({
        'message': 'Order created successfully',
        'order_id': order.id,
        'order': OrderSerializer(order).data,
        'total_amount': final_amount,
        'original_amount': sum([float(p.price) if p.price else 0 for p in products]),
        'discount_applied': discount_amount if 'discount_amount' in locals() else 0,
        'free_downloads_used': free_downloads_used,
        'free_purchase': bool(free_downloads_used > 0),
        'remaining_free_downloads': active_subscription.get_remaining_free_downloads() if active_subscription else 0
    }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='get',
    operation_summary='Check Free Downloads Availability',
    operation_description='Check if user has free downloads and mock PDF downloads available from their subscription.',
    responses={
        200: openapi.Response(
            description='Free downloads availability checked successfully',
            examples={
                'application/json': {
                    'has_subscription': True,
                    'remaining_free_downloads': 35,
                    'total_free_downloads': 40,
                    'used_free_downloads': 5,
                    'remaining_mock_pdf_downloads': 2,
                    'total_mock_pdf_downloads': 3,
                    'used_mock_pdf_downloads': 1,
                    'plan_name': 'Premium'
                }
            }
        ),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Orders']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_free_downloads_availability(request):
    """
    Check if user has free downloads and mock PDF downloads available from their active subscription.
    """
    from Plans.models import Subscription
    
    # Get active subscription
    active_subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).select_related('plan').first()
    
    if not active_subscription:
        return Response({
            'has_subscription': False,
            'remaining_free_downloads': 0,
            'total_free_downloads': 0,
            'used_free_downloads': 0,
            'remaining_mock_pdf_downloads': 0,
            'total_mock_pdf_downloads': 0,
            'used_mock_pdf_downloads': 0,
            'plan_name': None,
            'message': 'No active subscription found'
        }, status=status.HTTP_200_OK)
    
    plan = active_subscription.plan
    remaining_free = active_subscription.get_remaining_free_downloads()
    total_free = plan.no_of_free_downloads if hasattr(plan, 'no_of_free_downloads') else 0
    
    remaining_mock_pdf = active_subscription.get_remaining_mock_pdf_downloads()
    total_mock_pdf = plan.mock_pdf_count if hasattr(plan, 'mock_pdf_count') else 0
    
    # For annual plans, include monthly period information
    response_data = {
        'has_subscription': True,
        'remaining_free_downloads': remaining_free,
        'total_free_downloads': total_free,
        'used_free_downloads': active_subscription.free_downloads_used,
        'remaining_mock_pdf_downloads': remaining_mock_pdf,
        'total_mock_pdf_downloads': total_mock_pdf,
        'used_mock_pdf_downloads': active_subscription.mock_pdf_downloads_used,
        'plan_name': plan.get_plan_name_display(),
        'plan_discount': float(plan.discount) if hasattr(plan, 'discount') else 0.0,
        'plan_duration': plan.plan_duration,
        'is_annual_plan': plan.plan_duration == 'annually',
        'message': f'You have {remaining_free} free downloads and {remaining_mock_pdf} mock PDF downloads remaining'
    }
    
    # Add monthly period info for annual plans
    if plan.plan_duration == 'annually':
        period_start, period_end = active_subscription.get_current_settlement_period()
        current_period_used = active_subscription.get_current_period_downloads_used()
        monthly_limit = active_subscription.get_monthly_download_limit()
        remaining_monthly = active_subscription.get_remaining_monthly_downloads()
        
        response_data.update({
            'current_period_downloads_used': current_period_used,
            'current_period_downloads_allowed': monthly_limit,
            'current_period_remaining': remaining_monthly,
            'current_period_start': period_start.strftime('%Y-%m-%d') if period_start else None,
            'current_period_end': period_end.strftime('%Y-%m-%d') if period_end else None,
            'next_period_reset_date': period_end.strftime('%Y-%m-%d') if period_end else None,
        })
    else:
        # For monthly plans, set monthly fields to None
        response_data.update({
            'current_period_downloads_used': None,
            'current_period_downloads_allowed': None,
            'current_period_remaining': None,
            'current_period_start': None,
            'current_period_end': None,
            'next_period_reset_date': None,
        })
    
    return Response(response_data, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    operation_summary='My Downloads',
    operation_description='My Downloads endpoint',
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
def my_downloads(request):
    """
    Get user's downloadable products from successful orders.
    Returns products that were purchased in cart orders (order_type='cart', status='success')
    or subscription orders (order_type='subscription', status='success').
    """
    from Catalog.models import Product
    from Catalog.serializers import ProductSerializer
    from django.db.models import Q
    
    # Get filter parameter
    filter_type = request.GET.get('filter', 'all')  # 'all', 'paid'
    
    # Get all successful orders (both cart and subscription) for this user, sorted by latest first
    successful_orders = Order.objects.filter(
        created_by=request.user,
        status='success',
        order_type__in=['cart', 'subscription']
    ).exclude(product_ids__isnull=True).exclude(product_ids='').order_by('-created_at')
    
    # Collect product IDs with their purchase date (order created_at)
    # Use a dict to track the latest purchase date for each product
    product_purchase_dates = {}  # {product_id: order_created_at}
    product_ids_list = []  # Maintain order of products (latest first)
    
    # Count ALL items across all orders (for total_downloads)
    total_items_count = 0
    
    for order in successful_orders:
        if order.product_ids:
            try:
                # Parse comma-separated product IDs
                ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
                # Count all items in this order
                total_items_count += len(ids)
                for product_id in ids:
                    # Always update purchase date to the latest order date
                    # If product is already in the list, we'll re-sort later
                    if product_id not in product_purchase_dates:
                        # New product - add to list
                        product_purchase_dates[product_id] = order.created_at
                        product_ids_list.append(product_id)
                    else:
                        # Product already exists - update to latest purchase date if this order is newer
                        if order.created_at > product_purchase_dates[product_id]:
                            product_purchase_dates[product_id] = order.created_at
            except (ValueError, AttributeError):
                continue
    
    if not product_ids_list:
        return Response({
            'products': [],
            'total_downloads': 0,
            'paid_downloads': 0
        })
    
    # Sort products by their latest purchase date (latest first)
    sorted_product_ids = sorted(
        product_ids_list, 
        key=lambda pid: product_purchase_dates[pid], 
        reverse=True
    )
    
    # Get products that exist and are active
    products = Product.objects.filter(
        id__in=sorted_product_ids,
        status='active'
    ).select_related('category', 'created_by')
    
    # Create a dict for quick lookup
    products_dict = {p.id: p for p in products}
    
    # Sort products by purchase date (latest first) using the sorted product IDs
    sorted_products = [products_dict[pid] for pid in sorted_product_ids if pid in products_dict]
    
    # Serialize products with request context for absolute URLs
    serializer = ProductSerializer(sorted_products, many=True, context={'request': request})
    products_data = serializer.data
    
    # Add purchase_date to each product for frontend sorting
    for product_data in products_data:
        product_id = product_data.get('id')
        if product_id and product_id in product_purchase_dates:
            product_data['purchase_date'] = product_purchase_dates[product_id].isoformat() if product_purchase_dates[product_id] else None
        else:
            product_data['purchase_date'] = None
    
    # Count paid downloads - count ALL items from paid orders (cart orders are paid, subscription orders are free)
    paid_orders = successful_orders.filter(order_type='cart')
    paid_items_count = 0
    for order in paid_orders:
        if order.product_ids:
            try:
                ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
                paid_items_count += len(ids)  # Count all items in paid orders
            except (ValueError, AttributeError):
                continue
    
    return Response({
        'products': products_data,
        'total_downloads': total_items_count,  # Total count of all items across all orders
        'paid_downloads': paid_items_count  # Total count of all items from paid orders
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Download Product Zip',
    operation_description='Download all media files for a product as a zip file. Allows download for free products (price=0 or product_plan_type=free) or products purchased in a successful cart order.',
    responses={
        200: openapi.Response(description='Zip file download'),
        400: openapi.Response(description='Bad request - product not found'),
        401: openapi.Response(description='Unauthorized - authentication required'),
        403: openapi.Response(description='Forbidden - product not purchased and not free')
    },
    tags=['Orders']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_product_zip(request, product_id):
    """
    Download all media files for a product as a zip file.
    Allows download if:
    1. Product is free (price is 0 or null, or product_plan_type is 'free')
    2. Product was purchased in a successful cart order
    """
    import zipfile
    import io
    from django.http import HttpResponse
    from MediaFiles.models import Media
    from common.relations import get_related
    from django.core.files.storage import default_storage
    from decimal import Decimal
    
    try:
        product = Product.objects.get(id=product_id, status='active')
    except Product.DoesNotExist:
        return Response({
            'error': 'Product not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if product is free
    is_free = False
    if product.product_plan_type == 'free':
        is_free = True
    elif product.price is None or product.price == Decimal('0.00') or product.price == 0:
        is_free = True
    else:
        # Check sub-products (if they exist via relations)
        # For now, we'll check the main product price
        pass
    
    # If product is free, allow direct download
    if is_free:
        # Allow download for free products
        pass
    else:
        # Verify user has purchased this product in a successful order (cart or subscription)
        successful_orders = Order.objects.filter(
            created_by=request.user,
            status='success',
            order_type__in=['cart', 'subscription']
        ).exclude(product_ids__isnull=True).exclude(product_ids='')
        
        has_access = False
        for order in successful_orders:
            if order.product_ids:
                try:
                    product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
                    if product_id in product_ids:
                        has_access = True
                        break
                except (ValueError, AttributeError):
                    continue
        
        if not has_access:
            return Response({
                'error': 'You do not have access to download this product. Please purchase it first.'
            }, status=status.HTTP_403_FORBIDDEN)
    
    # Get all media files for this product
    media_files = get_related(product, 'Product:Media', Media)
    
    if not media_files or (hasattr(media_files, 'exists') and not media_files.exists()):
        return Response({
            'error': 'No media files found for this product'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Create zip file in memory
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for media in media_files:
                if media.file:
                    try:
                        # Get file path
                        file_path = media.file.name
                        
                        # Skip AVIF files - they are only for web display, not for download
                        file_name_lower = file_path.lower()
                        if file_name_lower.endswith('.avif'):
                            continue
                        
                        # Read file from storage
                        if default_storage.exists(file_path):
                            with default_storage.open(file_path, 'rb') as storage_file:
                                file_content = storage_file.read()
                                
                                # Get original filename or use a default
                                file_name = media.file.name.split('/')[-1] if '/' in media.file.name else media.file.name
                                
                                # Add to zip with sanitized filename
                                zip_file.writestr(file_name, file_content)
                    except Exception as e:
                        continue
        
        # Prepare response
        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{product.title.replace(" ", "_")}_{product_id}.zip"'
        response['Content-Length'] = zip_buffer.tell()
        
        return response
        
    except Exception as e:
        return Response({
            'error': f'Failed to create zip file: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_summary='Order History',
    operation_description='Order History endpoint',
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
def order_history(request):
    """
    Get user's order history.
    """
    orders = Order.objects.filter(
        created_by=request.user
    ).order_by('-created_at')
    
    return Response({
        'orders': OrderSerializer(orders, many=True).data,
        'total_orders': orders.count()
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Order Detail',
    operation_description='Order Detail endpoint',
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
def order_detail(request, order_id):
    """
    Get detailed information about a specific order.
    """
    try:
        order = Order.objects.get(
            id=order_id,
            created_by=request.user
        )
        return Response({
            'order': OrderSerializer(order).data
        })
    except Order.DoesNotExist:
        return Response({
            'error': 'Order not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='post',
    operation_summary='Add Bundle To Cart',
    operation_description='Add Bundle To Cart endpoint',
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
def add_bundle_to_cart(request):
    """
    Add collection bundle to cart.
    """
    bundle_id = request.data.get('bundle_id')
    cart_type = request.data.get('cart_type', 'cart')
    
    try:
        bundle = CollectionBundle.objects.get(id=bundle_id, status='available')
    except CollectionBundle.DoesNotExist:
        return Response({
            'error': 'Bundle not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Add each product in the bundle to cart
    if bundle.product_ids:
        product_ids = [int(id) for id in bundle.product_ids.split(',') if id.strip()]
        products = Product.objects.filter(id__in=product_ids, status='active')
        
        added_items = []
        for product in products:
            # Check if already in cart
            existing_item = Cart.objects.filter(
                product=product,
                created_by=request.user,
                cart_type=cart_type
            ).first()
            
            if not existing_item:
                cart_item = Cart.objects.create(
                    product=product,
                    cart_type=cart_type,
                    created_by=request.user
                )
                added_items.append(CartSerializer(cart_item).data)
        
        return Response({
            'message': f'Bundle added to {cart_type} successfully',
            'added_items': added_items,
            'total_added': len(added_items)
        })
    
    return Response({
        'error': 'Bundle has no products'
    }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_summary='Cart Summary',
    operation_description='Cart Summary endpoint',
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
def cart_summary(request):
    """
    Get cart summary with totals and subscription info.
    """
    cart_items = Cart.objects.filter(
        created_by=request.user,
        cart_type='cart'
    ).select_related('product')
    
    # Check for active subscription
    active_subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).select_related('plan').first()
    
    total_amount = sum(float(item.product.price or 0) for item in cart_items)
    number_of_items = cart_items.count()
    
    # Initialize response data
    response_data = {
        'cart_items': CartSerializer(cart_items, many=True).data,
        'total_items': number_of_items,
        'total_amount': total_amount,
        'has_active_subscription': bool(active_subscription),
        'will_be_free': False,
        'subscription_plan': None,
        'remaining_free_downloads': 0,
        'total_free_downloads': 0,
        'plan_discount': 0.0,
        'free_items_count': 0,
        'paid_items_count': number_of_items,
        'discounted_amount': total_amount,
    }
    
    if active_subscription:
        plan = active_subscription.plan
        remaining_free = active_subscription.get_remaining_free_downloads()
        
        # Get plan discount percentage
        plan_discount = 0.0
        if plan and hasattr(plan, 'discount'):
            plan_discount = float(plan.discount) if plan.discount else 0.0
        
        # Calculate how many items can be free
        free_items_count = min(remaining_free, number_of_items)
        paid_items_count = max(0, number_of_items - remaining_free)
        
        # Check if order will be completely free
        will_be_free = remaining_free >= number_of_items
        
        # Calculate discounted amount for paid items
        if paid_items_count > 0:
            # Calculate price for paid items based on actual item prices
            # Sort items by price (or use first N items for free, rest for paid)
            # For simplicity, we'll calculate proportionally, but in a real scenario,
            # you might want to prioritize cheaper items for free downloads
            paid_items_amount = total_amount * (paid_items_count / number_of_items) if number_of_items > 0 else 0
            
            # Apply plan discount to paid items
            if plan_discount > 0:
                discount_from_plan = (paid_items_amount * plan_discount) / 100
                discounted_paid_amount = paid_items_amount - discount_from_plan
            else:
                discounted_paid_amount = paid_items_amount
            
            # Free items amount is 0
            discounted_amount = discounted_paid_amount
        else:
            # All items are free
            discounted_amount = 0
        
        response_data.update({
            'will_be_free': will_be_free,
            'subscription_plan': plan.get_plan_name_display() if plan else None,
            'remaining_free_downloads': remaining_free,
            'total_free_downloads': plan.no_of_free_downloads if (plan and hasattr(plan, 'no_of_free_downloads')) else 0,
            'plan_discount': plan_discount,
            'free_items_count': free_items_count,
            'paid_items_count': paid_items_count,
            'discounted_amount': discounted_amount,
        })
    
    return Response(response_data)


@swagger_auto_schema(
    method='get',
    operation_summary='Get Order Comments',
    operation_description='Get all comments/messages for an order. Works for all order types (cart, subscription, custom).',
    manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, description='Page number', type=openapi.TYPE_INTEGER),
        openapi.Parameter('comment_type', openapi.IN_QUERY, description='Filter by comment type', type=openapi.TYPE_STRING, enum=['customer', 'admin', 'system'])
    ],
    responses={
        200: openapi.Response(
            description='Comments retrieved successfully',
            examples={
                'application/json': {
                    'order_id': 1,
                    'order_type': 'cart',
                    'order_title': 'Order #1',
                    'comments': [],
                    'total_comments': 0
                }
            }
        ),
        404: openapi.Response(description='Order not found'),
        403: openapi.Response(description='Permission denied')
    },
    tags=['Orders']
)
@swagger_auto_schema(
    method='post',
    operation_summary='Add Order Comment',
    operation_description='Add a new comment/message to an order. Works for all order types.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'message': openapi.Schema(type=openapi.TYPE_STRING, description='Message text'),
            'comment_type': openapi.Schema(type=openapi.TYPE_STRING, enum=['customer', 'admin', 'system'], default='customer', description='Type of comment'),
            'is_internal': openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False, description='Internal comment (admin only)'),
            'media_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER), description='Media file IDs to attach')
        },
        required=['message']
    ),
    responses={
        201: openapi.Response(description='Comment added successfully'),
        400: openapi.Response(description='Bad request'),
        404: openapi.Response(description='Order not found'),
        403: openapi.Response(description='Permission denied')
    },
    tags=['Orders']
)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def order_comments(request, order_id):
    """
    Get or add comments for an order.
    Works for all order types: cart, subscription, and custom.
    """
    try:
        order = Order.objects.select_related('created_by', 'custom_order_request').get(id=order_id)
    except Order.DoesNotExist:
        return Response({
            'error': 'Order not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check permissions - user must own the order or be admin
    if order.created_by != request.user and not (request.user.is_staff or request.user.is_superuser):
        return Response({
            'error': 'You do not have permission to access this order'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        # Get comments for this order
        # Prefetch read receipts to avoid N+1 queries
        comments = OrderComment.objects.filter(order=order).select_related('created_by', 'admin_user').prefetch_related('read_receipts')
        
        # Exclude internal comments for non-admin users
        if not (request.user.is_staff or request.user.is_superuser):
            comments = comments.exclude(is_internal=True)
        
        # Filter by comment type if provided
        comment_type = request.GET.get('comment_type')
        if comment_type:
            comments = comments.filter(comment_type=comment_type)
        
        # Order chronologically for chat view (oldest first)
        comments = comments.order_by('created_at')
        
        # Get order title (for custom orders, use custom request title)
        order_title = None
        if order.order_type == 'custom' and order.custom_order_request:
            order_title = order.custom_order_request.title
        else:
            order_title = f"Order #{order.id}"
        
        serializer = OrderCommentSerializer(comments, many=True, context={'request': request})
        
        return Response({
            'order_id': order.id,
            'order_type': order.order_type,
            'order_title': order_title,
            'comments': serializer.data,
            'total_comments': comments.count()
        })
    
    elif request.method == 'POST':
        # Create a new comment
        serializer = OrderCommentCreateSerializer(data=request.data)
        if serializer.is_valid():
            comment_type = serializer.validated_data.get('comment_type', 'customer')
            is_internal = serializer.validated_data.get('is_internal', False)
            
            # Set admin fields if user is admin
            is_admin = request.user.is_staff or request.user.is_superuser
            if is_admin and comment_type == 'customer':
                comment_type = 'admin'
            
            # Only admins can create internal comments
            if is_internal and not is_admin:
                return Response({
                    'error': 'Only admins can create internal comments'
                }, status=status.HTTP_403_FORBIDDEN)
            
            comment = OrderComment.objects.create(
                order=order,
                message=serializer.validated_data['message'],
                comment_type=comment_type,
                is_internal=is_internal,
                created_by=request.user,
                is_admin_response=is_admin,
                admin_user=request.user if is_admin else None
            )
            
            # When a new comment is created, the sender has already "read" it (they wrote it)
            # So create a read receipt for the sender automatically
            # Use get_or_create to avoid duplicate key errors if called multiple times
            OrderCommentReadReceipt.objects.get_or_create(
                comment=comment,
                user=request.user
            )
            
            # Handle media attachments if provided
            media_ids = request.data.get('media_ids', [])
            if media_ids and isinstance(media_ids, list):
                from MediaFiles.models import Media
                for media_id in media_ids:
                    try:
                        media_obj = Media.objects.get(id=media_id)
                        comment.attach_media(media_obj, meta={'type': 'comment_attachment'}, created_by=request.user)
                    except Media.DoesNotExist:
                        pass  # Skip invalid media IDs
            
            # TODO: Send notification
            # - If customer sends: notify admins
            # - If admin sends: notify customer
            
            return Response({
                'message': 'Comment added successfully',
                'comment': OrderCommentSerializer(comment, context={'request': request}).data
            }, status=status.HTTP_201_CREATED)
        
        # Return detailed validation errors
        return Response({
            'error': 'Validation failed',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    operation_summary='Mark Order Comments as Read',
    operation_description='Marks all comments for a given order as read for the current user. This endpoint acknowledges that the user has viewed the comments.',
    responses={
        200: openapi.Response(
            description='Comments marked as read',
            examples={
                'application/json': {
                    'message': 'Comments marked as read successfully'
                }
            }
        ),
        404: openapi.Response(description='Order not found'),
        403: openapi.Response(description='Permission denied')
    },
    tags=['Orders']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_order_comments_as_read(request, order_id):
    """
    Mark all unread comments for an order as read for the current user.
    Creates read receipts for all comments that the user hasn't read yet.
    """
    try:
        order = Order.objects.select_related('created_by').get(id=order_id)
    except Order.DoesNotExist:
        return Response({
            'error': 'Order not found'
        }, status=status.HTTP_404_NOT_FOUND)

    # Check permissions - user must own the order or be admin
    if order.created_by != request.user and not (request.user.is_staff or request.user.is_superuser):
        return Response({
            'error': 'You do not have permission to access this order'
        }, status=status.HTTP_403_FORBIDDEN)

    # Get all comments for this order
    comments = OrderComment.objects.filter(order=order)
    
    # Exclude internal comments for non-admin users
    if not (request.user.is_staff or request.user.is_superuser):
        comments = comments.exclude(is_internal=True)
    
    # Create read receipts for all comments that haven't been read by this user
    # Use get_or_create to avoid duplicate key errors
    read_receipts_created = 0
    for comment in comments:
        # Use get_or_create to safely create read receipt (avoids duplicate key errors)
        receipt, created = OrderCommentReadReceipt.objects.get_or_create(
            comment=comment,
            user=request.user
        )
        if created:
            read_receipts_created += 1
    
    return Response({
        'message': 'Comments marked as read successfully',
        'read_receipts_created': read_receipts_created
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    operation_summary='Get User Invoices',
    operation_description='Get all invoices for the authenticated user',
    responses={
        200: openapi.Response(description='Invoices retrieved successfully'),
        401: openapi.Response(description='Unauthorized')
    },
    tags=['Orders']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_invoices(request):
    """Get all invoices for the authenticated user"""
    invoices = Invoice.objects.filter(user=request.user).order_by('-created_at')
    
    serializer = InvoiceSerializer(invoices, many=True)
    return Response({
        'invoices': serializer.data,
        'count': invoices.count()
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    operation_summary='Download Invoice PDF',
    operation_description='Download invoice PDF by invoice ID',
    responses={
        200: openapi.Response(description='Invoice PDF'),
        404: openapi.Response(description='Invoice not found'),
        403: openapi.Response(description='Access denied')
    },
    tags=['Orders']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_invoice(request, invoice_id):
    """Download invoice PDF"""
    import os
    
    try:
        invoice = Invoice.objects.get(id=invoice_id, user=request.user)
    except Invoice.DoesNotExist:
        return Response({
            'error': 'Invoice not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Build full file path from relative path stored in database
    if not invoice.pdf_file_path:
        return Response({
            'error': 'Invoice PDF not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    file_path = os.path.join(settings.MEDIA_ROOT, invoice.pdf_file_path)
    if not os.path.exists(file_path):
        return Response({
            'error': 'Invoice PDF not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    from django.http import FileResponse
    return FileResponse(
        open(file_path, 'rb'),
        content_type='application/pdf',
        filename=f"{invoice.invoice_number}.pdf"
    )
