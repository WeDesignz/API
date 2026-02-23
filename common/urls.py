from django.urls import path
from . import views

urlpatterns = [
    # Pinterest endpoints
    path('authorize/', views.pinterest_oauth_initiate, name='pinterest_oauth_initiate'),
    path('authorize', views.pinterest_oauth_initiate, name='pinterest_oauth_initiate_no_slash'),
    path('callback/', views.pinterest_oauth_callback, name='pinterest_oauth_callback'),
    path('callback', views.pinterest_oauth_callback, name='pinterest_oauth_callback_no_slash'),
    path('status/', views.pinterest_status, name='pinterest_status'),
    path('status', views.pinterest_status, name='pinterest_status_no_slash'),
    path('boards/', views.pinterest_boards, name='pinterest_boards'),
    path('boards', views.pinterest_boards, name='pinterest_boards_no_slash'),
    path('set-board/', views.pinterest_set_board, name='pinterest_set_board'),
    path('set-board', views.pinterest_set_board, name='pinterest_set_board_no_slash'),
    path('create-board/', views.pinterest_create_board, name='pinterest_create_board'),
    path('create-board', views.pinterest_create_board, name='pinterest_create_board_no_slash'),
    path('update-board/', views.pinterest_update_board, name='pinterest_update_board'),
    path('update-board', views.pinterest_update_board, name='pinterest_update_board_no_slash'),
    path('delete-board/<str:board_id>/', views.pinterest_delete_board, name='pinterest_delete_board'),
    path('delete-board/<str:board_id>', views.pinterest_delete_board, name='pinterest_delete_board_no_slash'),
    path('posts/', views.pinterest_posts_list, name='pinterest_posts_list'),
    path('posts', views.pinterest_posts_list, name='pinterest_posts_list_no_slash'),
    path('posts/bulk-post/', views.pinterest_posts_bulk_post, name='pinterest_posts_bulk_post'),
    path('posts/bulk-post', views.pinterest_posts_bulk_post, name='pinterest_posts_bulk_post_no_slash'),
    path('posts/<int:post_id>/retry/', views.pinterest_post_retry, name='pinterest_post_retry'),
    path('posts/<int:post_id>/retry', views.pinterest_post_retry, name='pinterest_post_retry_no_slash'),
    # Instagram endpoints
    path('instagram/authorize/', views.instagram_oauth_initiate, name='instagram_oauth_initiate'),
    path('instagram/authorize', views.instagram_oauth_initiate, name='instagram_oauth_initiate_no_slash'),
    path('instagram/callback/', views.instagram_oauth_callback, name='instagram_oauth_callback'),
    path('instagram/callback', views.instagram_oauth_callback, name='instagram_oauth_callback_no_slash'),
    path('instagram/status/', views.instagram_status, name='instagram_status'),
    path('instagram/status', views.instagram_status, name='instagram_status_no_slash'),
    path('instagram/post/', views.instagram_post, name='instagram_post'),
    path('instagram/post', views.instagram_post, name='instagram_post_no_slash'),
    path('instagram/posts/', views.instagram_posts_list, name='instagram_posts_list'),
    path('instagram/posts', views.instagram_posts_list, name='instagram_posts_list_no_slash'),
]

