from django.urls import path
from . import views

urlpatterns = [
    # Landing page and home feed
    path('landing/', views.landing_page, name='landing_page'),
    path('home-feed/', views.home_feed, name='home_feed'),
    
    # Dynamic sections
    path('trending/', views.trending_designs, name='trending_designs'),
    path('recent/', views.recently_added, name='recently_added'),
    path('popular-categories/', views.popular_categories, name='popular_categories'),
    path('hero-section/', views.hero_section_designs, name='hero_section_designs'),
    path('featured-designs/', views.featured_designs, name='featured_designs'),
    path('dome-gallery/', views.dome_gallery_images, name='dome_gallery_images'),
    
    # Search and filters
    path('search/', views.search_and_filter, name='search_and_filter'),
    path('lens-search/', views.lens_search, name='lens_search'),
    
    # Product details
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),
    
    # My Designs
    path('my-designs/', views.my_designs, name='my_designs'),
    path('designs/<int:design_id>/', views.design_detail, name='design_detail'),
    path('design-analytics/<int:design_id>/', views.design_analytics, name='design_analytics'),
    path('upload-design/', views.upload_design, name='upload_design'),
    path('upload-designs-bulk/', views.upload_designs_bulk, name='upload_designs_bulk'),
    
    # Categories and tags
    path('categories/', views.categories_list, name='categories_list'),  # GET and POST
    path('categories/<int:category_id>/subcategories/', views.category_subcategories, name='category_subcategories'),  # GET and POST
    path('tags/', views.tags_list, name='tags_list'),
    
    # Bundles
    path('bundles/', views.bundles_list, name='bundles_list'),
    path('bundles/<int:bundle_id>/', views.bundle_detail, name='bundle_detail'),
    
    # PDF Download functionality
    path('pdf/config/', views.get_pdf_config, name='get_pdf_config'),
    path('pdf/check-eligibility/', views.check_free_download_eligibility, name='check_free_download_eligibility'),
    path('pdf/create-request/', views.create_pdf_download_request, name='create_pdf_download_request'),
    path('pdf/status/<int:download_id>/', views.get_pdf_download_status, name='get_pdf_download_status'),
    path('pdf/downloads/', views.list_user_pdf_downloads, name='list_user_pdf_downloads'),
    path('pdf/process-payment/', views.process_pdf_payment, name='process_pdf_payment'),
    path('pdf/download/<int:download_id>/', views.download_pdf_file, name='download_pdf_file'),
    path('pdf/pricing/', views.get_pdf_pricing_info, name='get_pdf_pricing_info'),
    path('pdf/search-products/', views.search_products_for_pdf, name='search_products_for_pdf'),
    path('pdf/browse-designs/', views.browse_designs_catalog, name='browse_designs_catalog'),
    path('pdf/add-products/<int:download_id>/', views.add_products_to_pdf, name='add_products_to_pdf'),
]
