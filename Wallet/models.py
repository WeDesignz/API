from django.db import models
from django.contrib.auth.models import User
from common.relations import attach_relation, get_related_ids, get_related, detach_relation


class Wallet(models.Model):
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_wallets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_wallets', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'wallet'
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'
    
    def __str__(self):
        return f"Wallet {self.pk} (Balance: {self.balance})"
    
    def get_wallet_transactions(self):
        return get_related(self, 'Wallet:WalletTransaction', WalletTransaction)
    
    def attach_wallet_transaction(self, wallet_transaction_obj, meta=None, created_by=None):
        return attach_relation('Wallet:WalletTransaction', self, wallet_transaction_obj, meta=meta, created_by=created_by)
    
    def detach_wallet_transaction(self, wallet_transaction_obj):
        return detach_relation('Wallet:WalletTransaction', self, wallet_transaction_obj)
    
    def get_withdrawal_requests(self):
        return get_related(self, 'Wallet:WithdrawalRequest', WalletWithdrawalRequest)
    
    def attach_withdrawal_request(self, withdrawal_request_obj, meta=None, created_by=None):
        return attach_relation('Wallet:WithdrawalRequest', self, withdrawal_request_obj, meta=meta, created_by=created_by)
    
    def detach_withdrawal_request(self, withdrawal_request_obj):
        return detach_relation('Wallet:WithdrawalRequest', self, withdrawal_request_obj)


class WalletTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]
    
    wallet_transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    reference_id = models.CharField(max_length=100, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_wallet_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_wallet_transactions', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'wallet_transaction'
        verbose_name = 'Wallet Transaction'
        verbose_name_plural = 'Wallet Transactions'
    
    def __str__(self):
        return f"Wallet Transaction {self.pk} - {self.wallet_transaction_type} ({self.amount})"


class WalletWithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reason = models.TextField(blank=True, null=True)
    admin_remarks = models.TextField(blank=True, null=True)
    processed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='processed_withdrawal_requests', null=True, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_wallet_withdrawal_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_wallet_withdrawal_requests', null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()
    
    class Meta:
        db_table = 'wallet_withdrawal_request'
        verbose_name = 'Wallet Withdrawal Request'
        verbose_name_plural = 'Wallet Withdrawal Requests'
    
    def __str__(self):
        return f"Withdrawal Request {self.pk} - {self.wallet.user.username} ({self.amount})"
    
    
    def get_wallet_transactions(self):
        return get_related(self, 'WithdrawalRequest:WalletTransaction', WalletTransaction)
    
    def attach_wallet_transaction(self, wallet_transaction_obj, meta=None, created_by=None):
        return attach_relation('WithdrawalRequest:WalletTransaction', self, wallet_transaction_obj, meta=meta, created_by=created_by)
    
    def detach_wallet_transaction(self, wallet_transaction_obj):
        return detach_relation('WithdrawalRequest:WalletTransaction', self, wallet_transaction_obj)


class SettlementRequest(models.Model):
    """
    Model to track monthly settlement requests for designers.
    Settlement window: Days 1-5 of each month
    Processing: Day 6 of each month
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),  # Created, waiting for opt-in
        ('opted_in', 'Opted In'),  # Designer opted in during window
        ('processing', 'Processing'),  # Being processed
        ('completed', 'Completed'),  # Settlement successful
        ('failed', 'Failed'),  # Settlement failed
        ('expired', 'Expired'),  # Window closed without opt-in
    ]
    
    designer_id = models.IntegerField()  # Will be linked via relation
    settlement_period_start = models.DateField()  # First day of previous month
    settlement_period_end = models.DateField()  # Last day of previous month
    wallet_balance_at_period_end = models.DecimalField(max_digits=10, decimal_places=2)
    settlement_amount = models.DecimalField(max_digits=10, decimal_places=2)  # Amount to settle
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Opt-in tracking
    opted_in = models.BooleanField(default=False)
    opted_in_at = models.DateTimeField(null=True, blank=True)
    
    # Settlement execution
    settlement_date = models.DateField(null=True, blank=True)  # Day 6 when processed
    razorpay_transfer_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payout_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Error tracking
    failure_reason = models.TextField(blank=True, null=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'settlement_request'
        verbose_name = 'Settlement Request'
        verbose_name_plural = 'Settlement Requests'
        ordering = ['-created_at']
        unique_together = [['designer_id', 'settlement_period_start']]  # One per period
    
    def __str__(self):
        return f"Settlement Request {self.pk} - Designer {self.designer_id} - {self.settlement_amount} - {self.get_status_display()}"
    
    @property
    def designer(self):
        """Get the related designer via relation system"""
        from django.contrib.auth.models import User
        from common.relations import get_related
        try:
            temp_obj = type('TempObj', (), {'pk': self.designer_id})()
            users = get_related(temp_obj, 'User:SettlementRequest', User)
            return users.first()
        except:
            return None
    
    def set_designer(self, designer):
        """Set the related designer via relation system"""
        from common.relations import attach_relation
        attach_relation('User:SettlementRequest', designer, self)