from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.conf import settings
import razorpay
import json
import hmac
import hashlib
from .models import RazorpayPayment, RazorpayWebhookEvent
from .serializers import RazorpayPaymentSerializer, RazorpayWebhookEventSerializer
from Orders.models import Order, Cart

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def delete_cart_items_for_order(order, user):
    """
    Delete cart items for products in the order after successful payment.
    """
    if not order or not order.product_ids:
        return
    
    try:
        # Parse product_ids from comma-separated string
        product_ids = [int(pid.strip()) for pid in order.product_ids.split(',') if pid.strip()]
        
        if product_ids:
            # Delete cart items for these products
            Cart.objects.filter(
                created_by=user,
                cart_type='cart',
                product_id__in=product_ids
            ).delete()
    except (ValueError, AttributeError) as e:
        # Log error but don't fail the payment capture
        import logging
        logger = logging.getLogger(__name__)

@swagger_auto_schema(
    method='post',
    operation_summary='Create Razorpay Payment Order',
    operation_description='Create a new Razorpay payment order for processing payments.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'amount': openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description='Payment amount in paise (e.g., 10000 for ₹100)',
                example=10000
            ),
            'currency': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Payment currency',
                example='INR',
                enum=['INR', 'USD', 'EUR']
            ),
            'order_id': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Internal order ID',
                example='ORD_123456'
            ),
            'description': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Payment description',
                example='Payment for order #123456'
            ),
            'customer_details': openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description='Customer information',
                properties={
                    'name': openapi.Schema(type=openapi.TYPE_STRING, example='John Doe'),
                    'email': openapi.Schema(type=openapi.TYPE_STRING, example='john@example.com'),
                    'contact': openapi.Schema(type=openapi.TYPE_STRING, example='+919876543210')
                }
            )
        },
        required=['amount', 'currency', 'order_id']
    ),
    responses={
        201: openapi.Response(
            description='Payment order created successfully',
            examples={
                'application/json': {
                    'message': 'Payment order created successfully',
                    'payment_order': {
                        'id': 'order_1234567890',
                        'amount': 10000,
                        'currency': 'INR',
                        'status': 'created',
                        'created_at': 1640995200,
                        'receipt': 'receipt_123456'
                    },
                    'razorpay_order_id': 'order_1234567890'
                }
            }
        ),
        400: openapi.Response(description='Bad request - invalid payment data'),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Razorpay Payments']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment_order(request):
    """
    Create a Razorpay order for payment.
    """
    amount = request.data.get('amount')
    currency = request.data.get('currency', 'INR')
    order_id = request.data.get('order_id')
    
    if not amount:
        return Response({
            'error': 'Amount is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create Razorpay order
        razorpay_order = razorpay_client.order.create({
            'amount': int(float(amount) * 100),  # Convert to paise
            'currency': currency,
            'receipt': f'order_{order_id}' if order_id else f'payment_{request.user.id}',
            'notes': {
                'user_id': request.user.id,
                'order_id': order_id
            }
        })
        
        # Get or create order if order_id is provided
        order = None
        if order_id:
            try:
                order = Order.objects.get(id=order_id, created_by=request.user)
            except Order.DoesNotExist:
                pass
        
        # Create payment record and associate with order
        # Note: razorpay_payment_id is not set here - it will be set when payment is captured
        # The field must be nullable in the database (run migration if you see NOT NULL constraint errors)
        payment = RazorpayPayment.objects.create(
            order=order,  # Associate order immediately if available
            razorpay_order_id=razorpay_order['id'],
            amount=amount,
            currency=currency,
            description=request.data.get('description', ''),
            notes=request.data.get('notes', {}),
            created_by=request.user
        )
        
        return Response({
            'message': 'Payment order created successfully',
            'razorpay_order_id': razorpay_order['id'],
            'amount': razorpay_order['amount'],
            'currency': razorpay_order['currency'],
            'payment_id': payment.id
        })
    
    except Exception as e:
        return Response({
            'error': f'Failed to create payment order: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary='Capture Payment',
    operation_description='Capture Payment endpoint',
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
def capture_payment(request):
    """
    Capture a Razorpay payment.
    Optimized to reduce external API calls and improve response time.
    """
    payment_id = request.data.get('payment_id')
    razorpay_payment_id = request.data.get('razorpay_payment_id')
    amount = request.data.get('amount')
    
    if not all([payment_id, razorpay_payment_id, amount]):
        return Response({
            'error': 'Payment ID, Razorpay payment ID, and amount are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        payment = RazorpayPayment.objects.select_related('order').get(
            id=payment_id,
            created_by=request.user
        )
        
        # Check if payment is already captured (fast check, no external API call)
        if payment.status == 'captured':
            # Payment already captured, return success immediately
            if payment.order:
                payment.order.status = 'success'
                payment.order.save()
                
                # Decrement free downloads from subscription if this order used them
                if payment.order.subscription and payment.order.free_downloads_used > 0:
                    try:
                        payment.order.subscription.use_free_downloads(payment.order.free_downloads_used)
                    except ValueError as e:
                        # Log error but don't fail payment capture
                        import logging
                        logger = logging.getLogger(__name__)

                # If this order is for subscription purchase, activate subscription
                if payment.order.subscription:
                    subscription = payment.order.subscription
                    subscription.status = 'active'
                    subscription.save()
                
                # If this order is for custom order request, update custom request payment status
                if payment.order.order_type == 'custom' and payment.order.custom_order_request:
                    custom_request = payment.order.custom_order_request
                    custom_request.payment_status = 'success'
                    # If status is still 'pending', keep it as 'pending' (workflow hasn't started yet)
                    if custom_request.status == 'pending':
                        custom_request.status = 'pending'
                    custom_request.save()
                
                # Delete cart items synchronously for immediate deletion (only for cart orders)
                if payment.order.order_type == 'cart' and payment.order.product_ids:
                    try:
                        delete_cart_items_for_order(payment.order, request.user)
                    except Exception as e:
                        # Log but don't fail the payment capture
                        import logging
                        logger = logging.getLogger(__name__)

            return Response({
                'message': 'Payment already captured',
                'payment': RazorpayPaymentSerializer(payment).data
            }, status=status.HTTP_200_OK)
        
        # Try to capture payment with Razorpay (single API call instead of fetch + capture)
        try:
            # Attempt capture directly - Razorpay will return error if already captured
            razorpay_client.payment.capture(
                razorpay_payment_id,
                int(float(amount) * 100)  # Convert to paise
            )
            # If we get here, capture was successful
            capture_successful = True
        except Exception as capture_error:
            error_message = str(capture_error)
            error_repr = repr(capture_error).lower()
            
            # Check if payment is already captured (check multiple possible error messages)
            is_already_captured = (
                'already been captured' in error_message.lower() or 
                'already captured' in error_message.lower() or
                'already been captured' in error_repr or
                'already captured' in error_repr or
                ('captured' in error_repr and 'already' in error_repr) or
                'this payment has already been captured' in error_message.lower() or
                'payment has already been captured' in error_message.lower()
            )
            
            if is_already_captured:
                # Payment already captured, update our record and return success
                capture_successful = True
            else:
                # Real error occurred, re-raise
                raise capture_error
        
        # Update payment status (whether newly captured or already captured)
        payment.razorpay_payment_id = razorpay_payment_id
        payment.status = 'captured'
        payment.save()
        
        # Update order status if exists
        if payment.order:
            payment.order.status = 'success'
            payment.order.save()
            
            # Decrement free downloads from subscription if this order used them
            if payment.order.subscription and payment.order.free_downloads_used > 0:
                try:
                    payment.order.subscription.use_free_downloads(payment.order.free_downloads_used)
                except ValueError as e:
                    # Log error but don't fail payment capture
                    import logging
                    logger = logging.getLogger(__name__)

            # If this order is for subscription purchase, activate subscription
            if payment.order.subscription:
                subscription = payment.order.subscription
                subscription.status = 'active'
                subscription.save()
            
            # If this order is for custom order request, update custom request payment status
            if payment.order.order_type == 'custom' and payment.order.custom_order_request:
                custom_request = payment.order.custom_order_request
                custom_request.payment_status = 'success'  # Payment successful, ready for processing
                # If status is still 'pending', keep it as 'pending' (workflow hasn't started yet)
                if custom_request.status == 'pending':
                    custom_request.status = 'pending'
                custom_request.save()
            
            # Delete cart items synchronously for immediate deletion (only for cart orders)
            if payment.order.order_type == 'cart' and payment.order.product_ids:
                try:
                    delete_cart_items_for_order(payment.order, request.user)
                except Exception as cart_error:
                    # Log but don't fail the payment capture
                    import logging
                    logger = logging.getLogger(__name__)

            # Process invoices and wallet settlements for cart orders
            if payment.order.order_type == 'cart' and payment.order.status == 'success':
                try:
                    from Orders.invoice_service import process_order_invoices
                    process_order_invoices(payment.order)
                except Exception as invoice_error:
                    # Log error but don't fail payment capture
                    import logging
                    logger = logging.getLogger(__name__)

        return Response({
            'message': 'Payment captured successfully',
            'payment': RazorpayPaymentSerializer(payment).data
        }, status=status.HTTP_200_OK)
    
    except RazorpayPayment.DoesNotExist:
        return Response({
            'error': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        error_message = str(e)
        error_repr = repr(e).lower()
        
        # Check if error is about payment already being captured (multiple checks)
        is_already_captured = (
            'already been captured' in error_message.lower() or 
            'already captured' in error_message.lower() or
            'already been captured' in error_repr or
            'already captured' in error_repr or
            ('captured' in error_repr and 'already' in error_repr) or
            'payment has already been captured' in error_message.lower()
        )
        
        if is_already_captured:
            # Update payment status to captured even if Razorpay says it's already captured
            try:
                payment = RazorpayPayment.objects.get(
                    id=payment_id,
                    created_by=request.user
                )
                payment.razorpay_payment_id = razorpay_payment_id
                payment.status = 'captured'
                payment.save()
                
                # Update order status if exists
                if payment.order:
                    payment.order.status = 'success'
                    payment.order.save()
                    
                    # Decrement free downloads from subscription if this order used them
                    if payment.order.subscription and payment.order.free_downloads_used > 0:
                        try:
                            payment.order.subscription.use_free_downloads(payment.order.free_downloads_used)
                        except ValueError as e:
                            # Log error but don't fail payment capture
                            import logging
                            logger = logging.getLogger(__name__)

                    # If this order is for subscription purchase, activate subscription
                    if payment.order.subscription:
                        subscription = payment.order.subscription
                        subscription.status = 'active'
                        subscription.save()
                    
                    # If this order is for custom order request, update custom request status
                    if payment.order.order_type == 'custom' and payment.order.custom_order_request:
                        custom_request = payment.order.custom_order_request
                        custom_request.status = 'success'
                        custom_request.save()
                    
                    # Delete cart items synchronously for immediate deletion (only for cart orders)
                    if payment.order.order_type == 'cart' and payment.order.product_ids:
                        try:
                            delete_cart_items_for_order(payment.order, request.user)
                        except Exception as cart_error:
                            # Log but don't fail the payment capture
                            import logging
                            logger = logging.getLogger(__name__)

                return Response({
                    'message': 'Payment already captured',
                    'payment': RazorpayPaymentSerializer(payment).data
                }, status=status.HTTP_200_OK)
            except Exception as update_error:
                # Log the error but continue to return the original error
                import logging
                logger = logging.getLogger(__name__)

                pass
        
        return Response({
            'error': f'Failed to capture payment: {error_message}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_summary='Payment Status',
    operation_description='Payment Status endpoint',
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
def payment_status(request, payment_id):
    """
    Get payment status.
    """
    try:
        payment = RazorpayPayment.objects.get(
            id=payment_id,
            created_by=request.user
        )
        
        # Fetch updated status from Razorpay
        if payment.razorpay_payment_id:
            try:
                razorpay_payment = razorpay_client.payment.fetch(payment.razorpay_payment_id)
                payment.status = razorpay_payment['status']
                payment.method = razorpay_payment.get('method')
                payment.fee = razorpay_payment.get('fee', 0) / 100  # Convert from paise
                payment.tax = razorpay_payment.get('tax', 0) / 100
                payment.save()
            except Exception as e:
                pass
        
        return Response({
            'payment': RazorpayPaymentSerializer(payment).data
        })
    
    except RazorpayPayment.DoesNotExist:
        return Response({
            'error': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)

@swagger_auto_schema(
    method='get',
    operation_summary='Payment History',
    operation_description='Payment History endpoint',
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
def payment_history(request):
    """
    Get user's payment history.
    """
    payments = RazorpayPayment.objects.filter(
        created_by=request.user
    ).order_by('-created_at')
    
    return Response({
        'payments': RazorpayPaymentSerializer(payments, many=True).data,
        'total_payments': payments.count()
    })

@swagger_auto_schema(
    method='post',
    operation_summary='Create Refund',
    operation_description='Create Refund endpoint',
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
def create_refund(request):
    """
    Create a refund for a payment.
    """
    payment_id = request.data.get('payment_id')
    amount = request.data.get('amount')
    notes = request.data.get('notes', {})
    
    if not all([payment_id, amount]):
        return Response({
            'error': 'Payment ID and amount are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        payment = RazorpayPayment.objects.get(
            id=payment_id,
            created_by=request.user,
            status='captured'
        )
        
        if not payment.razorpay_payment_id:
            return Response({
                'error': 'Payment not captured yet'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create refund with Razorpay
        refund = razorpay_client.payment.refund(
            payment.razorpay_payment_id,
            {
                'amount': int(float(amount) * 100),  # Convert to paise
                'notes': notes
            }
        )
        
        # Update payment status
        payment.status = 'refunded'
        payment.save()
        
        return Response({
            'message': 'Refund created successfully',
            'refund_id': refund['id'],
            'refund_amount': refund['amount'],
            'payment': RazorpayPaymentSerializer(payment).data
        })
    
    except RazorpayPayment.DoesNotExist:
        return Response({
            'error': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Failed to create refund: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
@swagger_auto_schema(
    method='post',
    operation_summary='Webhook Handler',
    operation_description='Webhook Handler endpoint',
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
@permission_classes([AllowAny])
def webhook_handler(request):
    """
    Handle Razorpay webhook events.
    """
    try:
        # Get webhook signature
        webhook_signature = request.headers.get('X-Razorpay-Signature')
        webhook_body = request.body
        
        # Verify webhook signature
        expected_signature = hmac.new(
            settings.RAZORPAY_WEBHOOK_SECRET.encode('utf-8'),
            webhook_body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(webhook_signature, expected_signature):
            return HttpResponse('Unauthorized', status=401)
        
        # Parse webhook data
        webhook_data = json.loads(webhook_body)
        event_type = webhook_data.get('event')
        event_id = webhook_data.get('id')
        
        # Create webhook event record
        webhook_event = RazorpayWebhookEvent.objects.create(
            event_id=event_id,
            event_type=event_type,
            payload=webhook_data
        )
        
        # Process webhook event
        if event_type == 'payment.captured':
            payment_id = webhook_data.get('payload', {}).get('payment', {}).get('entity', {}).get('id')
            if payment_id:
                try:
                    payment = RazorpayPayment.objects.get(razorpay_payment_id=payment_id)
                    payment.status = 'captured'
                    payment.save()
                    
                    # Update order status
                    if payment.order:
                        payment.order.status = 'success'
                        payment.order.save()
                        
                        # Decrement free downloads from subscription if this order used them
                        if payment.order.subscription and payment.order.free_downloads_used > 0:
                            try:
                                payment.order.subscription.use_free_downloads(payment.order.free_downloads_used)
                            except ValueError as e:
                                # Log error but don't fail webhook processing
                                import logging
                                logger = logging.getLogger(__name__)

                        # If this order is for subscription purchase, activate subscription
                        if payment.order.subscription:
                            subscription = payment.order.subscription
                            subscription.status = 'active'
                            subscription.save()
                        
                        # If this order is for custom order request, update custom request status
                        if payment.order.order_type == 'custom' and payment.order.custom_order_request:
                            custom_request = payment.order.custom_order_request
                            custom_request.status = 'success'
                            custom_request.save()
                        
                        # Delete cart items synchronously for immediate deletion (only for cart orders)
                        # Note: webhook doesn't have request.user, so we use order.created_by
                        if payment.order.order_type == 'cart' and payment.order.product_ids:
                            try:
                                delete_cart_items_for_order(payment.order, payment.order.created_by)
                            except Exception as cart_error:
                                # Log but don't fail the webhook processing
                                import logging
                                logger = logging.getLogger(__name__)

                        # Process invoices and wallet settlements for cart orders
                        if payment.order.order_type == 'cart' and payment.order.status == 'success':
                            try:
                                from Orders.invoice_service import process_order_invoices
                                process_order_invoices(payment.order)
                            except Exception as invoice_error:
                                # Log error but don't fail webhook processing
                                import logging
                                logger = logging.getLogger(__name__)

                    webhook_event.processed = True
                    webhook_event.save()
                except RazorpayPayment.DoesNotExist:
                    pass
        
        elif event_type == 'payment.failed':
            payment_id = webhook_data.get('payload', {}).get('payment', {}).get('entity', {}).get('id')
            if payment_id:
                try:
                    payment = RazorpayPayment.objects.get(razorpay_payment_id=payment_id)
                    payment.status = 'failed'
                    payment.error_code = webhook_data.get('payload', {}).get('payment', {}).get('entity', {}).get('error_code')
                    payment.error_description = webhook_data.get('payload', {}).get('payment', {}).get('entity', {}).get('error_description')
                    payment.save()
                    
                    # Update Order status to failed
                    if payment.order:
                        payment.order.status = 'failed'
                        payment.order.save()
                        
                        # If this order is for subscription purchase, mark subscription as failed
                        if payment.order.subscription:
                            subscription = payment.order.subscription
                            subscription.status = 'failed'
                            subscription.save()
                        
                        # If this order is for custom order request, mark custom request payment as failed
                        if payment.order.order_type == 'custom' and payment.order.custom_order_request:
                            custom_request = payment.order.custom_order_request
                            custom_request.payment_status = 'failed'
                            custom_request.save()
                    
                    webhook_event.processed = True
                    webhook_event.save()
                except RazorpayPayment.DoesNotExist:
                    pass
        
        # Note: Razorpay Route API and Payouts API webhook handlers removed
        # Settlements are now processed manually using the settlement sheet
        
        return HttpResponse('OK', status=200)
    
    except Exception as e:
        return HttpResponse(f'Error: {str(e)}', status=500)

@swagger_auto_schema(
    method='get',
    operation_summary='Webhook Events',
    operation_description='Webhook Events endpoint',
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
def webhook_events(request):
    """
    Get webhook events (admin only).
    """
    events = RazorpayWebhookEvent.objects.all().order_by('-created_at')
    
    return Response({
        'webhook_events': RazorpayWebhookEventSerializer(events, many=True).data,
        'total_events': events.count()
    })

@swagger_auto_schema(
    method='get',
    operation_summary='Payment Methods',
    operation_description='Payment Methods endpoint',
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
def payment_methods(request):
    """
    Get available payment methods.
    """
    try:
        methods = razorpay_client.payment_methods.fetch_all()
        return Response({
            'payment_methods': methods
        })
    except Exception as e:
        return Response({
            'error': f'Failed to fetch payment methods: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary='Create Subscription Payment',
    operation_description='Create Subscription Payment endpoint',
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
def create_subscription_payment(request):
    """
    Create payment for subscription plan.
    """
    plan_id = request.data.get('plan_id')
    amount = request.data.get('amount')
    
    if not all([plan_id, amount]):
        return Response({
            'error': 'Plan ID and amount are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create Razorpay order for subscription
        razorpay_order = razorpay_client.order.create({
            'amount': int(float(amount) * 100),
            'currency': 'INR',
            'receipt': f'subscription_{plan_id}_{request.user.id}',
            'notes': {
                'user_id': request.user.id,
                'plan_id': plan_id,
                'type': 'subscription'
            }
        })
        
        # Create payment record
        # Note: razorpay_payment_id is not set here - it will be set when payment is captured
        # The field must be nullable in the database (run migration if you see NOT NULL constraint errors)
        payment = RazorpayPayment.objects.create(
            razorpay_order_id=razorpay_order['id'],
            amount=amount,
            currency='INR',
            description=f'Subscription payment for plan {plan_id}',
            notes={'plan_id': plan_id, 'type': 'subscription'},
            created_by=request.user
        )
        
        return Response({
            'message': 'Subscription payment order created successfully',
            'razorpay_order_id': razorpay_order['id'],
            'amount': razorpay_order['amount'],
            'currency': razorpay_order['currency'],
            'payment_id': payment.id
        })
    
    except Exception as e:
        return Response({
            'error': f'Failed to create subscription payment: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary='Create Pdf Payment Order',
    operation_description='Create Pdf Payment Order endpoint',
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
def create_pdf_payment_order(request):
    """
    Create a Razorpay order for PDF download payment.
    """
    download_id = request.data.get('download_id')
    amount = request.data.get('amount')
    
    if not all([download_id, amount]):
        return Response({
            'error': 'Download ID and amount are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Import here to avoid circular imports
        from Catalog.models import PDFDownload
        
        # Verify PDF download exists and is eligible for payment
        try:
            pdf_download = PDFDownload.objects.get(
                id=download_id,
                download_type='paid',
                payment_status='pending'
            )
        except PDFDownload.DoesNotExist:
            return Response({
                'error': 'PDF download not found or not eligible for payment'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify user owns this PDF download via relations system
        pdf_user = pdf_download.get_user()
        if pdf_user != request.user:
            return Response({
                'error': 'You do not have permission to process payment for this PDF download'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Create Razorpay order for PDF payment
        razorpay_order = razorpay_client.order.create({
            'amount': int(float(amount) * 100),  # Convert to paise
            'currency': 'INR',
            'receipt': f'pdf_download_{download_id}',
            'notes': {
                'user_id': request.user.id,
                'download_id': download_id,
                'type': 'pdf_download'
            }
        })
        
        # Create payment record
        # Note: razorpay_payment_id is not set here - it will be set when payment is captured
        # The field must be nullable in the database (run migration if you see NOT NULL constraint errors)
        payment = RazorpayPayment.objects.create(
            razorpay_order_id=razorpay_order['id'],
            amount=amount,
            currency='INR',
            description=f'PDF Download Payment - {pdf_download.total_pages} pages',
            notes={
                'download_id': download_id,
                'type': 'pdf_download',
                'total_pages': pdf_download.total_pages,
                'price_per_design': float(pdf_download.price_per_design)
            },
            created_by=request.user
        )
        
        # Link payment to PDF download
        pdf_download.razorpay_payment = payment
        pdf_download.save()
        
        return Response({
            'message': 'PDF payment order created successfully',
            'razorpay_order_id': razorpay_order['id'],
            'amount': razorpay_order['amount'],
            'currency': razorpay_order['currency'],
            'payment_id': payment.id,
            'download_id': download_id
        })
    
    except PDFDownload.DoesNotExist:
        return Response({
            'error': 'PDF download not found or not eligible for payment'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Failed to create PDF payment order: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='post',
    operation_summary='Capture Pdf Payment',
    operation_description='Capture Pdf Payment endpoint',
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
def capture_pdf_payment(request):
    """
    Capture a Razorpay payment for PDF download.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    payment_id = request.data.get('payment_id')
    razorpay_payment_id = request.data.get('razorpay_payment_id')
    amount = request.data.get('amount')
    
    # Log received data for debugging

    # Validate required fields
    if payment_id is None or payment_id == '':

        return Response({
            'error': 'Payment ID is required',
            'received_data': {
                'payment_id': payment_id,
                'razorpay_payment_id': razorpay_payment_id,
                'amount': amount
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not razorpay_payment_id or razorpay_payment_id == '':

        return Response({
            'error': 'Razorpay payment ID is required',
            'received_data': {
                'payment_id': payment_id,
                'razorpay_payment_id': razorpay_payment_id,
                'amount': amount
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if amount is None or amount == '':

        return Response({
            'error': 'Amount is required',
            'received_data': {
                'payment_id': payment_id,
                'razorpay_payment_id': razorpay_payment_id,
                'amount': amount
            }
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Convert payment_id to int if it's a string
        try:
            payment_id_int = int(payment_id) if payment_id else None
        except (ValueError, TypeError):

            return Response({
                'error': f'Invalid payment ID format: {payment_id}',
                'received_data': {
                    'payment_id': payment_id,
                    'razorpay_payment_id': razorpay_payment_id,
                    'amount': amount
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        payment = RazorpayPayment.objects.get(
            id=payment_id_int,
            created_by=request.user
        )
        
        # Check if payment is already captured
        if payment.status == 'captured' and payment.razorpay_payment_id:

            # Payment already captured, just proceed with order creation
            capture_successful = True
        else:
            # Convert amount to float then int (paise)
            try:
                amount_float = float(amount)
                amount_paise = int(amount_float * 100)
            except (ValueError, TypeError) as e:

                return Response({
                    'error': f'Invalid amount format: {amount}',
                    'received_data': {
                        'payment_id': payment_id,
                        'razorpay_payment_id': razorpay_payment_id,
                        'amount': amount
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Capture payment with Razorpay (with handling for already-captured payments)
            try:
                razorpay_client.payment.capture(
                    razorpay_payment_id,
                    amount_paise
                )
                capture_successful = True

            except Exception as capture_error:
                error_message = str(capture_error)
                error_repr = repr(capture_error).lower()
                
                # Check if payment is already captured (check multiple possible error messages)
                is_already_captured = (
                    'already been captured' in error_message.lower() or 
                    'already captured' in error_message.lower() or
                    'already been captured' in error_repr or
                    'already captured' in error_repr or
                    ('captured' in error_repr and 'already' in error_repr) or
                    'this payment has already been captured' in error_message.lower() or
                    'payment has already been captured' in error_message.lower()
                )
                
                if is_already_captured:
                    # Payment already captured, update our record and continue

                    capture_successful = True
                else:
                    # Real error occurred, re-raise

                    raise capture_error
        
        # Update payment status (whether newly captured or already captured)
        payment.razorpay_payment_id = razorpay_payment_id
        payment.status = 'captured'
        payment.save()
        
        # Update PDF download status and create order
        pdf_downloads = payment.pdf_downloads.all()

        orders_created = []
        
        if pdf_downloads.count() == 0:

            # Try to find PDF download by download_id from payment notes
            download_id = payment.notes.get('download_id') if payment.notes else None
            if download_id:
                from Catalog.models import PDFDownload
                try:
                    pdf_download = PDFDownload.objects.get(id=download_id)

                    pdf_download.razorpay_payment = payment
                    pdf_download.save()
                    pdf_downloads = [pdf_download]
                except PDFDownload.DoesNotExist:
                    pass

        for pdf_download in pdf_downloads:
            try:
                pdf_download.payment_status = 'paid'
                # PDF is generated on-demand when user clicks download (not stored permanently)
                pdf_download.status = 'pending'
                pdf_download.save()

                # Create order for mock PDF download
                from Orders.models import Order
                product_ids_str = ','.join([str(pid) for pid in pdf_download.selected_products]) if pdf_download.selected_products else ''

                order = Order.objects.create(
                    order_type='mock_pdf',
                    product_ids=product_ids_str,
                    total_amount=float(pdf_download.total_amount),
                    status='success',  # Payment already captured, so order is successful
                    pdf_download=pdf_download,  # Link order to PDF download
                    created_by=request.user
                )
                orders_created.append(order.id)

                # Link RazorpayPayment to Order (bidirectional relationship)
                payment.order = order
                payment.save()

            except Exception as e:

                # Continue with other PDF downloads even if one fails
                continue
        
        # Convert pdf_downloads to list if it's a queryset for length calculation
        pdf_downloads_list = list(pdf_downloads) if hasattr(pdf_downloads, '__iter__') and not isinstance(pdf_downloads, list) else pdf_downloads
        
        return Response({
            'message': 'PDF payment captured successfully',
            'payment': RazorpayPaymentSerializer(payment).data,
            'pdf_downloads_updated': len(pdf_downloads_list),
            'orders_created': orders_created,
            'orders_count': len(orders_created)
        })
    
    except RazorpayPayment.DoesNotExist:
        return Response({
            'error': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': f'Failed to capture PDF payment: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_summary='Pdf Payment Status',
    operation_description='Pdf Payment Status endpoint',
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
def pdf_payment_status(request, payment_id):
    """
    Get PDF payment status.
    """
    try:
        payment = RazorpayPayment.objects.get(
            id=payment_id,
            created_by=request.user
        )
        
        # Fetch updated status from Razorpay
        if payment.razorpay_payment_id:
            try:
                razorpay_payment = razorpay_client.payment.fetch(payment.razorpay_payment_id)
                payment.status = razorpay_payment['status']
                payment.method = razorpay_payment.get('method')
                payment.fee = razorpay_payment.get('fee', 0) / 100  # Convert from paise
                payment.tax = razorpay_payment.get('tax', 0) / 100
                payment.save()
            except Exception as e:
                pass
        
        # Get associated PDF downloads
        pdf_downloads = payment.pdf_downloads.all()
        
        return Response({
            'payment': RazorpayPaymentSerializer(payment).data,
            'pdf_downloads': [{
                'id': download.id,
                'status': download.status,
                'payment_status': download.payment_status,
                'total_pages': download.total_pages,
                'total_amount': float(download.total_amount)
            } for download in pdf_downloads]
        })
    
    except RazorpayPayment.DoesNotExist:
        return Response({
            'error': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)
