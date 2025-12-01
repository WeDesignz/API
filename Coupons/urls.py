from django.urls import path
from . import views

urlpatterns = [
    # Admin coupons
    path('admin/', views.admin_coupons, name='admin_coupons'),
    
    # Coupons
    path('available/', views.available_coupons, name='available_coupons'),
    path('featured/', views.featured_coupons, name='featured_coupons'),
    path('search/', views.search_coupons, name='search_coupons'),
    path('<int:coupon_id>/', views.coupon_details, name='coupon_details'),
    
    # Coupon Operations
    path('validate/', views.validate_coupon, name='validate_coupon'),
    path('apply/', views.apply_coupon, name='apply_coupon'),
    path('remove/', views.remove_coupon, name='remove_coupon'),
    
    # User Coupon Data
    path('my-usage/', views.my_coupon_usage, name='my_coupon_usage'),
]
