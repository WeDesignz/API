from django.contrib import admin
from .models import Wallet, WalletTransaction, WalletWithdrawalRequest, SettlementRequest


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    """
    Admin interface for Wallet model.
    Manages user wallets and balance information.
    """
    list_display = ['balance', 'created_by', 'created_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['balance']
    list_display_links = ['created_by']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Wallet Information', {
            'fields': ('balance',)
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by', 'updated_by')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    """
    Admin interface for WalletTransaction model.
    Manages wallet transactions including credits and debits.
    """
    list_display = ['id', 'wallet_transaction_type', 'amount', 'description', 'reference_id', 'created_by', 'created_at']
    list_filter = ['wallet_transaction_type', 'created_at', 'updated_at']
    search_fields = ['description', 'reference_id', 'created_by__username', 'created_by__email']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['wallet_transaction_type', 'amount']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('wallet_transaction_type', 'amount', 'description', 'reference_id')
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by', 'updated_by')


@admin.register(WalletWithdrawalRequest)
class WalletWithdrawalRequestAdmin(admin.ModelAdmin):
    """
    Admin interface for WalletWithdrawalRequest model.
    Manages wallet withdrawal requests and their processing status.
    """
    list_display = ['id', 'wallet', 'amount', 'status', 'processed_by', 'created_by', 'created_at']
    list_filter = ['status', 'created_at', 'updated_at', 'processed_at']
    search_fields = ['wallet__created_by__username', 'wallet__created_by__email', 'reason', 'admin_remarks', 'created_by__username']
    readonly_fields = ['created_at', 'updated_at', 'processed_at']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Withdrawal Information', {
            'fields': ('wallet', 'amount', 'status', 'reason')
        }),
        ('Processing Information', {
            'fields': ('processed_by', 'processed_at', 'admin_remarks'),
            'classes': ('collapse',)
        }),
        ('User Information', {
            'fields': ('created_by', 'updated_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('wallet', 'processed_by', 'created_by', 'updated_by')


@admin.register(SettlementRequest)
class SettlementRequestAdmin(admin.ModelAdmin):
    """
    Admin interface for SettlementRequest model.
    Manages monthly settlement requests for designers.
    """
    list_display = ['id', 'designer_id', 'settlement_period_start', 'settlement_amount', 'status', 'opted_in', 'settlement_date', 'created_at']
    list_filter = ['status', 'opted_in', 'settlement_period_start', 'created_at', 'settlement_date']
    search_fields = ['designer_id', 'razorpay_transfer_id', 'razorpay_payout_id', 'failure_reason']
    readonly_fields = ['created_at', 'updated_at', 'settlement_date']
    list_editable = ['status']
    ordering = ['-created_at']
    list_per_page = 25
    
    fieldsets = (
        ('Settlement Information', {
            'fields': ('designer_id', 'settlement_period_start', 'settlement_period_end', 
                      'wallet_balance_at_period_end', 'settlement_amount', 'status')
        }),
        ('Opt-in Information', {
            'fields': ('opted_in', 'opted_in_at')
        }),
        ('Processing Information', {
            'fields': ('settlement_date', 'razorpay_transfer_id', 'razorpay_payout_id', 'failure_reason'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )