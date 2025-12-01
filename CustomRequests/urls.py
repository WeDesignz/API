from django.urls import path
from . import views

urlpatterns = [
    # Custom Requests
    path('', views.custom_requests_list, name='custom_requests_list'),
    path('submit/', views.submit_custom_request, name='submit_custom_request'),
    path('history/', views.custom_request_history, name='custom_request_history'),
    
    # Custom Request Details
    path('<int:request_id>/', views.custom_request_detail, name='custom_request_detail'),
    path('<int:request_id>/status/', views.custom_request_status, name='custom_request_status'),
    path('<int:request_id>/cancel/', views.cancel_custom_request, name='cancel_custom_request'),
    path('<int:request_id>/timer/', views.custom_request_timer, name='custom_request_timer'),
    path('<int:request_id>/media/', views.custom_request_media, name='custom_request_media'),
    path('<int:request_id>/deliverables/zip/', views.download_custom_order_deliverables_zip, name='download_custom_order_deliverables_zip'),
    
    # Comments are now handled through OrderComment model via Order
    # Use /api/orders/{order_id}/comments/ endpoint instead
]
