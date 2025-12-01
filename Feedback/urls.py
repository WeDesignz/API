from django.urls import path
from . import views

urlpatterns = [
    # Feedback
    path('', views.feedback_list, name='feedback_list'),
    path('submit/', views.submit_feedback, name='submit_feedback'),
    path('<int:feedback_id>/', views.feedback_detail, name='feedback_detail'),
    path('my-feedback/', views.my_feedback, name='my_feedback'),
    path('stats/', views.feedback_stats, name='feedback_stats'),
    
    # Notifications
    path('designer-notifications/', views.designer_notifications, name='designer_notifications'),
    path('mark-notification-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('mark-all-notifications-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notification-count/', views.notification_count, name='notification_count'),
    path('statistics/', views.notification_statistics, name='notification_statistics'),
    
    # Support
    path('support-threads/', views.support_threads, name='support_threads'),
    path('create-support-thread/', views.create_support_thread, name='create_support_thread'),
    path('support-thread/<int:thread_id>/', views.support_thread, name='support_thread'),
    path('support-messages/', views.support_messages, name='support_messages'),
    
    # FAQ
    path('faqs/', views.faqs_list, name='faqs_list'),
    path('faqs/<int:faq_id>/', views.faqs_detail, name='faqs_detail'),
    path('faq-tags/', views.faq_tags_list, name='faq_tags_list'),
]
