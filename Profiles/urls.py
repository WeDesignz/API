from django.urls import path
from . import views

urlpatterns = [
    # Addresses
    path('addresses/', views.addresses_list, name='addresses_list'),
    path('addresses/<int:address_id>/', views.address_detail, name='address_detail'),
    
    # Designer Profile
    path('designer-profile/', views.designer_profile, name='designer_profile'),
    path('designer-dashboard/', views.designer_dashboard, name='designer_dashboard'),
    
    # Designer Onboarding
    path('designer-onboarding-step1/', views.designer_onboarding_step1, name='designer_onboarding_step1'),
    path('designer-onboarding-step2/', views.designer_onboarding_step2, name='designer_onboarding_step2'),
    path('designer-onboarding-step3/', views.designer_onboarding_step3, name='designer_onboarding_step3'),
    path('designer-onboarding-step4/', views.designer_onboarding_step4, name='designer_onboarding_step4'),
    path('designer-onboarding-status/', views.designer_onboarding_status, name='designer_onboarding_status'),
    # Design Processing
    path('design-processing-progress/', views.get_design_processing_progress, name='get_design_processing_progress'),
    path('design-processing-status/', views.get_design_processing_status, name='get_design_processing_status'),
    path('design-processing-stream/', views.stream_design_processing_progress, name='stream_design_processing_progress'),
    # GET endpoints for retrieving saved data
    path('get-designer-onboarding-step1/', views.get_designer_onboarding_step1, name='get_designer_onboarding_step1'),
    path('get-designer-onboarding-step2/', views.get_designer_onboarding_step2, name='get_designer_onboarding_step2'),
    path('get-designer-onboarding-step3/', views.get_designer_onboarding_step3, name='get_designer_onboarding_step3'),
    
    # Studios
    path('studios/', views.studios_list, name='studios_list'),
    path('studios/create/', views.create_studio, name='create_studio'),
    path('studios/design-number-info/', views.studio_design_number_info, name='studio_design_number_info'),
    path('studios/regenerate-name/', views.regenerate_studio_name, name='regenerate_studio_name'),
    path('studios/<int:studio_id>/', views.studio_detail, name='studio_detail'),
    path('studios/<int:studio_id>/business-details/', views.studio_business_details, name='studio_business_details'),
    path('studios/<int:studio_id>/members/', views.studio_members, name='studio_members'),
    path('studios/<int:studio_id>/members/create/', views.create_studio_member_with_user, name='create_studio_member_with_user'),
    path('studios/<int:studio_id>/members/<int:member_id>/', views.studio_member_detail, name='studio_member_detail'),
    path('studios/<int:studio_id>/members/<int:member_id>/send-credentials/', views.send_studio_member_credentials, name='send_studio_member_credentials'),
    path('studios/<int:studio_id>/ratings/', views.studio_ratings, name='studio_ratings'),
    path('studios/<int:studio_id>/members/<int:member_id>/ratings/', views.studio_member_ratings, name='studio_member_ratings'),
    
    # My Studios and Ratings
    path('my-studios/', views.my_studios, name='my_studios'),
    path('my-ratings/', views.my_ratings, name='my_ratings'),
    path('top-studios/', views.top_studios, name='top_studios'),
    
    # Ratings
    path('ratings/', views.ratings_list, name='ratings_list'),
]
