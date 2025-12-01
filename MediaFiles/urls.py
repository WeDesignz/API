from django.urls import path
from . import views

urlpatterns = [
    # Media Files
    path('upload/', views.upload_media, name='upload_media'),
    path('my-media/', views.my_media, name='my_media'),
    path('<int:media_id>/', views.media_detail, name='media_detail'),
    path('<int:media_id>/delete/', views.delete_media, name='delete_media'),
    path('search/', views.search_media, name='search_media'),
    path('stats/', views.media_stats, name='media_stats'),
]
