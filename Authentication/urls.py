from django.urls import path
from . import views

urlpatterns = [
    # Authentication endpoints
    path('signup/', views.signup, name='signup'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('refresh-token/', views.refresh_token, name='refresh_token'),
    
    # Email verification
    path('verify-email/', views.verify_email, name='verify_email'),
    
    # Password reset
    path('request-password-reset/', views.request_password_reset, name='request_password_reset'),
    path('verify-password-reset-otp/', views.verify_password_reset_otp, name='verify_password_reset_otp'),
    path('confirm-password-reset/', views.confirm_password_reset, name='confirm_password_reset'),
    
    # Mobile number management
    path('add-mobile-number/', views.add_mobile_number, name='add_mobile_number'),
    path('verify-mobile-number/', views.verify_mobile_number, name='verify_mobile_number'),
    path('mobile-numbers/<int:mobile_id>/', views.update_mobile_number, name='update_mobile_number'),
    path('mobile-numbers/<int:mobile_id>/delete/', views.delete_mobile_number, name='delete_mobile_number'),
    
    # OTP management
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    
    # User profile management
    path('profile/', views.user_profile, name='user_profile'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('upload-profile-photo/', views.upload_profile_photo, name='upload_profile_photo'),
    path('change-password/', views.change_password, name='change_password'),
    
    # Email management
    path('emails/', views.list_email_addresses, name='list_email_addresses'),
    path('emails/add/', views.add_email_address, name='add_email_address'),
    path('emails/<int:email_id>/', views.update_email_address, name='update_email_address'),
    path('emails/<int:email_id>/delete/', views.delete_email_address, name='delete_email_address'),
    path('emails/verify/', views.verify_email_address, name='verify_email_address'),
    
    # Customer notifications
    path('customer-notifications/', views.customer_notifications, name='customer_notifications'),
    path('customer-notification-count/', views.customer_notification_count, name='customer_notification_count'),
    path('customer-notifications/<int:notification_id>/mark-read/', views.mark_customer_notification_read, name='mark_customer_notification_read'),
    path('customer-notifications/mark-all-read/', views.mark_all_customer_notifications_read, name='mark_all_customer_notifications_read'),
]
