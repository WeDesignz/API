from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Q, Count, Avg
from django.conf import settings
from .models import FeedbackReview, FeedbackQuestion, ReportIssue, SupportThread, SupportMessage, FAQ, FAQTag
from .serializers import (
    FeedbackReviewSerializer, FeedbackReviewListSerializer,
    SupportThreadSerializer, SupportThreadListSerializer, SupportThreadCreateSerializer,
    SupportMessageSerializer, SupportMessageCreateSerializer,
    FAQSerializer, FAQListSerializer, FAQTagSerializer, FAQTagListSerializer
)
from CoreAdmin.models import DesignerNotification
from Profiles.serializers import DesignerNotificationSerializer
from common.relations import get_related
from django.utils import timezone


@swagger_auto_schema(
    method='get',
    operation_summary='Get Feedback Reviews',
    operation_description='Get all feedback reviews with ratings and comments.',
    responses={
        200: openapi.Response(
            description='Feedback reviews retrieved successfully',
            examples={
                'application/json': {
                    'feedbacks': [
                        {
                            'id': 1,
                            'rating': 5,
                            'comment': 'Excellent service and quality designs!',
                            'user': {
                                'id': 1,
                                'username': 'john_doe',
                                'first_name': 'John',
                                'last_name': 'Doe'
                            },
                            'created_at': '2024-01-01T00:00:00Z'
                        }
                    ],
                    'total_feedbacks': 1
                }
            }
        )
    },
    tags=['Feedback']
)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def feedback_list(request):
    """
    Get feedback list or create new feedback.
    """
    if request.method == 'GET':
        feedbacks = FeedbackReview.objects.all().order_by('-created_at')
        return Response({
            'feedbacks': FeedbackReviewListSerializer(feedbacks, many=True).data,
            'total_feedbacks': feedbacks.count()
        })
    
    elif request.method == 'POST':
        serializer = FeedbackReviewSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response({
                'message': 'Feedback submitted successfully',
                'feedback': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_summary='Feedback Detail',
    operation_description='Feedback Detail endpoint',
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
def feedback_detail(request, feedback_id):
    """
    Get, update, or delete specific feedback.
    """
    try:
        feedback = FeedbackReview.objects.get(id=feedback_id, created_by=request.user)
    except FeedbackReview.DoesNotExist:
        return Response({
            'error': 'Feedback not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        return Response({
            'feedback': FeedbackReviewSerializer(feedback).data
        })
    
    elif request.method == 'PUT':
        serializer = FeedbackReviewSerializer(feedback, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(updated_by=request.user)
            return Response({
                'message': 'Feedback updated successfully',
                'feedback': serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        feedback.delete()
        return Response({
            'message': 'Feedback deleted successfully'
        })


@swagger_auto_schema(
    method='post',
    operation_summary='Submit Feedback',
    operation_description='Submit Feedback endpoint',
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
def submit_feedback(request):
    """
    Submit feedback for a product or service.
    """
    serializer = FeedbackSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(created_by=request.user)
        return Response({
            'message': 'Feedback submitted successfully',
            'feedback': serializer.data
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_summary='My Feedback',
    operation_description='My Feedback endpoint',
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
def my_feedback(request):
    """
    Get user's feedback history.
    """
    feedbacks = FeedbackReview.objects.filter(created_by=request.user).order_by('-created_at')
    return Response({
        'my_feedbacks': FeedbackReviewListSerializer(feedbacks, many=True).data,
        'total_feedbacks': feedbacks.count()
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Feedback Stats',
    operation_description='Feedback Stats endpoint',
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
def feedback_stats(request):
    """
    Get feedback statistics.
    """
    total_feedbacks = FeedbackReview.objects.all().count()
    average_rating = FeedbackReview.objects.filter(
        rating__isnull=False
    ).aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
    
    return Response({
        'total_feedbacks': total_feedbacks,
        'average_rating': round(average_rating, 2),
        'rating_distribution': {
            '5_star': FeedbackReview.objects.filter(rating=5).count(),
            '4_star': FeedbackReview.objects.filter(rating=4).count(),
            '3_star': FeedbackReview.objects.filter(rating=3).count(),
            '2_star': FeedbackReview.objects.filter(rating=2).count(),
            '1_star': FeedbackReview.objects.filter(rating=1).count(),
        }
    })


# ==================== DESIGNER CONSOLE - NOTIFICATIONS & MESSAGING ====================

@swagger_auto_schema(
    method='get',
    operation_summary='Get Designer Notifications',
    operation_description='Get designer notifications with filtering and pagination.',
    responses={
        200: openapi.Response(description='Notifications retrieved successfully'),
        403: openapi.Response(description='Access denied')
    },
    tags=['Notifications']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def designer_notifications(request):
    """
    Get designer's notifications with filtering and pagination.
    """
    try:
        from django.core.paginator import Paginator
        
        # Get query parameters
        status_filter = request.GET.get('status', 'all')  # 'unread', 'read', 'all'
        notification_type = request.GET.get('type')
        try:
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 20))
        except (ValueError, TypeError):
            page = 1
            page_size = 20
        
        # Get notifications for the user via relation system
        notifications = get_related(request.user, 'User:DesignerNotification', DesignerNotification)
        
        # Apply status filter
        if status_filter == 'unread':
            notifications = notifications.filter(is_read=False)
        elif status_filter == 'read':
            notifications = notifications.filter(is_read=True)
        
        # Apply type filter
        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)
        
        # Order by created_at descending
        notifications = notifications.order_by('-created_at')
        
        # Get counts before pagination
        total_count = notifications.count()
        unread_count = get_related(request.user, 'User:DesignerNotification', DesignerNotification).filter(is_read=False).count()
        
        # Pagination
        paginator = Paginator(notifications, page_size)
        page_obj = paginator.get_page(page)
        
        # Serialize notifications
        serializer = DesignerNotificationSerializer(page_obj.object_list, many=True)
        
        notifications_data = {
            'notifications': serializer.data,
            'unread_count': unread_count,
            'total_count': total_count,
            'current_page': page,
            'total_pages': paginator.num_pages,
            'filters_applied': {
                'status': status_filter,
                'type': notification_type
            }
        }
        
        return Response(notifications_data)
    except Exception as e:
        return Response({
            'error': 'An error occurred while retrieving notifications',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_statistics(request):
    """
    Get notification statistics (unread count, total count, etc.)
    """
    try:
        # Get all notifications for the user
        notifications = get_related(request.user, 'User:DesignerNotification', DesignerNotification)
        
        # Calculate statistics
        unread_count = notifications.filter(is_read=False).count()
        total_count = notifications.count()
        
        # Count by type
        by_type = {}
        for notif_type, _ in DesignerNotification.NOTIFICATION_TYPES:
            count = notifications.filter(notification_type=notif_type).count()
            if count > 0:
                by_type[notif_type] = count
        
        stats_data = {
            'unread_count': unread_count,
            'total_count': total_count,
            'by_type': by_type,
            'by_priority': {}  # Not used in current model
        }
        
        return Response(stats_data)
    except Exception as e:
        return Response({
            'error': 'An error occurred while retrieving statistics',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_summary='Mark Notification Read',
    operation_description='Mark Notification Read endpoint',
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
def mark_notification_read(request, notification_id):
    """
    Mark a specific notification as read.
    """
    try:
        # Get notifications for the user via relation system
        user_notifications = get_related(request.user, 'User:DesignerNotification', DesignerNotification)
        
        try:
            notification = user_notifications.get(id=notification_id)
        except DesignerNotification.DoesNotExist:
            return Response({
                'error': 'Notification not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Mark as read
        notification.mark_as_read()
        
        return Response({
            'message': 'Notification marked as read'
        })
    except Exception as e:
        return Response({
            'error': 'An error occurred while marking notification as read',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='post',
    operation_summary='Mark All Notifications Read',
    operation_description='Mark All Notifications Read endpoint',
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
def mark_all_notifications_read(request):
    """
    Mark all notifications as read for the designer.
    """
    try:
        # Get all unread notifications for the user
        user_notifications = get_related(request.user, 'User:DesignerNotification', DesignerNotification)
        unread_notifications = user_notifications.filter(is_read=False)
        
        # Mark all as read
        count = unread_notifications.update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return Response({
            'message': 'All notifications marked as read',
            'count': count
        })
    except Exception as e:
        return Response({
            'error': 'An error occurred while marking all notifications as read',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_summary='Notification Count',
    operation_description='Notification Count endpoint',
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
def notification_count(request):
    """
    Get unread notification count for the designer.
    """
    try:
        # Get unread notifications for the user
        user_notifications = get_related(request.user, 'User:DesignerNotification', DesignerNotification)
        unread_count = user_notifications.filter(is_read=False).count()
        
        return Response({
            'unread_count': unread_count
        })
    except Exception as e:
        return Response({
            'error': 'An error occurred while retrieving notification count',
            'details': str(e) if settings.DEBUG else None,
            'unread_count': 0
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_summary='Support Messages',
    operation_description='Support Messages endpoint',
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

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def support_messages(request):
    """
    Get or create support messages between designer and admin.
    """
    if request.method == 'GET':
        # TODO: Get support messages from SupportMessage model
        # messages = SupportMessage.objects.filter(
        #     Q(sender=request.user) | Q(recipient=request.user)
        # ).order_by('-created_at')
        
        support_messages = {
            'messages': [],  # TODO: Serialize messages
            'total_messages': 0,
            'unread_count': 0
        }
        
        return Response(support_messages)
    
    elif request.method == 'POST':
        # Create new support message
        message_text = request.data.get('message')
        subject = request.data.get('subject', 'Support Request')
        priority = request.data.get('priority', 'medium')
        
        if not message_text:
            return Response({
                'error': 'Message text is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # TODO: Create support message
        # support_message = SupportMessage.objects.create(
        #     sender=request.user,
        #     recipient=get_admin_user(),  # TODO: Get admin user
        #     subject=subject,
        #     message=message_text,
        #     priority=priority
        # )
        
        # TODO: Send notification to admin
        # notifications.tasks.send_support_message_notification(support_message)
        
        return Response({
            'message': 'Support message sent successfully',
            'message_id': 'SUPPORT_MSG_123'  # TODO: Return actual message ID
        }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='get',
    operation_summary='Get Support Thread Messages',
    operation_description='Get messages for a specific support thread.',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'thread_id': 1,
                    'subject': 'Support Request',
                    'status': 'open',
                    'messages': []
                }
            }
        ),
        404: openapi.Response(description='Thread not found')
    },
    tags=['Support']
)
@swagger_auto_schema(
    method='post',
    operation_summary='Send Message to Thread',
    operation_description='Add a message to a support thread.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'message': openapi.Schema(type=openapi.TYPE_STRING, description='Message text')
        }
    ),
    responses={
        201: openapi.Response(description='Message sent successfully'),
        400: openapi.Response(description='Bad request')
    },
    tags=['Support']
)
@swagger_auto_schema(
    method='patch',
    operation_summary='Update Support Thread',
    operation_description='Update support thread status or other fields.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'status': openapi.Schema(type=openapi.TYPE_STRING, enum=['open', 'in_progress', 'resolved', 'closed'], description='Thread status'),
            'priority': openapi.Schema(type=openapi.TYPE_STRING, enum=['low', 'medium', 'high', 'urgent'], description='Thread priority'),
            'assigned_to': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID to assign thread to'),
            'resolution': openapi.Schema(type=openapi.TYPE_STRING, description='Resolution notes')
        }
    ),
    responses={
        200: openapi.Response(description='Thread updated successfully'),
        400: openapi.Response(description='Bad request'),
        403: openapi.Response(description='Permission denied')
    },
    tags=['Support']
)
@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAuthenticated])
def support_thread(request, thread_id):
    """
    Get or add messages to a specific support thread.
    """
    try:
        thread = SupportThread.objects.select_related('created_by', 'assigned_to').prefetch_related('messages__sender').get(id=thread_id)
        
        # Check if user has access to this thread
        if thread.created_by != request.user and not (request.user.is_staff or request.user.is_superuser):
            return Response({
                'error': 'You do not have permission to access this thread'
            }, status=status.HTTP_403_FORBIDDEN)
    except SupportThread.DoesNotExist:
        return Response({
            'error': 'Support thread not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        # Get messages for this thread
        messages = thread.messages.select_related('sender').all().order_by('created_at')
        
        # Mark messages as read for the requesting user (if they're not the sender)
        for message in messages:
            if message.sender != request.user and not message.read_at:
                message.mark_as_read(request.user)
        
        thread_data = {
            'thread_id': thread.id,
            'subject': thread.subject,
            'status': thread.status,
            'priority': thread.priority,
            'category': thread.category,
            'messages': SupportMessageSerializer(messages, many=True).data
        }
        
        return Response(thread_data)
    
    elif request.method == 'POST':
        # Add message to thread
        message_text = request.data.get('message')
        
        if not message_text:
            return Response({
                'error': 'Message text is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create message
        serializer = SupportMessageCreateSerializer(
            data={'thread': thread.id, 'message': message_text},
            context={'request': request}
        )
        
        if serializer.is_valid():
            message = serializer.save()
            return Response({
                'message': 'Message sent successfully',
                'message_id': message.id
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'error': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'PATCH':
        # Update thread (status, priority, assigned_to, etc.)
        # Only staff/admin can update threads
        if not (request.user.is_staff or request.user.is_superuser):
            return Response({
                'error': 'You do not have permission to update this thread'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get fields to update
        status_value = request.data.get('status')
        priority_value = request.data.get('priority')
        assigned_to_id = request.data.get('assigned_to')
        resolution_text = request.data.get('resolution')
        
        # Update status
        if status_value:
            if status_value not in ['open', 'in_progress', 'resolved', 'closed']:
                return Response({
                    'error': f'Invalid status: {status_value}. Must be one of: open, in_progress, resolved, closed'
                }, status=status.HTTP_400_BAD_REQUEST)
            thread.status = status_value
            
            # If resolving, set resolved_by and resolved_at
            if status_value == 'resolved':
                thread.resolved_by = request.user
                from django.utils import timezone
                thread.resolved_at = timezone.now()
        
        # Update priority
        if priority_value:
            if priority_value not in ['low', 'medium', 'high', 'urgent']:
                return Response({
                    'error': f'Invalid priority: {priority_value}. Must be one of: low, medium, high, urgent'
                }, status=status.HTTP_400_BAD_REQUEST)
            thread.priority = priority_value
        
        # Update assigned_to
        if assigned_to_id is not None:
            if assigned_to_id:
                try:
                    from django.contrib.auth.models import User
                    assigned_user = User.objects.get(id=assigned_to_id)
                    if not (assigned_user.is_staff or assigned_user.is_superuser):
                        return Response({
                            'error': 'Assigned user must be a staff member'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    thread.assigned_to = assigned_user
                except User.DoesNotExist:
                    return Response({
                        'error': f'User with ID {assigned_to_id} not found'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:
                thread.assigned_to = None
        
        # Update resolution
        if resolution_text is not None:
            thread.resolution = resolution_text
        
        thread.save()
        
        # Serialize and return updated thread
        serializer = SupportThreadSerializer(thread, context={'request': request})
        return Response({
            'message': 'Thread updated successfully',
            'thread': serializer.data
        }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    operation_summary='Get Support Threads',
    operation_description='Get all support threads for the authenticated user.',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'threads': [],
                    'total_threads': 0,
                    'open_threads': 0,
                    'closed_threads': 0
                }
            }
        )
    },
    tags=['Support']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def support_threads(request):
    """
    Get all support threads for the authenticated user.
    For customers: only shows customer tickets (thread_type='customer')
    For designers: only shows designer tickets (thread_type='designer')
    For admins: shows all tickets
    Can filter by thread_type query parameter: ?thread_type=customer or ?thread_type=designer
    """
    from Profiles.models import DesignerProfile
    from django.db.models import Q
    
    # Get requested thread_type from query parameter
    requested_thread_type = request.GET.get('thread_type', None)
    
    # Get threads created by the user (or all threads if staff/admin)
    if request.user.is_staff or request.user.is_superuser:
        # Admins see all threads, but can filter by thread_type if requested
        threads = SupportThread.objects.select_related('created_by', 'assigned_to').prefetch_related('messages__sender').all()
        if requested_thread_type in ['customer', 'designer']:
            threads = threads.filter(thread_type=requested_thread_type)
        threads = threads.order_by('-updated_at')
    else:
        # Non-admin users: filter by user and thread_type
        threads = SupportThread.objects.select_related('created_by', 'assigned_to').prefetch_related('messages__sender').filter(
            created_by=request.user
        )
        
        # Determine user's context if thread_type not explicitly requested
        if not requested_thread_type:
            # Check if user is a verified designer
            is_designer = False
            try:
                designer_profile = DesignerProfile.objects.filter(
                    created_by=request.user
                ).first()
                if designer_profile and (designer_profile.status == 'verified' or designer_profile.onboarding_completed):
                    is_designer = True
            except Exception:
                pass
            
            # Filter by thread_type based on user context
            if is_designer:
                # Designer accessing - show only designer tickets
                threads = threads.filter(thread_type='designer')
            else:
                # Customer accessing - show only customer tickets
                threads = threads.filter(thread_type='customer')
        else:
            # Explicit thread_type requested - filter by it
            if requested_thread_type in ['customer', 'designer']:
                threads = threads.filter(thread_type=requested_thread_type)
        
        threads = threads.order_by('-updated_at')
    
    # Serialize threads with request context
    serializer = SupportThreadListSerializer(threads, many=True, context={'request': request})
    
    threads_data = {
        'threads': serializer.data,
        'total_threads': threads.count(),
        'open_threads': threads.filter(status__in=['open', 'in_progress']).count(),
        'closed_threads': threads.filter(status__in=['resolved', 'closed']).count()
    }
    
    return Response(threads_data)


@swagger_auto_schema(
    method='post',
    operation_summary='Create Support Thread',
    operation_description='Create a new support thread with an initial message.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'subject': openapi.Schema(type=openapi.TYPE_STRING, description='Thread subject'),
            'message': openapi.Schema(type=openapi.TYPE_STRING, description='Initial message'),
            'priority': openapi.Schema(type=openapi.TYPE_STRING, enum=['low', 'medium', 'high'], description='Priority level'),
            'category': openapi.Schema(type=openapi.TYPE_STRING, enum=['general', 'technical', 'billing', 'account', 'order', 'other'], description='Category')
        },
        required=['subject', 'message']
    ),
    responses={
        201: openapi.Response(description='Thread created successfully'),
        400: openapi.Response(description='Bad request')
    },
    tags=['Support']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_support_thread(request):
    """
    Create a new support thread with an initial message.
    """
    serializer = SupportThreadCreateSerializer(data=request.data, context={'request': request})
    
    if serializer.is_valid():
        thread = serializer.save()
        
        # TODO: Send notification to admin (via async task)
        # from common.tasks import send_support_thread_notification
        # send_support_thread_notification.delay(thread.id)
        
        return Response({
            'message': 'Support thread created successfully',
            'thread_id': thread.id,
            'thread': SupportThreadSerializer(thread).data
        }, status=status.HTTP_201_CREATED)
    else:
        return Response({
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


# ==================== FAQ VIEWS ====================

@swagger_auto_schema(
    method='get',
    operation_summary='Get FAQs',
    operation_description='Get all FAQs with optional filtering.',
    responses={
        200: openapi.Response(
            description='FAQs retrieved successfully',
            examples={
                'application/json': {
                    'faqs': [
                        {
                            'id': 1,
                            'question': 'How do I create an account?',
                            'answer': 'Click on Sign Up...',
                            'slug': 'how-do-i-create-an-account',
                            'is_active': True,
                            'view_count': 10,
                            'sort_order': 0
                        }
                    ]
                }
            }
        )
    },
    tags=['FAQ']
)
@swagger_auto_schema(
    method='post',
    operation_summary='Create FAQ',
    operation_description='Create a new FAQ. Admin only.',
    request_body=FAQSerializer,
    responses={
        201: openapi.Response(description='FAQ created successfully'),
        400: openapi.Response(description='Bad request')
    },
    tags=['FAQ']
)
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def faqs_list(request):
    """
    Get all FAQs or create a new FAQ.
    GET: Public endpoint, returns active FAQs.
    POST: Requires authentication, creates a new FAQ.
    """
    if request.method == 'GET':
        from django.db.models import Q
        import json
        
        # IMPORTANT: Check ALL FAQs first (including inactive) for display_locations
        # We'll filter by is_active AFTER location filtering
        all_faqs_in_db = FAQ.objects.all()
        
        # Optional filtering by display location
        location = request.GET.get('location', '')
        if location:
            # Use Python filtering to check if location is in display_locations array
            # Check ALL FAQs in database, not just active ones
            all_faqs_data = list(all_faqs_in_db.values('id', 'display_locations', 'is_active'))
            faq_ids = []
            
            for faq_data in all_faqs_data:
                faq_id = faq_data['id']
                display_locs = faq_data['display_locations']
                is_active = faq_data['is_active']
                
                # Handle different data types
                if display_locs is None:
                    continue
                
                # Convert to list if it's a string
                if isinstance(display_locs, str):
                    try:
                        display_locs = json.loads(display_locs)
                    except:
                        continue
                
                if isinstance(display_locs, list):
                    # Check if location is in the list or 'all' is in the list
                    if location in display_locs or 'all' in display_locs:
                        faq_ids.append(faq_id)
            
            
            if faq_ids:
                # Recreate queryset with filtered IDs
                faqs = FAQ.objects.filter(id__in=faq_ids)
            else:
                # If no matches, return empty queryset
                faqs = FAQ.objects.none()
        else:
            # No location filter, use all FAQs
            faqs = all_faqs_in_db
        
        # For public access, filter by is_active AFTER location filtering
        if not request.user.is_authenticated or not request.user.is_staff:
            faqs = faqs.filter(is_active=True)
        
        # Optional filtering by search
        search = request.GET.get('search', '')
        if search:
            faqs = faqs.filter(Q(question__icontains=search) | Q(answer__icontains=search))
        
        # Ensure ordering
        if not isinstance(faqs, type(FAQ.objects.none())):
            faqs = faqs.order_by('sort_order', 'id')
        
        serializer = FAQListSerializer(faqs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        # POST requires authentication
        if not request.user.is_authenticated:
            return Response({
                'error': 'Authentication required'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        serializer = FAQSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            faq = serializer.save()
            return Response({
                'message': 'FAQ created successfully',
                'faq': FAQSerializer(faq).data
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='get',
    operation_summary='Get FAQ Detail',
    operation_description='Get a specific FAQ by ID.',
    responses={
        200: openapi.Response(description='FAQ retrieved successfully'),
        404: openapi.Response(description='FAQ not found')
    },
    tags=['FAQ']
)
@swagger_auto_schema(
    method='put',
    operation_summary='Update FAQ',
    operation_description='Update a specific FAQ. Admin only.',
    request_body=FAQSerializer,
    responses={
        200: openapi.Response(description='FAQ updated successfully'),
        400: openapi.Response(description='Bad request'),
        404: openapi.Response(description='FAQ not found')
    },
    tags=['FAQ']
)
@swagger_auto_schema(
    method='delete',
    operation_summary='Delete FAQ',
    operation_description='Delete a specific FAQ. Admin only.',
    responses={
        200: openapi.Response(description='FAQ deleted successfully'),
        404: openapi.Response(description='FAQ not found')
    },
    tags=['FAQ']
)
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def faqs_detail(request, faq_id):
    """
    Get, update, or delete a specific FAQ.
    """
    try:
        faq = FAQ.objects.get(id=faq_id)
    except FAQ.DoesNotExist:
        return Response({
            'error': 'FAQ not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        # Increment view count for public access
        faq.view_count += 1
        faq.save(update_fields=['view_count'])
        
        serializer = FAQSerializer(faq)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'PUT':
        serializer = FAQSerializer(faq, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'FAQ updated successfully',
                'faq': serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        faq.delete()
        return Response({
            'message': 'FAQ deleted successfully'
        }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    operation_summary='Get FAQ Tags',
    operation_description='Get all FAQ tags.',
    responses={
        200: openapi.Response(description='FAQ tags retrieved successfully')
    },
    tags=['FAQ']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def faq_tags_list(request):
    """
    Get all FAQ tags. Public endpoint.
    """
    tags = FAQTag.objects.all().order_by('name')
    serializer = FAQTagListSerializer(tags, many=True)
    return Response({
        'tags': serializer.data
    }, status=status.HTTP_200_OK)
