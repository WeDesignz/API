from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Wallet, WalletTransaction, WalletWithdrawalRequest
from Accounts.serializers import UserSerializer


class WalletSerializer(serializers.ModelSerializer):
    """
    Serializer for Wallet model with full CRUD operations.
    Handles wallet creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    transactions = serializers.SerializerMethodField()
    withdrawal_requests = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = [
            'id', 'balance', 'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id', 'transactions', 'withdrawal_requests'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_transactions(self, obj):
        """
        Get related wallet transactions for the wallet.
        """
        if obj:
            try:
                transactions = obj.get_wallet_transactions()
                return WalletTransactionListSerializer(transactions, many=True).data
            except Exception:
                # If get_wallet_transactions fails, return empty list
                return []
        return []
    
    def get_withdrawal_requests(self, obj):
        """
        Get related withdrawal requests for the wallet.
        """
        if obj:
            try:
                withdrawal_requests = obj.get_withdrawal_requests()
                return WalletWithdrawalRequestListSerializer(withdrawal_requests, many=True).data
            except Exception:
                # If get_withdrawal_requests fails, return empty list
                return []
        return []
    
    def validate_balance(self, value):
        """
        Validate balance is non-negative.
        """
        if value < 0:
            raise serializers.ValidationError("Balance cannot be negative.")
        return value


class WalletListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for Wallet model used in list views.
    """
    created_by = UserSerializer(read_only=True)
    transactions_count = serializers.SerializerMethodField()
    withdrawal_requests_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = [
            'id', 'balance', 'created_by', 'created_at',
            'transactions_count', 'withdrawal_requests_count'
        ]
    
    def get_transactions_count(self, obj):
        """
        Get count of related wallet transactions.
        """
        return len(obj.get_wallet_transactions())
    
    def get_withdrawal_requests_count(self, obj):
        """
        Get count of related withdrawal requests.
        """
        return len(obj.get_withdrawal_requests())


class WalletCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating wallets with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Wallet
        fields = ['balance', 'created_by_id']
    
    def validate_balance(self, value):
        """
        Validate balance is non-negative.
        """
        if value < 0:
            raise serializers.ValidationError("Balance cannot be negative.")
        return value


class WalletUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating wallets with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = Wallet
        fields = ['balance', 'updated_by_id']
    
    def validate_balance(self, value):
        """
        Validate balance is non-negative.
        """
        if value is not None and value < 0:
            raise serializers.ValidationError("Balance cannot be negative.")
        return value


class WalletTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for WalletTransaction model with full CRUD operations.
    Handles wallet transaction creation, updates, and management.
    """
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'wallet_transaction_type', 'amount', 'description', 'reference_id',
            'created_by', 'created_at', 'updated_by', 'updated_at',
            'created_by_id', 'updated_by_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_amount(self, value):
        """
        Validate amount is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value
    
    def validate_description(self, value):
        """
        Validate description is not empty if provided.
        """
        if value is not None and not value.strip():
            raise serializers.ValidationError("Description cannot be empty.")
        return value.strip() if value else value


class WalletTransactionListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for WalletTransaction model used in list views.
    """
    created_by = UserSerializer(read_only=True)
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'wallet_transaction_type', 'amount', 'description',
            'reference_id', 'created_by', 'created_at'
        ]


class WalletTransactionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating wallet transactions with minimal required fields.
    """
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = WalletTransaction
        fields = [
            'wallet_transaction_type', 'amount', 'description', 'reference_id', 'created_by_id'
        ]
    
    def validate_amount(self, value):
        """
        Validate amount is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class WalletTransactionUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating wallet transactions with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = WalletTransaction
        fields = ['description', 'reference_id', 'updated_by_id']


class WalletWithdrawalRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for WalletWithdrawalRequest model with full CRUD operations.
    Handles withdrawal request creation, updates, and management.
    """
    wallet = WalletSerializer(read_only=True)
    processed_by = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    wallet_id = serializers.IntegerField(write_only=True)
    processed_by_id = serializers.IntegerField(write_only=True, required=False)
    created_by_id = serializers.IntegerField(write_only=True, required=False)
    updated_by_id = serializers.IntegerField(write_only=True, required=False)
    wallet_transactions = serializers.SerializerMethodField()
    
    class Meta:
        model = WalletWithdrawalRequest
        fields = [
            'id', 'wallet', 'wallet_id', 'amount', 'status', 'reason', 'admin_remarks',
            'processed_by', 'processed_at', 'created_by', 'created_at',
            'updated_by', 'updated_at', 'processed_by_id', 'created_by_id',
            'updated_by_id', 'wallet_transactions'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'processed_at']
    
    def get_wallet_transactions(self, obj):
        """
        Get related wallet transactions for the withdrawal request.
        """
        if obj:
            wallet_transactions = obj.get_wallet_transactions()
            return WalletTransactionListSerializer(wallet_transactions, many=True).data
        return []
    
    def validate_wallet_id(self, value):
        """
        Validate that wallet exists.
        """
        try:
            Wallet.objects.get(id=value)
        except Wallet.DoesNotExist:
            raise serializers.ValidationError("Wallet does not exist.")
        return value
    
    def validate_amount(self, value):
        """
        Validate amount is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value
    
    def validate_reason(self, value):
        """
        Validate reason is not empty if provided.
        """
        if value is not None and not value.strip():
            raise serializers.ValidationError("Reason cannot be empty.")
        return value.strip() if value else value
    
    def validate_admin_remarks(self, value):
        """
        Validate admin remarks is not empty if provided.
        """
        if value is not None and not value.strip():
            raise serializers.ValidationError("Admin remarks cannot be empty.")
        return value.strip() if value else value
    
    def validate(self, attrs):
        """
        Validate business logic for withdrawal requests.
        """
        wallet_id = attrs.get('wallet_id')
        amount = attrs.get('amount')
        status = attrs.get('status')
        processed_by_id = attrs.get('processed_by_id')
        
        # Validate wallet has sufficient balance
        if wallet_id and amount:
            try:
                wallet = Wallet.objects.get(id=wallet_id)
                if wallet.balance < amount:
                    raise serializers.ValidationError("Insufficient wallet balance.")
            except Wallet.DoesNotExist:
                raise serializers.ValidationError("Wallet does not exist.")
        
        # Validate processed_by is provided when status is approved or rejected
        if status in ['approved', 'rejected'] and not processed_by_id:
            raise serializers.ValidationError("Processed by user is required when status is approved or rejected.")
        
        return attrs


class WalletWithdrawalRequestListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for WalletWithdrawalRequest model used in list views.
    """
    wallet = WalletListSerializer(read_only=True)
    processed_by = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    wallet_transactions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = WalletWithdrawalRequest
        fields = [
            'id', 'wallet', 'amount', 'status', 'reason', 'admin_remarks',
            'processed_by', 'processed_at', 'created_by', 'created_at', 'wallet_transactions_count'
        ]
    
    def get_wallet_transactions_count(self, obj):
        """
        Get count of related wallet transactions.
        """
        return len(obj.get_wallet_transactions())


class WalletWithdrawalRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating withdrawal requests with minimal required fields.
    """
    wallet_id = serializers.IntegerField()
    created_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = WalletWithdrawalRequest
        fields = ['wallet_id', 'amount', 'reason', 'created_by_id']
    
    def validate_wallet_id(self, value):
        """
        Validate that wallet exists.
        """
        try:
            Wallet.objects.get(id=value)
        except Wallet.DoesNotExist:
            raise serializers.ValidationError("Wallet does not exist.")
        return value


class WalletWithdrawalRequestUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating withdrawal requests with selective field updates.
    """
    updated_by_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = WalletWithdrawalRequest
        fields = ['status', 'reason', 'admin_remarks', 'updated_by_id']


class WalletWithdrawalRequestStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating withdrawal request status.
    """
    status = serializers.ChoiceField(choices=WalletWithdrawalRequest.STATUS_CHOICES)
    admin_remarks = serializers.CharField(required=False, allow_blank=True)
    processed_by_id = serializers.IntegerField(required=False)
    
    def validate_status(self, value):
        """
        Validate status transition is allowed.
        """
        # Add business logic for status transitions here
        # For example, prevent moving from 'approved' to 'pending'
        return value


class WalletSearchSerializer(serializers.Serializer):
    """
    Serializer for wallet search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    min_balance = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_balance = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    user_id = serializers.IntegerField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        min_balance = attrs.get('min_balance')
        max_balance = attrs.get('max_balance')
        
        if min_balance is not None and max_balance is not None:
            if min_balance > max_balance:
                raise serializers.ValidationError("Min balance cannot be greater than max balance.")
        
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        return attrs


