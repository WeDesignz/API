from django.urls import path
from . import views

urlpatterns = [
    # User Management
    path('users/', views.users_list, name='users_list'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/activate/', views.activate_user, name='activate_user'),
    path('users/<int:user_id>/deactivate/', views.deactivate_user, name='deactivate_user'),
    path('users/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('stats/', views.user_stats, name='user_stats'),
    path('search/', views.search_users, name='search_users'),
]
