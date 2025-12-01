from django.urls import path
from . import views
from .auth import admin_token_refresh

# CoreAdmin URLs
urlpatterns = [
    # Authentication endpoints
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('token/refresh/', admin_token_refresh, name='admin_token_refresh'),
    
    # 2FA endpoints
    path('2fa/setup/', views.admin_2fa_setup, name='admin_2fa_setup'),
    path('2fa/verify/', views.admin_2fa_verify, name='admin_2fa_verify'),
    path('2fa/enable/', views.admin_2fa_enable, name='admin_2fa_enable'),
    path('2fa/disable/', views.admin_2fa_disable, name='admin_2fa_disable'),
    
    # Profile and management endpoints
    path('profile/', views.admin_profile, name='admin_profile'),
    path('profile/upload-photo/', views.admin_upload_profile_photo, name='admin_upload_profile_photo'),
    path('change-password/', views.admin_change_password, name='admin_change_password'),
    path('activity-logs/', views.admin_activity_logs, name='admin_activity_logs'),
    path('sessions/', views.admin_sessions, name='admin_sessions'),
    
    # Designer Management endpoints
    path('designers/', views.designers_list, name='designers_list'),
    path('designers/<int:designer_id>/', views.designer_detail, name='designer_detail'),
    path('designers/<int:designer_id>/update-status/', views.designer_update_status, name='designer_update_status'),
    path('designers/<int:designer_id>/wallet/', views.designer_wallet, name='designer_wallet'),
    path('designers/<int:designer_id>/transactions/', views.designer_transactions, name='designer_transactions'),
    path('designers/<int:designer_id>/withdrawals/', views.designer_withdrawals, name='designer_withdrawals'),
    path('withdrawals/<int:withdrawal_id>/update-status/', views.update_withdrawal_status, name='update_withdrawal_status'),
    path('designers/analytics/', views.designer_analytics, name='designer_analytics'),
    path('designers/bulk-update/', views.bulk_update_designer_status, name='bulk_update_designer_status'),
    
    # Enhanced Designer Management endpoints
    path('designers/onboarding/', views.designer_onboarding_list, name='designer_onboarding_list'),
    path('designers/<int:designer_id>/onboarding/', views.designer_onboarding_detail, name='designer_onboarding_detail'),
    path('designers/<int:designer_id>/onboarding/verify/', views.verify_designer_onboarding, name='verify_designer_onboarding'),
    path('designers/payouts/', views.designer_payout_requests, name='designer_payout_requests'),
    path('designers/payouts/process/', views.process_designer_payouts, name='process_designer_payouts'),
    path('designers/<int:designer_id>/account-action/', views.designer_account_action, name='designer_account_action'),
    path('designers/<int:designer_id>/wallet-summary/', views.designer_wallet_summary, name='designer_wallet_summary'),
    
    # Customer Management endpoints
    path('customers/', views.customers_list, name='customers_list'),
    path('customers/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:customer_id>/history/', views.customer_history, name='customer_history'),
    path('customers/<int:customer_id>/account-action/', views.customer_account_action, name='customer_account_action'),
    path('customers/analytics/', views.customer_analytics, name='customer_analytics'),
    
    # Design Management endpoints
    path('designs/', views.designs_list, name='designs_list'),
    path('designs/<int:design_id>/', views.design_detail, name='design_detail'),
    path('designs/<int:design_id>/action/', views.design_action, name='design_action'),
    path('designs/stats/', views.design_stats, name='design_stats'),
    path('categories/', views.categories_list, name='categories_list'),
    path('categories/create/', views.create_category, name='create_category'),
    path('tags/', views.tags_list, name='tags_list'),
    path('copyright-reports/', views.copyright_reports_list, name='copyright_reports_list'),
    path('copyright-reports/<int:report_id>/action/', views.copyright_report_action, name='copyright_report_action'),
    path('designs/analytics/', views.design_analytics, name='design_analytics'),
    
    # Transaction and Order Management endpoints
    path('transactions/', views.transactions_list, name='transactions_list'),
    path('transactions/<int:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    path('transactions/<int:transaction_id>/refund/', views.initiate_refund, name='initiate_refund'),
    path('refunds/', views.refunds_list, name='refunds_list'),
    path('orders/', views.orders_list, name='orders_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/update-status/', views.update_order_status, name='update_order_status'),
    path('financial-reports/', views.financial_reports, name='financial_reports'),
    
    # Custom Order Management endpoints
    path('custom-orders/', views.custom_orders_list, name='custom_orders_list'),
    path('custom-orders/<int:order_id>/', views.custom_order_detail, name='custom_order_detail'),
    path('custom-orders/<int:order_id>/action/', views.custom_order_action, name='custom_order_action'),
    path('custom-orders/<int:order_id>/update-status/', views.update_custom_order_status, name='update_custom_order_status'),
    path('custom-orders/<int:order_id>/upload-files/', views.custom_order_upload_files, name='custom_order_upload_files'),
    path('custom-orders/analytics/', views.custom_order_analytics, name='custom_order_analytics'),
    
    # Subscription Plans Management endpoints
    path('subscription-plans/', views.subscription_plans_list, name='subscription_plans_list'),
    path('subscription-plans/<int:plan_id>/', views.subscription_plan_detail, name='subscription_plan_detail'),
    path('subscription-plans/create/', views.create_subscription_plan, name='create_subscription_plan'),
    path('subscription-plans/<int:plan_id>/update/', views.update_subscription_plan, name='update_subscription_plan'),
    path('subscription-plans/<int:plan_id>/deactivate/', views.deactivate_subscription_plan, name='deactivate_subscription_plan'),
    path('subscription-plans/analytics/', views.subscription_plans_analytics, name='subscription_plans_analytics'),
    
    # Business Configuration endpoints
    path('business-config/', views.business_config, name='business_config'),
    
    # System Configuration endpoints
    path('landing-page-data/', views.get_landing_page_data, name='get_landing_page_data'),
    path('system-config/', views.get_system_config, name='get_system_config'),
    path('system-config/update/', views.update_system_config, name='update_system_config'),
    
    # Notification Management endpoints
    path('notifications/create/', views.create_notification, name='create_notification'),
    path('notifications/campaigns/', views.list_notification_campaigns, name='list_notification_campaigns'),
    
    # Admin User Management endpoints (Super Admin only)
    path('admin-users/', views.admin_users_list, name='admin_users_list'),
    path('admin-users/create/', views.admin_user_create, name='admin_user_create'),
    path('admin-users/create-profile/', views.admin_user_create_profile, name='admin_user_create_profile'),
    path('admin-users/<int:user_id>/', views.admin_user_detail, name='admin_user_detail'),
    path('admin-users/<int:user_id>/reset-password/', views.admin_user_reset_password, name='admin_user_reset_password'),
    
    # Permission Groups Management endpoints (Super Admin only)
    path('permission-groups/', views.permission_groups_list, name='permission_groups_list'),
    path('permission-groups/create/', views.permission_group_create, name='permission_group_create'),
    path('permission-groups/<int:group_id>/', views.permission_group_detail, name='permission_group_detail'),
]
