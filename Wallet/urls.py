from django.urls import path
from . import views

urlpatterns = [
    # Wallet Balance and Transactions
    path('balance/', views.wallet_balance, name='wallet_balance'),
    path('transactions/', views.wallet_transactions, name='wallet_transactions'),
    path('summary/', views.wallet_summary, name='wallet_summary'),
    path('recent-transactions/', views.recent_transactions, name='recent_transactions'),
    
    # Wallet Operations
    path('add-balance/', views.add_wallet_balance, name='add_wallet_balance'),
    path('deduct-balance/', views.deduct_wallet_balance, name='deduct_wallet_balance'),
    path('transfer/', views.transfer_to_wallet, name='transfer_to_wallet'),
    
    # Withdrawal Requests
    path('withdrawal-requests/', views.withdrawal_requests, name='withdrawal_requests'),
    path('withdrawal-requests/<int:request_id>/', views.withdrawal_request_detail, name='withdrawal_request_detail'),
    path('withdrawal-requests/<int:request_id>/cancel/', views.cancel_withdrawal_request, name='cancel_withdrawal_request'),
    path('create-withdrawal/', views.create_withdrawal_request, name='create_withdrawal_request'),
    
    # Earnings Summary
    path('earnings-summary/', views.earnings_summary, name='earnings_summary'),
    
    # Settlement Management
    path('settlement-status/', views.settlement_status, name='settlement_status'),
    path('accept-settlement/', views.accept_settlement, name='accept_settlement'),
    
    # Admin - Settlement Management
    # settlement-sheet must come BEFORE all settlements patterns to avoid conflicts
    path('admin/settlement-sheet/', views.download_settlement_sheet, name='download_settlement_sheet'),
    path('admin/settlements/<int:settlement_id>/status/', views.update_settlement_status, name='update_settlement_status'),
    path('admin/settlements/bulk-update/', views.bulk_update_settlement_status, name='bulk_update_settlement_status'),
    path('admin/settlements/', views.list_settlements, name='list_settlements'),
]
