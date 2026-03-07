from django.urls import path
from . import views

urlpatterns = [
    # Cart management
    path('cart/', views.cart_list, name='cart_list'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:cart_item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/summary/', views.cart_summary, name='cart_summary'),
    
    # Cart item management
    path('cart/move-to-wishlist/<int:cart_item_id>/', views.move_to_wishlist, name='move_to_wishlist'),
    path('cart/move-to-cart/<int:cart_item_id>/', views.move_to_cart, name='move_to_cart'),
    
    # Wishlist management
    path('wishlist/', views.wishlist_list, name='wishlist_list'),
    
    # Bundle management
    path('cart/add-bundle/', views.add_bundle_to_cart, name='add_bundle_to_cart'),
    
    # Purchase and downloads
    path('create/', views.create_order, name='create_order'),
    path('check-free-downloads/', views.check_free_downloads_availability, name='check_free_downloads_availability'),
    path('free-benefits/', views.free_benefits, name='free_benefits'),
    path('purchase/', views.purchase_cart, name='purchase_cart'),
    path('downloads/', views.my_downloads, name='my_downloads'),
    path('downloads/product/<int:product_id>/zip/', views.download_product_zip, name='download_product_zip'),
    
    # Order management
    path('orders/', views.order_history, name='order_history'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('order/<int:order_id>/comments/', views.order_comments, name='order_comments'),
    path('order/<int:order_id>/comments/mark_read/', views.mark_order_comments_as_read, name='mark_order_comments_as_read'),
    
    # Invoice management
    path('invoices/', views.get_user_invoices, name='get_user_invoices'),
    path('invoices/<int:invoice_id>/download/', views.download_invoice, name='download_invoice'),
]
