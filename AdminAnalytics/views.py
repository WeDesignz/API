from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.conf import settings
from .models import (
    RevenueReport, TopDesignsReport, TopDesignersReport, 
    ActiveUsersReport, GrowthChart, ReportExport, AnalyticsCache
)
from .serializers import (
    RevenueReportSerializer, RevenueReportCreateSerializer,
    TopDesignsReportSerializer, TopDesignersReportSerializer,
    ActiveUsersReportSerializer, ActiveUsersReportCreateSerializer,
    GrowthChartSerializer, ReportExportSerializer, ReportExportCreateSerializer,
    AnalyticsCacheSerializer, RevenueAnalyticsSerializer, TopPerformersSerializer,
    UserStatsSerializer, DashboardSummarySerializer, ExportRequestSerializer
)
from CoreAdmin.models import AdminUserProfile, AdminActivityLog

@swagger_auto_schema(
    method='get',
    operation_summary="Dashboard Summary",
    operation_description="Get dashboard summary with key metrics. Returns different data for SuperAdmin and Moderator roles.",
    responses={
        200: openapi.Response(description="Dashboard summary retrieved successfully"),
        403: openapi.Response(description="Access denied - Admin privileges required")
    },
    tags=['Admin Analytics Dashboard']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """
    Get dashboard summary with key metrics.
    Returns different data based on admin role (SuperAdmin vs Moderator).
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        is_superadmin = admin_profile.admin_group == 'superadmin'
        is_moderator = admin_profile.admin_group == 'moderator'
        
        if not (is_superadmin or is_moderator):
            return Response({
                'error': 'Admin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while retrieving dashboard summary'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        from django.contrib.auth.models import User
        from datetime import datetime, timedelta
        from django.db.models import Q, Sum, Count, Avg
        from Orders.models import Order
        from Plans.models import Subscription
        from Catalog.models import Product
        from CoreAdmin.models import DesignApproval
        from Profiles.models import DesignerProfile
        from CustomRequests.models import CustomOrderRequest
        from Feedback.models import SupportThread, ReportIssue
        from Wallet.models import Wallet
        
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)
        last_month_end = month_start - timedelta(microseconds=1)
        
        if is_superadmin:
            # ========== SUPER ADMIN DASHBOARD ==========
            
            # Financial Metrics
            # Total Revenue - Today
            revenue_today = Order.objects.filter(
                status='success',
                created_at__gte=today_start,
                created_at__lte=today_end
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # Total Revenue - This Month
            revenue_month = Order.objects.filter(
                status='success',
                created_at__gte=month_start,
                created_at__lte=now
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # Total Revenue - Last Month (for growth calculation)
            revenue_last_month = Order.objects.filter(
                status='success',
                created_at__gte=last_month_start,
                created_at__lte=last_month_end
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # Total Revenue - This Year
            revenue_year = Order.objects.filter(
                status='success',
                created_at__gte=year_start,
                created_at__lte=now
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # Calculate growth rate
            revenue_growth = 0.0
            if revenue_last_month > 0:
                revenue_growth = ((float(revenue_month) - float(revenue_last_month)) / float(revenue_last_month)) * 100
            
            # Revenue by Source
            plan_revenue = Order.objects.filter(
                status='success',
                order_type='cart',
                subscription__isnull=False,
                created_at__gte=month_start
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            design_revenue = Order.objects.filter(
                status='success',
                order_type__in=['cart', 'subscription'],
                product_ids__isnull=False,
                subscription__isnull=True,
                created_at__gte=month_start
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            custom_order_revenue = Order.objects.filter(
                status='success',
                order_type='custom',
                created_at__gte=month_start
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            # Refunds
            from CoreAdmin.models import Refund
            total_refunds = Refund.objects.filter(
                created_at__gte=month_start
            ).aggregate(total=Sum('refund_amount'))['total'] or 0
            
            # Refund count
            refund_count = Refund.objects.filter(
                created_at__gte=month_start
            ).count()
            
            net_revenue = float(revenue_month) - float(total_refunds)
            
            # Transactions
            total_transactions = Order.objects.filter(created_at__gte=month_start).count()
            successful_transactions = Order.objects.filter(
                status='success',
                created_at__gte=month_start
            ).count()
            failed_transactions = Order.objects.filter(
                status='failed',
                created_at__gte=month_start
            ).count()
            
            # Average Order Value
            avg_order_value = float(revenue_month) / successful_transactions if successful_transactions > 0 else 0
            
            # User Metrics
            total_customers = User.objects.filter(
                is_staff=False,
                is_superuser=False
            ).exclude(
                created_designer_profiles__isnull=False
            ).count()
            
            total_designers = User.objects.filter(
                created_designer_profiles__isnull=False,
                created_designer_profiles__onboarding_completed=True
            ).distinct().count()
            
            # Active Subscriptions
            active_subscriptions = Subscription.objects.filter(status='active').count()
            
            # New Signups - Last 7 days
            seven_days_ago = now - timedelta(days=7)
            new_customers = User.objects.filter(
                is_staff=False,
                is_superuser=False,
                date_joined__gte=seven_days_ago
            ).exclude(
                created_designer_profiles__isnull=False
            ).count()
            
            new_designers = User.objects.filter(
                created_designer_profiles__isnull=False,
                created_designer_profiles__onboarding_completed=True,
                date_joined__gte=seven_days_ago
            ).distinct().count()
            
            # Pending Tasks
            from Profiles.models import DesignerProfile
            pending_designer_approvals = DesignerProfile.objects.filter(
                status='pending',
                onboarding_completed=True
            ).count()
            
            pending_design_reviews = Product.objects.filter(
                status='draft'
            ).count()
            
            # Custom Orders requiring attention (pending or delayed)
            custom_orders_pending = CustomOrderRequest.objects.filter(
                status__in=['pending', 'in_progress']
            ).count()
            
            custom_orders_delayed = CustomOrderRequest.objects.filter(
                status='delayed'
            ).count()
            
            # Support Tickets
            open_support_tickets = SupportThread.objects.filter(
                status__in=['open', 'in_progress']
            ).count()
            
            open_report_issues = ReportIssue.objects.filter(
                status__in=['open', 'in_progress']
            ).count()
            
            # Pending Payouts
            from Wallet.models import WalletWithdrawalRequest
            pending_payouts = WalletWithdrawalRequest.objects.filter(
                status='pending'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            pending_payout_count = WalletWithdrawalRequest.objects.filter(
                status='pending'
            ).count()
            
            # Top Customers (by spending this month)
            top_customers = []
            customer_orders = Order.objects.filter(
                status='success',
                created_at__gte=month_start
            ).values('created_by').annotate(
                total_spent=Sum('total_amount'),
                order_count=Count('id')
            ).order_by('-total_spent')[:5]
            
            for order_data in customer_orders:
                try:
                    customer = User.objects.get(pk=order_data['created_by'])
                    top_customers.append({
                        'id': customer.id,
                        'name': customer.get_full_name() or customer.username,
                        'email': customer.email,
                        'total_spent': float(order_data['total_spent']),
                        'order_count': order_data['order_count']
                    })
                except User.DoesNotExist:
                    continue
            
            # Revenue trend (last 7 days)
            revenue_trend = []
            for i in range(6, -1, -1):
                day_date = (now - timedelta(days=i)).date()
                day_start = timezone.make_aware(datetime.combine(day_date, datetime.min.time()))
                day_end = day_start + timedelta(days=1) - timedelta(microseconds=1)
                day_revenue = Order.objects.filter(
                    status='success',
                    created_at__gte=day_start,
                    created_at__lte=day_end
                ).aggregate(total=Sum('total_amount'))['total'] or 0
                revenue_trend.append({
                    'date': day_date.strftime('%Y-%m-%d'),
                    'label': day_start.strftime('%a'),
                    'revenue': float(day_revenue)
                })
            
            summary_data = {
                'role': 'superadmin',
                'financial': {
                    'revenue_today': float(revenue_today),
                    'revenue_month': float(revenue_month),
                    'revenue_year': float(revenue_year),
                    'revenue_growth': round(revenue_growth, 2),
                    'net_revenue': float(net_revenue),
                    'total_refunds': float(total_refunds),
                    'avg_order_value': round(avg_order_value, 2),
                    'revenue_by_source': {
                        'plans': float(plan_revenue),
                        'designs': float(design_revenue),
                        'custom_orders': float(custom_order_revenue)
                    }
                },
                'transactions': {
                    'total': total_transactions,
                    'successful': successful_transactions,
                    'failed': failed_transactions,
                    'success_rate': round((successful_transactions / total_transactions * 100) if total_transactions > 0 else 0, 2)
                },
                'users': {
                    'total_customers': total_customers,
                    'total_designers': total_designers,
                    'new_customers_7d': new_customers,
                    'new_designers_7d': new_designers,
                    'active_subscriptions': active_subscriptions
                },
                'pending_tasks': {
                    'designer_approvals': pending_designer_approvals,
                    'design_reviews': pending_design_reviews,
                    'custom_orders': custom_orders_pending,
                    'custom_orders_delayed': custom_orders_delayed,
                    'support_tickets': open_support_tickets + open_report_issues
                },
                'payouts': {
                    'pending_amount': float(pending_payouts),
                    'pending_count': pending_payout_count
                },
                'top_customers': top_customers,
                'revenue_trend': revenue_trend
            }
        else:
            # ========== MODERATOR DASHBOARD ==========
            moderator_id = request.user.id
            today = now.date()
            
            # Today's Activity
            from Profiles.models import DesignerProfile
            # Count designers whose status was updated to 'verified' today
            designers_approved_today = DesignerProfile.objects.filter(
                status='verified',
                updated_at__gte=today_start,
                updated_at__lte=today_end
            ).count()
            
            # Note: 'rejected' status doesn't exist in DesignerProfile
            designers_rejected_today = 0
            
            designs_approved_today = DesignApproval.objects.filter(
                approved_by_id=moderator_id,
                action='approved',
                approved_at__gte=today_start,
                approved_at__lte=today_end
            ).count()
            
            designs_rejected_today = DesignApproval.objects.filter(
                approved_by_id=moderator_id,
                action='rejected',
                approved_at__gte=today_start,
                approved_at__lte=today_end
            ).count()
            
            custom_orders_completed_today = CustomOrderRequest.objects.filter(
                Q(assigned_to_id=moderator_id) | Q(updated_by_id=moderator_id),
                status='completed',
                completed_at__gte=today_start,
                completed_at__lte=today_end
            ).count()
            
            support_resolved_today = SupportThread.objects.filter(
                Q(assigned_to_id=moderator_id) | Q(resolved_by_id=moderator_id),
                status__in=['resolved', 'closed'],
                resolved_at__gte=today_start,
                resolved_at__lte=today_end
            ).count()
            
            # Pending Tasks
            from Profiles.models import DesignerProfile
            pending_designer_approvals = DesignerProfile.objects.filter(
                status='pending',
                onboarding_completed=True
            ).count()
            
            pending_design_reviews = Product.objects.filter(
                status='draft'
            ).count()
            
            custom_orders_assigned = CustomOrderRequest.objects.filter(
                assigned_to_id=moderator_id,
                status__in=['pending', 'in_progress']
            ).count()
            
            support_tickets_assigned = SupportThread.objects.filter(
                assigned_to_id=moderator_id,
                status__in=['open', 'in_progress']
            ).count()
            
            # Activity Summary
            total_activity_today = (
                designers_approved_today + designers_rejected_today +
                designs_approved_today + designs_rejected_today +
                custom_orders_completed_today + support_resolved_today
            )
            
            summary_data = {
                'role': 'moderator',
                'today_activity': {
                    'total': total_activity_today,
                    'designers_approved': designers_approved_today,
                    'designers_rejected': designers_rejected_today,
                    'designs_approved': designs_approved_today,
                    'designs_rejected': designs_rejected_today,
                    'custom_orders_completed': custom_orders_completed_today,
                    'support_resolved': support_resolved_today
                },
                'pending_tasks': {
                    'designer_approvals': pending_designer_approvals,
                    'design_reviews': pending_design_reviews,
                    'custom_orders': custom_orders_assigned,
                    'support_tickets': support_tickets_assigned,
                    'total': pending_designer_approvals + pending_design_reviews + custom_orders_assigned + support_tickets_assigned
                }
        }
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='other',
                description='Dashboard summary viewed',
                request=request,
                metadata={
                    'action': 'dashboard_viewed',
                    'role': admin_profile.admin_group
                }
            )
        except Exception as e:
            # Log error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)

        return Response({
            'message': 'Dashboard summary retrieved successfully',
            'data': summary_data
        })
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while retrieving dashboard summary',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary="Revenue Analytics",
    operation_description="Get revenue analytics and financial insights (SuperAdmin access only).",
    manual_parameters=[
        openapi.Parameter(
            'start_date',
            openapi.IN_QUERY,
            description='Start date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'end_date',
            openapi.IN_QUERY,
            description='End date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'report_type',
            openapi.IN_QUERY,
            description='Report type (daily, monthly, yearly, custom)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'include_refunds',
            openapi.IN_QUERY,
            description='Include refund data',
            type=openapi.TYPE_BOOLEAN
        ),
        openapi.Parameter(
            'group_by',
            openapi.IN_QUERY,
            description='Group by period (day, week, month, year)',
            type=openapi.TYPE_STRING
        )
    ],
    responses={
        200: openapi.Response(description="Revenue analytics retrieved successfully"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['Admin Analytics Revenue']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def revenue_analytics(request):
    """
    Get revenue analytics and financial insights.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin':
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while retrieving revenue analytics'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        serializer = RevenueAnalyticsSerializer(data=request.GET)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid parameters',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'Invalid request parameters'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        filters = serializer.validated_data
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        report_type = filters.get('report_type', 'custom')
        include_refunds = filters.get('include_refunds', True)
        group_by = filters.get('group_by', 'day')
        
        # Convert date to datetime if needed for consistency
        if start_date:
            from datetime import datetime
            if isinstance(start_date, str):
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                except ValueError:
                    pass
        if end_date:
            from datetime import datetime
            if isinstance(end_date, str):
                try:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                except ValueError:
                    pass
        
        # TODO: Implement actual revenue calculation
        # finance.services.get_total_revenue(start_date, end_date)
        revenue_data = {
            'total_revenue': 0.00,
            'plan_purchases_revenue': 0.00,
            'bundle_sales_revenue': 0.00,
            'design_sales_revenue': 0.00,
            'custom_orders_revenue': 0.00,
            'total_refunds': 0.00 if not include_refunds else 0.00,
            'net_revenue': 0.00,
            'total_transactions': 0,
            'successful_transactions': 0,
            'failed_transactions': 0,
            'refund_count': 0,
            'growth_rate': 0.00,
            'period_breakdown': []
        }
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='other',
                description='Revenue analytics viewed',
                request=request,
                metadata={
                    'action': 'revenue_analytics_viewed',
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None,
                    'report_type': report_type,
                    'include_refunds': include_refunds
                }
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)

        return Response({
            'message': 'Revenue analytics retrieved successfully',
            'data': revenue_data
        })
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while retrieving revenue analytics',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary="Top Performing Designs",
    operation_description="Get top performing designs analytics (SuperAdmin access only).",
    manual_parameters=[
        openapi.Parameter(
            'start_date',
            openapi.IN_QUERY,
            description='Start date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'end_date',
            openapi.IN_QUERY,
            description='End date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'limit',
            openapi.IN_QUERY,
            description='Number of top designs to return (1-100)',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by metric (revenue, sales, downloads, rating)',
            type=openapi.TYPE_STRING
        )
    ],
    responses={
        200: openapi.Response(description="Top designs analytics retrieved successfully"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['Admin Analytics Top Performers']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def top_designs_analytics(request):
    """
    Get top performing designs analytics.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin':
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = TopPerformersSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid parameters',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    filters = serializer.validated_data
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    limit = filters.get('limit', 10)
    sort_by = filters.get('sort_by', 'revenue')
    
    # TODO: Implement actual top designs calculation
    # analytics.services.get_top_designs(limit, start_date, end_date)
    top_designs = []
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='other',
            description='Top designs analytics viewed',
            request=request,
            metadata={
                'action': 'top_designs_analytics_viewed',
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'limit': limit,
                'sort_by': sort_by
            }
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

    return Response({
        'message': 'Top designs analytics retrieved successfully',
        'data': {
            'top_designs': top_designs,
            'total_count': len(top_designs),
            'period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            }
        }
    })

@swagger_auto_schema(
    method='get',
    operation_summary="Top Performing Designers",
    operation_description="Get top performing designers analytics (SuperAdmin access only).",
    manual_parameters=[
        openapi.Parameter(
            'start_date',
            openapi.IN_QUERY,
            description='Start date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'end_date',
            openapi.IN_QUERY,
            description='End date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'limit',
            openapi.IN_QUERY,
            description='Number of top designers to return (1-100)',
            type=openapi.TYPE_INTEGER
        ),
        openapi.Parameter(
            'sort_by',
            openapi.IN_QUERY,
            description='Sort by metric (revenue, sales, downloads, rating)',
            type=openapi.TYPE_STRING
        )
    ],
    responses={
        200: openapi.Response(description="Top designers analytics retrieved successfully"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['Admin Analytics Top Performers']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def top_designers_analytics(request):
    """
    Get top performing designers analytics.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin':
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while retrieving top designers analytics'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        serializer = TopPerformersSerializer(data=request.GET)
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid parameters',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'Invalid request parameters'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        filters = serializer.validated_data
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        limit = filters.get('limit', 10)
        sort_by = filters.get('sort_by', 'revenue')
        
        # Convert date to datetime if needed for consistency
        if start_date:
            from datetime import datetime
            if isinstance(start_date, str):
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                except ValueError:
                    pass
        if end_date:
            from datetime import datetime
            if isinstance(end_date, str):
                try:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                except ValueError:
                    pass
        
        # TODO: Implement actual top designers calculation
        # analytics.services.get_top_designers(limit, start_date, end_date)
        top_designers = []
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='other',
                description='Top designers analytics viewed',
                request=request,
                metadata={
                    'action': 'top_designers_analytics_viewed',
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None,
                    'limit': limit,
                    'sort_by': sort_by
                }
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)

        return Response({
            'message': 'Top designers analytics retrieved successfully',
            'data': {
                'top_designers': top_designers,
                'total_count': len(top_designers),
                'period': {
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None
                }
            }
        })
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while retrieving top designers analytics',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_summary="Active User Statistics",
    operation_description="Get active user statistics and engagement metrics (SuperAdmin access only).",
    manual_parameters=[
        openapi.Parameter(
            'start_date',
            openapi.IN_QUERY,
            description='Start date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'end_date',
            openapi.IN_QUERY,
            description='End date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'report_type',
            openapi.IN_QUERY,
            description='Report type (daily, weekly, monthly, custom)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'include_churn',
            openapi.IN_QUERY,
            description='Include churn rate calculation',
            type=openapi.TYPE_BOOLEAN
        ),
        openapi.Parameter(
            'include_engagement',
            openapi.IN_QUERY,
            description='Include engagement metrics',
            type=openapi.TYPE_BOOLEAN
        )
    ],
    responses={
        200: openapi.Response(description="User statistics retrieved successfully"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['Admin Analytics User Stats']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_statistics(request):
    """
    Get active user statistics and engagement metrics.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin':
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = UserStatsSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid parameters',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    filters = serializer.validated_data
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    report_type = filters.get('report_type', 'custom')
    include_churn = filters.get('include_churn', True)
    include_engagement = filters.get('include_engagement', True)
    
    # TODO: Implement actual user statistics calculation
    # user_activity.services.get_active_user_stats(start_date, end_date)
    user_stats = {
        'total_active_users': 0,
        'new_signups': 0,
        'returning_users': 0,
        'customer_count': 0,
        'designer_count': 0,
        'active_subscriptions': 0,
        'subscription_renewals': 0,
        'expired_subscriptions': 0,
        'churn_rate': 0.00,
        'total_logins': 0,
        'average_session_duration': 0.00,
        'page_views': 0,
        'engagement_metrics': {}
    }
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='other',
            description='User statistics viewed',
            request=request,
            metadata={
                'action': 'user_statistics_viewed',
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'report_type': report_type,
                'include_churn': include_churn,
                'include_engagement': include_engagement
            }
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

    return Response({
        'message': 'User statistics retrieved successfully',
        'data': user_stats
    })

@swagger_auto_schema(
    method='get',
    operation_summary="Growth Charts Data",
    operation_description="Get growth charts data for visual analytics (SuperAdmin access only).",
    manual_parameters=[
        openapi.Parameter(
            'chart_type',
            openapi.IN_QUERY,
            description='Chart type (sales_growth, subscription_growth, user_registrations, etc.)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'start_date',
            openapi.IN_QUERY,
            description='Start date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'end_date',
            openapi.IN_QUERY,
            description='End date for analytics (YYYY-MM-DD)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'group_by',
            openapi.IN_QUERY,
            description='Group by period (day, week, month)',
            type=openapi.TYPE_STRING
        ),
        openapi.Parameter(
            'include_secondary',
            openapi.IN_QUERY,
            description='Include secondary metrics',
            type=openapi.TYPE_BOOLEAN
        )
    ],
    responses={
        200: openapi.Response(description="Growth charts data retrieved successfully"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['Admin Analytics Growth Charts']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def growth_charts(request):
    """
    Get growth charts data for visual analytics.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin':
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = GrowthChartSerializer(data=request.GET)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid parameters',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    filters = serializer.validated_data
    chart_type = filters.get('chart_type')
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    group_by = filters.get('group_by', 'day')
    include_secondary = filters.get('include_secondary', False)
    
    # Get growth chart data
    charts_query = GrowthChart.objects.all()
    
    if chart_type:
        charts_query = charts_query.filter(chart_type=chart_type)
    
    if start_date:
        charts_query = charts_query.filter(date__gte=start_date.date())
    
    if end_date:
        charts_query = charts_query.filter(date__lte=end_date.date())
    
    charts_data = charts_query.order_by('date')
    serializer_data = GrowthChartSerializer(charts_data, many=True).data
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='other',
            description='Growth charts viewed',
            request=request,
            metadata={
                'action': 'growth_charts_viewed',
                'chart_type': chart_type,
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'group_by': group_by,
                'include_secondary': include_secondary
            }
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

    return Response({
        'message': 'Growth charts data retrieved successfully',
        'data': {
            'charts': serializer_data,
            'total_points': len(serializer_data),
            'period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            }
        }
    })

@swagger_auto_schema(
    method='post',
    operation_summary="Export Report",
    operation_description="Export analytics report as CSV/Excel (SuperAdmin access only).",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'export_type': openapi.Schema(type=openapi.TYPE_STRING, description='Export type'),
            'export_format': openapi.Schema(type=openapi.TYPE_STRING, description='Export format (csv, xlsx)'),
            'start_date': openapi.Schema(type=openapi.TYPE_STRING, description='Start date'),
            'end_date': openapi.Schema(type=openapi.TYPE_STRING, description='End date'),
            'filters': openapi.Schema(type=openapi.TYPE_OBJECT, description='Additional filters'),
            'include_charts': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Include charts')
        }
    ),
    responses={
        202: openapi.Response(description="Export request submitted successfully"),
        400: openapi.Response(description="Invalid export parameters"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['Admin Analytics Export']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_report(request):
    """
    Export analytics report as CSV/Excel.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin':
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = ExportRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'error': 'Invalid export parameters',
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    export_data = serializer.validated_data
    
    try:
        # Create export record
        export = ReportExport.objects.create(
            export_type=export_data['export_type'],
            export_format=export_data['export_format'],
            start_date=export_data.get('start_date'),
            end_date=export_data.get('end_date'),
            filters=export_data.get('filters', {}),
            created_by=request.user
        )
        
        # TODO: Implement Celery task for async export
        # export_task = generate_report_export.delay(export.id)
        # export.celery_task_id = export_task.id
        # export.save()
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='data_export',
                description='Report export requested',
                request=request,
                metadata={
                    'export_id': export.id,
                    'export_type': export.export_type,
                    'export_format': export.export_format
                }
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)

        return Response({
            'message': 'Export request submitted successfully',
            'data': {
                'export_id': export.id,
                'status': export.status,
                'estimated_completion': '5-10 minutes'
            }
        }, status=status.HTTP_202_ACCEPTED)
        
    except Exception as e:
        return Response({
            'error': f'Export request failed: {str(e)}'
        }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_summary="Export Status",
    operation_description="Check export status and download link (SuperAdmin access only).",
    responses={
        200: openapi.Response(description="Export status retrieved successfully"),
        404: openapi.Response(description="Export not found"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['Admin Analytics Export']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_status(request, export_id):
    """
    Check export status and download link.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin':
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        export = ReportExport.objects.get(id=export_id, created_by=request.user)
    except ReportExport.DoesNotExist:
        return Response({
            'error': 'Export not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = ReportExportSerializer(export)
    
    # Log activity
    try:
        AdminActivityLog.log_activity(
            user=request.user,
            activity_type='data_export',
            description='Export status viewed',
            request=request,
            metadata={
                'action': 'export_status_viewed',
                'export_id': export_id
            }
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)

    return Response({
        'message': 'Export status retrieved successfully',
        'data': serializer.data
    })

@swagger_auto_schema(
    method='get',
    operation_summary="Moderator Daily Report",
    operation_description="Get daily activity report for a specific moderator (SuperAdmin access only).",
    manual_parameters=[
        openapi.Parameter(
            'date',
            openapi.IN_QUERY,
            description='Date for the report (YYYY-MM-DD). Defaults to today.',
            type=openapi.TYPE_STRING
        ),
    ],
    responses={
        200: openapi.Response(description="Moderator daily report retrieved successfully"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required"),
        404: openapi.Response(description="Moderator not found")
    },
    tags=['Admin Analytics Reports']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def moderator_daily_report(request, moderator_id):
    """
    Get daily activity report for a specific moderator.
    """
    try:
        admin_profile = AdminUserProfile.objects.get(user=request.user)
        if admin_profile.admin_group != 'superadmin':
            return Response({
                'error': 'SuperAdmin privileges required'
            }, status=status.HTTP_403_FORBIDDEN)
    except AdminUserProfile.DoesNotExist:
        return Response({
            'error': 'Admin profile required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from django.contrib.auth.models import User
        from datetime import datetime, timedelta
        from django.db.models import Q, Count
        from CoreAdmin.models import DesignApproval
        from Profiles.models import DesignerProfile
        from CustomRequests.models import CustomOrderRequest
        from Feedback.models import SupportThread, ReportIssue
        from Coupons.models import Coupon, CouponUsage
        
        # Get moderator
        try:
            moderator = User.objects.get(pk=moderator_id)
            moderator_profile = AdminUserProfile.objects.get(user=moderator)
            if moderator_profile.admin_group != 'moderator':
                return Response({
                    'error': 'User is not a moderator'
                }, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({
                'error': 'Moderator not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except AdminUserProfile.DoesNotExist:
            return Response({
                'error': 'Moderator profile not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Get date from query params or use today
        date_str = request.GET.get('date')
        if date_str:
            try:
                report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            report_date = timezone.now().date()
        
        # Calculate date range for the day
        start_datetime = timezone.make_aware(datetime.combine(report_date, datetime.min.time()))
        end_datetime = start_datetime + timedelta(days=1) - timedelta(microseconds=1)
        
        # 1. Designers Approved/Rejected
        # Count designers whose status was updated to 'verified' today by this moderator
        # Note: We track by updated_at and updated_by, but DesignerProfile doesn't have approved_by
        # So we count all designers updated to verified today (may not be accurate per moderator)
        designers_approved = DesignerProfile.objects.filter(
            status='verified',
            updated_at__gte=start_datetime,
            updated_at__lte=end_datetime,
            updated_by_id=moderator_id
        ).count()
        
        # Note: 'rejected' status doesn't exist in DesignerProfile
        designers_rejected = 0
        
        # Get detailed list
        designers_approved_list = DesignerProfile.objects.filter(
            status='verified',
            updated_at__gte=start_datetime,
            updated_at__lte=end_datetime,
            updated_by_id=moderator_id
        ).select_related('created_by').values(
            'id', 'created_by_id', 'updated_at'
        )[:50]  # Limit to 50 for performance
        
        designers_rejected_list = []  # No rejected status
        
        # 2. Designs Approved/Rejected
        designs_approved = DesignApproval.objects.filter(
            approved_by_id=moderator_id,
            action='approved',
            approved_at__gte=start_datetime,
            approved_at__lte=end_datetime
        ).count()
        
        designs_rejected = DesignApproval.objects.filter(
            approved_by_id=moderator_id,
            action='rejected',
            approved_at__gte=start_datetime,
            approved_at__lte=end_datetime
        ).count()
        
        # Get detailed list
        designs_approved_list = DesignApproval.objects.filter(
            approved_by_id=moderator_id,
            action='approved',
            approved_at__gte=start_datetime,
            approved_at__lte=end_datetime
        ).values(
            'id', 'product_id', 'approved_at', 'admin_notes'
        )[:50]
        
        designs_rejected_list = DesignApproval.objects.filter(
            approved_by_id=moderator_id,
            action='rejected',
            approved_at__gte=start_datetime,
            approved_at__lte=end_datetime
        ).values(
            'id', 'product_id', 'approved_at', 'rejection_reason', 'admin_notes'
        )[:50]
        
        # 3. Custom Orders
        # Orders assigned to or updated by this moderator
        custom_orders_completed = CustomOrderRequest.objects.filter(
            Q(assigned_to_id=moderator_id) | Q(updated_by_id=moderator_id),
            status='completed',
            completed_at__gte=start_datetime,
            completed_at__lte=end_datetime
        ).count()
        
        custom_orders_interacted = CustomOrderRequest.objects.filter(
            Q(assigned_to_id=moderator_id) | Q(updated_by_id=moderator_id),
            updated_at__gte=start_datetime,
            updated_at__lte=end_datetime
        ).exclude(status='pending').count()
        
        # Get detailed list with rejection reasons
        custom_orders_list = CustomOrderRequest.objects.filter(
            Q(assigned_to_id=moderator_id) | Q(updated_by_id=moderator_id),
            updated_at__gte=start_datetime,
            updated_at__lte=end_datetime
        ).values(
            'id', 'title', 'status', 'updated_at', 'cancellation_reason', 'refund_reason'
        )[:50]
        
        # 4. Support Tickets
        support_resolved = SupportThread.objects.filter(
            Q(assigned_to_id=moderator_id) | Q(resolved_by_id=moderator_id),
            status__in=['resolved', 'closed'],
            resolved_at__gte=start_datetime,
            resolved_at__lte=end_datetime
        ).count()
        
        support_rejected = SupportThread.objects.filter(
            assigned_to_id=moderator_id,
            status='closed',
            resolved_at__gte=start_datetime,
            resolved_at__lte=end_datetime
        ).exclude(resolution__isnull=False).count()
        
        support_interacted = SupportThread.objects.filter(
            Q(assigned_to_id=moderator_id) | Q(resolved_by_id=moderator_id),
            updated_at__gte=start_datetime,
            updated_at__lte=end_datetime
        ).count()
        
        # Get detailed list
        support_tickets_list = SupportThread.objects.filter(
            Q(assigned_to_id=moderator_id) | Q(resolved_by_id=moderator_id),
            updated_at__gte=start_datetime,
            updated_at__lte=end_datetime
        ).values(
            'id', 'subject', 'status', 'priority', 'updated_at', 'resolution'
        )[:50]
        
        # Report Issues
        report_issues_resolved = ReportIssue.objects.filter(
            resolved_by_id=moderator_id,
            status__in=['resolved', 'closed'],
            resolved_at__gte=start_datetime,
            resolved_at__lte=end_datetime
        ).count()
        
        report_issues_list = ReportIssue.objects.filter(
            resolved_by_id=moderator_id,
            resolved_at__gte=start_datetime,
            resolved_at__lte=end_datetime
        ).values(
            'id', 'title', 'status', 'priority', 'resolved_at', 'resolution'
        )[:50]
        
        # 5. Coupons
        coupons_added = Coupon.objects.filter(
            created_by_id=moderator_id,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        ).count()
        
        # Get coupon usage count for coupons created by this moderator
        coupons_created_today = Coupon.objects.filter(
            created_by_id=moderator_id,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        )
        coupon_usage_count = CouponUsage.objects.filter(
            coupon_id__in=coupons_created_today.values_list('id', flat=True)
        ).count()
        
        # Get detailed list
        coupons_list = Coupon.objects.filter(
            created_by_id=moderator_id,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        ).values(
            'id', 'name', 'code', 'created_at'
        )[:50]
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='other',
                description=f'Viewed daily report for moderator {moderator.username}',
                request=request,
                metadata={
                    'action': 'moderator_daily_report_viewed',
                    'moderator_id': moderator_id,
                    'report_date': report_date.isoformat()
                }
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)

        return Response({
            'message': 'Moderator daily report retrieved successfully',
            'data': {
                'moderator': {
                    'id': moderator.id,
                    'username': moderator.username,
                    'email': moderator.email,
                    'first_name': moderator.first_name,
                    'last_name': moderator.last_name,
                },
                'report_date': report_date.isoformat(),
                'designers': {
                    'approved': designers_approved,
                    'rejected': designers_rejected,
                    'approved_list': list(designers_approved_list),
                    'rejected_list': list(designers_rejected_list),
                },
                'designs': {
                    'approved': designs_approved,
                    'rejected': designs_rejected,
                    'approved_list': list(designs_approved_list),
                    'rejected_list': list(designs_rejected_list),
                },
                'custom_orders': {
                    'completed': custom_orders_completed,
                    'interacted': custom_orders_interacted,
                    'list': list(custom_orders_list),
                },
                'support': {
                    'resolved': support_resolved + report_issues_resolved,
                    'rejected': support_rejected,
                    'interacted': support_interacted + report_issues_resolved,
                    'support_threads': list(support_tickets_list),
                    'report_issues': list(report_issues_list),
                },
                'coupons': {
                    'added': coupons_added,
                    'usage_count': coupon_usage_count,
                    'list': list(coupons_list),
                },
            }
        })
        
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)

        return Response({
            'error': 'An error occurred while retrieving moderator daily report',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
