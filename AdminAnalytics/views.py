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
    operation_description="Get dashboard summary with key metrics (SuperAdmin access only).",
    responses={
        200: openapi.Response(description="Dashboard summary retrieved successfully"),
        403: openapi.Response(description="Access denied - SuperAdmin privileges required")
    },
    tags=['Admin Analytics Dashboard']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """
    Get dashboard summary with key metrics.
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
        logger.error(f'Error in dashboard_summary: {e}')
        return Response({
            'error': 'An error occurred while retrieving dashboard summary'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    try:
        # TODO: Implement actual data aggregation
        # This is a placeholder implementation
        summary_data = {
            'total_revenue': 0.00,
            'total_users': 0,
            'total_designs': 0,
            'total_downloads': 0,
            'active_subscriptions': 0,
            'growth_rate': 0.00,
            'top_design': {},
            'top_designer': {},
            'recent_activity': []
        }
        
        # Log activity
        try:
            AdminActivityLog.log_activity(
                user=request.user,
                activity_type='other',
                description='Dashboard summary viewed',
                request=request,
                metadata={'action': 'dashboard_viewed'}
            )
        except Exception as e:
            # Log error but don't fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Failed to log activity: {e}')
        
        return Response({
            'message': 'Dashboard summary retrieved successfully',
            'data': summary_data
        })
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f'Error in dashboard_summary: {e}')
        logger.error(traceback.format_exc())
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
        logger.error(f'Error in revenue_analytics: {e}')
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
        logger.error(f'Error validating revenue_analytics request: {e}')
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
            logger.error(f'Failed to log activity: {e}')
        
        return Response({
            'message': 'Revenue analytics retrieved successfully',
            'data': revenue_data
        })
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f'Error in revenue_analytics: {e}')
        logger.error(traceback.format_exc())
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
        logger.error(f'Failed to log activity: {e}')
    
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
        logger.error(f'Error in top_designers_analytics: {e}')
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
        logger.error(f'Error validating top_designers_analytics request: {e}')
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
            logger.error(f'Failed to log activity: {e}')
        
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
        logger.error(f'Error in top_designers_analytics: {e}')
        logger.error(traceback.format_exc())
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
        logger.error(f'Failed to log activity: {e}')
    
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
        logger.error(f'Failed to log activity: {e}')
    
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
            logger.error(f'Failed to log activity: {e}')
        
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
        logger.error(f'Failed to log activity: {e}')
    
    return Response({
        'message': 'Export status retrieved successfully',
        'data': serializer.data
    })