class WalletTransactionSearchSerializer(serializers.Serializer):
    """
    Serializer for wallet transaction search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    transaction_type = serializers.ChoiceField(
        choices=WalletTransaction.TRANSACTION_TYPE_CHOICES,
        required=False
    )
    min_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    user_id = serializers.IntegerField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        min_amount = attrs.get('min_amount')
        max_amount = attrs.get('max_amount')
        
        if min_amount is not None and max_amount is not None:
            if min_amount > max_amount:
                raise serializers.ValidationError("Min amount cannot be greater than max amount.")
        
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        return attrs


class WalletWithdrawalRequestSearchSerializer(serializers.Serializer):
    """
    Serializer for withdrawal request search functionality.
    """
    query = serializers.CharField(max_length=200, required=False)
    status = serializers.ChoiceField(
        choices=WalletWithdrawalRequest.STATUS_CHOICES,
        required=False
    )
    min_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    user_id = serializers.IntegerField(required=False)
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    
    def validate(self, attrs):
        """
        Validate search parameters.
        """
        min_amount = attrs.get('min_amount')
        max_amount = attrs.get('max_amount')
        
        if min_amount is not None and max_amount is not None:
            if min_amount > max_amount:
                raise serializers.ValidationError("Min amount cannot be greater than max amount.")
        
        created_after = attrs.get('created_after')
        created_before = attrs.get('created_before')
        
        if created_after and created_before:
            if created_after >= created_before:
                raise serializers.ValidationError("Created after date must be before created before date.")
        
        return attrs


class WalletFilterSerializer(serializers.Serializer):
    """
    Serializer for wallet filtering functionality.
    """
    balance_range = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    
    def validate_balance_range(self, value):
        """
        Validate balance range format.
        """
        if value:
            if 'min' not in value or 'max' not in value:
                raise serializers.ValidationError("Balance range must have 'min' and 'max' keys.")
            if value['min'] > value['max']:
                raise serializers.ValidationError("Min balance cannot be greater than max balance.")
        return value


class WalletTransactionFilterSerializer(serializers.Serializer):
    """
    Serializer for wallet transaction filtering functionality.
    """
    transaction_types = serializers.ListField(
        child=serializers.ChoiceField(choices=WalletTransaction.TRANSACTION_TYPE_CHOICES),
        required=False
    )
    amount_range = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    
    def validate_amount_range(self, value):
        """
        Validate amount range format.
        """
        if value:
            if 'min' not in value or 'max' not in value:
                raise serializers.ValidationError("Amount range must have 'min' and 'max' keys.")
            if value['min'] > value['max']:
                raise serializers.ValidationError("Min amount cannot be greater than max amount.")
        return value


class WalletWithdrawalRequestFilterSerializer(serializers.Serializer):
    """
    Serializer for withdrawal request filtering functionality.
    """
    statuses = serializers.ListField(
        child=serializers.ChoiceField(choices=WalletWithdrawalRequest.STATUS_CHOICES),
        required=False
    )
    amount_range = serializers.DictField(
        child=serializers.DecimalField(max_digits=10, decimal_places=2),
        required=False
    )
    created_after = serializers.DateTimeField(required=False)
    created_before = serializers.DateTimeField(required=False)
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )
    
    def validate_amount_range(self, value):
        """
        Validate amount range format.
        """
        if value:
            if 'min' not in value or 'max' not in value:
                raise serializers.ValidationError("Amount range must have 'min' and 'max' keys.")
            if value['min'] > value['max']:
                raise serializers.ValidationError("Min amount cannot be greater than max amount.")
        return value


class WalletAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for wallet analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['created_by', 'balance_range'],
        required=False
    )
    
    def validate(self, attrs):
        """
        Validate date range and grouping options.
        """
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class WalletTransactionAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for wallet transaction analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['transaction_type', 'created_by', 'amount_range'],
        required=False
    )
    
    def validate(self, attrs):
        """
        Validate date range and grouping options.
        """
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class WalletWithdrawalRequestAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for withdrawal request analytics data.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=['status', 'created_by', 'amount_range'],
        required=False
    )
    
    def validate(self, attrs):
        """
        Validate date range and grouping options.
        """
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class BulkWalletUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk wallet updates.
    """
    wallet_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_wallet_ids(self, value):
        """
        Validate that all wallets exist.
        """
        existing_wallets = Wallet.objects.filter(id__in=value).count()
        if existing_wallets != len(value):
            raise serializers.ValidationError("One or more wallets do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['balance']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class BulkWalletWithdrawalRequestUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk withdrawal request updates.
    """
    request_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )
    updates = serializers.DictField()
    
    def validate_request_ids(self, value):
        """
        Validate that all withdrawal requests exist.
        """
        existing_requests = WalletWithdrawalRequest.objects.filter(id__in=value).count()
        if existing_requests != len(value):
            raise serializers.ValidationError("One or more withdrawal requests do not exist.")
        return value
    
    def validate_updates(self, value):
        """
        Validate update fields.
        """
        allowed_fields = ['status', 'admin_remarks']
        for field in value.keys():
            if field not in allowed_fields:
                raise serializers.ValidationError(f"Field '{field}' is not allowed for bulk update.")
        return value


class WalletTransactionCreateSerializer(serializers.Serializer):
    """
    Serializer for creating wallet transactions with wallet validation.
    """
    wallet_id = serializers.IntegerField()
    transaction_type = serializers.ChoiceField(choices=WalletTransaction.TRANSACTION_TYPE_CHOICES)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    description = serializers.CharField(required=False, allow_blank=True)
    reference_id = serializers.CharField(required=False, allow_blank=True)
    created_by_id = serializers.IntegerField(required=False)
    
    def validate_wallet_id(self, value):
        """
        Validate that wallet exists.
        """
        try:
            Wallet.objects.get(id=value)
        except Wallet.DoesNotExist:
            raise serializers.ValidationError("Wallet does not exist.")
        return value
    
    def validate_amount(self, value):
        """
        Validate amount is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class WalletBalanceUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating wallet balance.
    """
    wallet_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = serializers.ChoiceField(choices=WalletTransaction.TRANSACTION_TYPE_CHOICES)
    description = serializers.CharField(required=False, allow_blank=True)
    reference_id = serializers.CharField(required=False, allow_blank=True)
    updated_by_id = serializers.IntegerField(required=False)
    
    def validate_wallet_id(self, value):
        """
        Validate that wallet exists.
        """
        try:
            Wallet.objects.get(id=value)
        except Wallet.DoesNotExist:
            raise serializers.ValidationError("Wallet does not exist.")
        return value
    
    def validate_amount(self, value):
        """
        Validate amount is positive.
        """
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value
    
    def validate(self, attrs):
        """
        Validate business logic for balance updates.
        """
        wallet_id = attrs.get('wallet_id')
        amount = attrs.get('amount')
        transaction_type = attrs.get('transaction_type')
        
        if wallet_id and amount and transaction_type:
            try:
                wallet = Wallet.objects.get(id=wallet_id)
                if transaction_type == 'debit' and wallet.balance < amount:
                    raise serializers.ValidationError("Insufficient wallet balance for debit transaction.")
            except Wallet.DoesNotExist:
                raise serializers.ValidationError("Wallet does not exist.")
        
        return attrs
from django.contrib.auth.models import User
from .models import Wallet, WalletTransaction, WalletWithdrawalRequest
from common.relations import get_related


class WalletAdminSerializer(serializers.ModelSerializer):
    """
    Serializer for wallet information in admin panel.
    """
    user = serializers.SerializerMethodField()
    transaction_count = serializers.SerializerMethodField()
    pending_withdrawals = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = [
            'id', 'balance', 'created_at', 'updated_at', 'user',
            'transaction_count', 'pending_withdrawals'
        ]
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at', 'user', 'transaction_count', 'pending_withdrawals']
    
    def get_user(self, obj):
        """Get user information"""
        users = get_related(obj, 'Wallet:User', User)
        if users.exists():
            user = users.first()
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        return None
    
    def get_transaction_count(self, obj):
        """Get count of wallet transactions"""
        return obj.wallettransaction_set.count()
    
    def get_pending_withdrawals(self, obj):
        """Get count of pending withdrawal requests"""
        return obj.walletwithdrawalrequest_set.filter(status='pending').count()


class WalletTransactionAdminSerializer(serializers.ModelSerializer):
    """
    Serializer for wallet transactions in admin panel.
    """
    user = serializers.SerializerMethodField()
    wallet = WalletAdminSerializer(read_only=True)
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'wallet', 'wallet_transaction_type', 'amount', 'description',
            'reference_id', 'created_at', 'user'
        ]
        read_only_fields = ['id', 'wallet', 'wallet_transaction_type', 'amount', 'description', 'reference_id', 'created_at', 'user']
    
    def get_user(self, obj):
        """Get user information"""
        users = get_related(obj.wallet, 'Wallet:User', User)
        if users.exists():
            user = users.first()
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        return None


class WalletWithdrawalRequestAdminSerializer(serializers.ModelSerializer):
    """
    Serializer for wallet withdrawal requests in admin panel.
    """
    user = serializers.SerializerMethodField()
    wallet = WalletAdminSerializer(read_only=True)
    approved_by = serializers.SerializerMethodField()
    
    class Meta:
        model = WalletWithdrawalRequest
        fields = [
            'id', 'wallet', 'amount', 'status', 'request_date', 'processed_date',
            'razorpay_payout_id', 'admin_notes', 'user', 'approved_by'
        ]
        read_only_fields = ['id', 'wallet', 'amount', 'status', 'request_date', 'processed_date', 'razorpay_payout_id', 'admin_notes', 'user', 'approved_by']
    
    def get_user(self, obj):
        """Get user information"""
        users = get_related(obj.wallet, 'Wallet:User', User)
        if users.exists():
            user = users.first()
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        return None
    
    def get_approved_by(self, obj):
        """Get admin user who approved the withdrawal"""
        if obj.approved_by_id:
            try:
                admin_user = User.objects.get(id=obj.approved_by_id)
                return {
                    'id': admin_user.id,
                    'username': admin_user.username,
                    'email': admin_user.email,
                    'first_name': admin_user.first_name,
                    'last_name': admin_user.last_name
                }
            except User.DoesNotExist:
                return None
        return None


class WalletAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for wallet analytics.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    group_by = serializers.ChoiceField(
        choices=[('day', 'Day'), ('week', 'Week'), ('month', 'Month')],
        required=False
    )
    
    def validate(self, attrs):
        """Validate analytics parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        return attrs


class WalletFilterSerializer(serializers.Serializer):
    """
    Serializer for wallet filtering.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    transaction_type = serializers.ChoiceField(
        choices=[('credit', 'Credit'), ('debit', 'Debit')],
        required=False
    )
    min_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    user_id = serializers.IntegerField(required=False)
    
    def validate(self, attrs):
        """Validate filter parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        min_amount = attrs.get('min_amount')
        max_amount = attrs.get('max_amount')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        if min_amount is not None and max_amount is not None:
            if min_amount > max_amount:
                raise serializers.ValidationError("Min amount cannot be greater than max amount.")
        
        return attrs


class WithdrawalFilterSerializer(serializers.Serializer):
    """
    Serializer for withdrawal request filtering.
    """
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    status = serializers.ChoiceField(
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('processed', 'Processed')],
        required=False
    )
    min_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    user_id = serializers.IntegerField(required=False)
    
    def validate(self, attrs):
        """Validate filter parameters"""
        start_date = attrs.get('start_date')
        end_date = attrs.get('end_date')
        min_amount = attrs.get('min_amount')
        max_amount = attrs.get('max_amount')
        
        if start_date and end_date:
            if start_date >= end_date:
                raise serializers.ValidationError("Start date must be before end date.")
        
        if min_amount is not None and max_amount is not None:
            if min_amount > max_amount:
                raise serializers.ValidationError("Min amount cannot be greater than max amount.")
        
        return attrs
