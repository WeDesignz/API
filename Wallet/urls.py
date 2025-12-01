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
]
