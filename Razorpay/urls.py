from django.urls import path
from . import views

urlpatterns = [
    # Payment Orders
    path('create-order/', views.create_payment_order, name='create_payment_order'),
    path('capture-payment/', views.capture_payment, name='capture_payment'),
    path('payment/<int:payment_id>/status/', views.payment_status, name='payment_status'),
    path('payment-history/', views.payment_history, name='payment_history'),
    
    # Refunds
    path('create-refund/', views.create_refund, name='create_refund'),
    
    # Subscription Payments
    path('subscription-payment/', views.create_subscription_payment, name='create_subscription_payment'),
    
    # PDF Download Payments
    path('pdf-payment/', views.create_pdf_payment_order, name='create_pdf_payment_order'),
    path('pdf-capture-payment/', views.capture_pdf_payment, name='capture_pdf_payment'),
    path('pdf-payment/<int:payment_id>/status/', views.pdf_payment_status, name='pdf_payment_status'),
    
    # Payment Methods
    path('payment-methods/', views.payment_methods, name='payment_methods'),
    
    # Webhooks
    path('webhook/', views.webhook_handler, name='webhook_handler'),
    path('webhook-events/', views.webhook_events, name='webhook_events'),
    
    # Linked Accounts
    path('create-linked-account/', views.create_linked_account, name='create_linked_account'),
]
