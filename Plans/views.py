from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from .models import Plan, Subscription
from .serializers import PlanSerializer, SubscriptionSerializer
from Orders.models import Order


@swagger_auto_schema(
    method='get',
    operation_summary='Get Subscription Plans',
    operation_description='Get all active subscription plans (monthly and annual).',
    responses={
        200: openapi.Response(
            description='Plans retrieved successfully',
            examples={
                'application/json': {
                    'monthly_plans': [
                        {
                            'id': 1,
                            'plan_name': 'Basic Monthly',
                            'plan_duration': 'monthly',
                            'price': 9.99,
                            'features': ['10 downloads/month', 'Basic support'],
                            'status': 'active'
                        }
                    ],
                    'annual_plans': [
                        {
                            'id': 2,
                            'plan_name': 'Premium Annual',
                            'plan_duration': 'annually',
                            'price': 99.99,
                            'features': ['Unlimited downloads', 'Priority support'],
                            'status': 'active'
                        }
                    ],
                    'all_plans': []
                }
            }
        )
    },
    tags=['Plans']
)

@api_view(['GET'])
@permission_classes([AllowAny])
def plans_list(request):
    """
    Get all active plans (monthly and annual).
    """
    plans = Plan.objects.filter(status='active').order_by('plan_name', 'plan_duration')
    
    # Separate monthly and annual plans
    monthly_plans = plans.filter(plan_duration='monthly')
    annual_plans = plans.filter(plan_duration='annually')
    
    return Response({
        'monthly_plans': PlanSerializer(monthly_plans, many=True).data,
        'annual_plans': PlanSerializer(annual_plans, many=True).data,
        'all_plans': PlanSerializer(plans, many=True).data
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Plan Detail',
    operation_description='Plan Detail endpoint',
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
def plan_detail(request, plan_id):
    """
    Get detailed information about a specific plan.
    """
    try:
        plan = Plan.objects.get(id=plan_id, status='active')
        return Response({
            'plan': PlanSerializer(plan).data
        })
    except Plan.DoesNotExist:
        return Response({
            'error': 'Plan not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='get',
    operation_summary='My Subscription',
    operation_description='My Subscription endpoint',
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
def my_subscription(request):
    """
    Get user's current subscription status.
    """
    subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).first()
    
    if subscription:
        return Response({
            'subscription': SubscriptionSerializer(subscription).data,
            'has_active_subscription': True,
            'plan': PlanSerializer(subscription.plan).data
        })
    else:
        return Response({
            'subscription': None,
            'has_active_subscription': False
        })


@swagger_auto_schema(
    method='post',
    operation_summary='Subscribe To Plan',
    operation_description='Subscribe To Plan endpoint',
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
def subscribe_to_plan(request):
    """
    Subscribe user to a plan - creates Subscription and Order records.
    Subscription starts as 'pending' until payment is successful.
    """
    plan_id = request.data.get('plan_id')
    auto_renew = request.data.get('auto_renew', True)
    
    try:
        plan = Plan.objects.get(id=plan_id, status='active')
    except Plan.DoesNotExist:
        return Response({
            'error': 'Plan not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if user already has an active subscription
    existing_subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).first()
    
    if existing_subscription:
        return Response({
            'error': 'User already has an active subscription',
            'current_subscription': SubscriptionSerializer(existing_subscription).data
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create subscription with pending status (payment not completed yet)
    subscription = Subscription.objects.create(
        plan=plan,
        auto_renew=auto_renew,
        status='pending',  # Will be updated to 'active' on successful payment
        created_by=request.user
    )
    
    # Create Order for subscription purchase
    order = Order.objects.create(
        order_type='subscription',  # Using 'subscription' for subscription purchase transaction
        total_amount=plan.price,
        status='pending',  # Will be updated to 'success' on successful payment
        subscription=subscription,  # Link to subscription being purchased
        created_by=request.user
    )
    
    return Response({
        'message': 'Subscription created. Please complete payment.',
        'subscription': SubscriptionSerializer(subscription).data,
        'plan': PlanSerializer(plan).data,
        'order_id': order.id,  # Return order_id for payment processing
        'amount': float(plan.price)
    }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='post',
    operation_summary='Cancel Subscription',
    operation_description='Cancel Subscription endpoint',
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
def cancel_subscription(request):
    """
    Cancel user's active subscription.
    """
    subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).first()
    
    if not subscription:
        return Response({
            'error': 'No active subscription found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    subscription.status = 'cancelled'
    subscription.save()
    
    return Response({
        'message': 'Subscription cancelled successfully',
        'subscription': SubscriptionSerializer(subscription).data
    })


@swagger_auto_schema(
    method='post',
    operation_summary='Update Subscription',
    operation_description='Update Subscription endpoint',
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
def update_subscription(request):
    """
    Update subscription settings (like auto_renew).
    """
    subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).first()
    
    if not subscription:
        return Response({
            'error': 'No active subscription found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    auto_renew = request.data.get('auto_renew')
    if auto_renew is not None:
        subscription.auto_renew = auto_renew
        subscription.save()
    
    return Response({
        'message': 'Subscription updated successfully',
        'subscription': SubscriptionSerializer(subscription).data
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Subscription History',
    operation_description='Subscription History endpoint',
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
def subscription_history(request):
    """
    Get user's subscription history.
    """
    subscriptions = Subscription.objects.filter(
        created_by=request.user
    ).order_by('-created_at')
    
    return Response({
        'subscriptions': SubscriptionSerializer(subscriptions, many=True).data,
        'total_subscriptions': subscriptions.count()
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Subscription Benefits',
    operation_description='Subscription Benefits endpoint',
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
def subscription_benefits(request):
    """
    Get benefits of user's current subscription plan.
    """
    subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).first()
    
    if not subscription:
        return Response({
            'error': 'No active subscription found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    plan = subscription.plan
    benefits = plan.description  # This would contain the plan benefits
    
    return Response({
        'plan': PlanSerializer(plan).data,
        'benefits': benefits,
        'subscription': SubscriptionSerializer(subscription).data
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Subscription Usage',
    operation_description='Subscription Usage endpoint',
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
def subscription_usage(request):
    """
    Get user's subscription usage statistics.
    """
    subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).first()
    
    if not subscription:
        return Response({
            'error': 'No active subscription found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Calculate usage based on plan type and duration
    plan = subscription.plan
    subscription_start = subscription.created_at
    
    # Calculate days since subscription
    days_since_subscription = (timezone.now() - subscription_start).days
    
    # Get usage data (this would be calculated based on actual usage)
    usage_data = {
        'plan_name': plan.get_plan_name_display(),
        'plan_duration': plan.get_plan_duration_display(),
        'subscription_start': subscription_start,
        'days_since_subscription': days_since_subscription,
        'auto_renew': subscription.auto_renew,
        'status': subscription.get_status_display()
    }
    
    return Response({
        'subscription': SubscriptionSerializer(subscription).data,
        'usage': usage_data
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Plan Comparison',
    operation_description='Plan Comparison endpoint',
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
def plan_comparison(request):
    """
    Get plan comparison data for all active plans.
    """
    plans = Plan.objects.filter(status='active').order_by('plan_name', 'plan_duration')
    
    # Group plans by name for comparison
    plan_groups = {}
    for plan in plans:
        plan_name = plan.get_plan_name_display()
        if plan_name not in plan_groups:
            plan_groups[plan_name] = {}
        plan_groups[plan_name][plan.get_plan_duration_display()] = PlanSerializer(plan).data
    
    return Response({
        'plan_groups': plan_groups,
        'all_plans': PlanSerializer(plans, many=True).data
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Subscription Expiry',
    operation_description='Subscription Expiry endpoint',
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
def subscription_expiry(request):
    """
    Get subscription expiry information.
    """
    subscription = Subscription.objects.filter(
        created_by=request.user,
        status='active'
    ).first()
    
    if not subscription:
        return Response({
            'error': 'No active subscription found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Calculate expiry date based on plan duration
    plan = subscription.plan
    subscription_start = subscription.created_at
    
    if plan.plan_duration == 'monthly':
        expiry_date = subscription_start + timedelta(days=30)
    else:  # annually
        expiry_date = subscription_start + timedelta(days=365)
    
    days_until_expiry = (expiry_date - timezone.now()).days
    
    return Response({
        'subscription': SubscriptionSerializer(subscription).data,
        'expiry_date': expiry_date,
        'days_until_expiry': days_until_expiry,
        'is_expired': days_until_expiry <= 0,
        'auto_renew': subscription.auto_renew
    })
