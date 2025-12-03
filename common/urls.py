from django.urls import path
from . import views

urlpatterns = [
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
]

