from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Q
from django.utils import timezone
from .models import Wallet, WalletTransaction, WalletWithdrawalRequest
from .serializers import (
    WalletSerializer, WalletTransactionSerializer, WalletWithdrawalRequestSerializer
)


@swagger_auto_schema(
    method='get',
    operation_summary='Get Wallet Balance',
    operation_description='Get user wallet balance and details.',
    responses={
        200: openapi.Response(
            description='Wallet balance retrieved successfully',
            examples={
                'application/json': {
                    'wallet': {
                        'id': 1,
                        'balance': 150.75,
                        'created_at': '2024-01-01T00:00:00Z',
                        'updated_at': '2024-01-01T00:00:00Z'
                    },
                    'balance': 150.75
                }
            }
        ),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Wallet']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_balance(request):
    """
    Get user's wallet balance and details.
    """
    try:
        wallet = Wallet.objects.get(created_by=request.user)
    except Wallet.DoesNotExist:
        # Create wallet if it doesn't exist
        wallet = Wallet.objects.create(created_by=request.user)
    
    try:
        wallet_data = WalletSerializer(wallet).data
    except Exception as e:
        # If serialization fails, return minimal wallet data
        wallet_data = {
            'id': wallet.id,
            'balance': float(wallet.balance),
            'created_at': wallet.created_at.isoformat() if wallet.created_at else None,
            'updated_at': wallet.updated_at.isoformat() if wallet.updated_at else None,
            'transactions': [],
            'withdrawal_requests': []
        }
    
    return Response({
        'wallet': wallet_data,
        'balance': float(wallet.balance)
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Wallet Transactions',
    operation_description='Wallet Transactions endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_transactions(request):
    """
    Get user's wallet transaction history.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        wallet = Wallet.objects.get(created_by=request.user)
    except Wallet.DoesNotExist:
        wallet = Wallet.objects.create(created_by=request.user)
    
    # Get transactions both by created_by and through wallet relations
    from common.relations import get_related
    
    # Get transactions created by user
    transactions_by_user = WalletTransaction.objects.filter(created_by=request.user)
    
    # Get transactions linked to wallet through relations
    transactions_by_wallet = get_related(wallet, 'Wallet:WalletTransaction', WalletTransaction)
    
    # Combine both querysets and remove duplicates
    all_transaction_ids = set(transactions_by_user.values_list('id', flat=True))
    all_transaction_ids.update(transactions_by_wallet.values_list('id', flat=True))
    
    # Get all unique transactions ordered by created_at
    transactions = WalletTransaction.objects.filter(id__in=all_transaction_ids).order_by('-created_at')
    
    # Log transaction count for debugging
    transaction_count = transactions.count()
    logger.info(f"Wallet transactions query for user {request.user.id}: Found {transaction_count} transactions (by user: {transactions_by_user.count()}, by wallet: {transactions_by_wallet.count()})")
    
    # Get transaction summary
    total_credit = transactions.filter(wallet_transaction_type='credit').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    total_debit = transactions.filter(wallet_transaction_type='debit').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    try:
        wallet_data = WalletSerializer(wallet).data
    except Exception as e:
        logger.error(f"Failed to serialize wallet data: {str(e)}", exc_info=True)
        # If serialization fails, return minimal wallet data
        wallet_data = {
            'id': wallet.id,
            'balance': float(wallet.balance),
            'created_at': wallet.created_at.isoformat() if wallet.created_at else None,
            'updated_at': wallet.updated_at.isoformat() if wallet.updated_at else None,
            'transactions': [],
            'withdrawal_requests': []
        }
    
    try:
        transactions_data = WalletTransactionSerializer(transactions, many=True).data
        logger.info(f"Successfully serialized {len(transactions_data)} transactions")
    except Exception as e:
        logger.error(f"Failed to serialize wallet transactions: {str(e)}", exc_info=True)
        # If serialization fails, return empty list
        transactions_data = []
    
    response_data = {
        'wallet': wallet_data,
        'transactions': transactions_data,
        'summary': {
            'total_credit': float(total_credit),
            'total_debit': float(total_debit),
            'current_balance': float(wallet.balance),
            'total_transactions': transaction_count
        }
    }
    
    logger.info(f"Returning wallet transactions response with {len(transactions_data)} transactions")
    
    return Response(response_data)


@swagger_auto_schema(
    method='post',
    operation_summary='Add Wallet Balance',
    operation_description='Add money to user wallet balance.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'amount': openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description='Amount to add to wallet',
                example=50.00
            ),
            'payment_method': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Payment method',
                example='razorpay',
                enum=['razorpay', 'bank_transfer']
            ),
            'description': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Transaction description',
                example='Wallet top-up'
            )
        },
        required=['amount', 'payment_method']
    ),
    responses={
        201: openapi.Response(
            description='Balance added successfully',
            examples={
                'application/json': {
                    'message': 'Balance added successfully',
                    'transaction': {
                        'id': 1,
                        'amount': 50.00,
                        'type': 'credit',
                        'description': 'Wallet top-up',
                        'created_at': '2024-01-01T00:00:00Z'
                    },
                    'new_balance': 200.75
                }
            }
        ),
        400: openapi.Response(description='Bad request - invalid amount or payment method'),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Wallet']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_wallet_balance(request):
    """
    Add balance to user's wallet.
    """
    amount = request.data.get('amount')
    description = request.data.get('description', 'Wallet top-up')
    reference_id = request.data.get('reference_id')
    
    if not amount or float(amount) <= 0:
        return Response({
            'error': 'Valid amount is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        wallet = Wallet.objects.get(created_by=request.user)
    except Wallet.DoesNotExist:
        wallet = Wallet.objects.create(created_by=request.user)
    
    # Create credit transaction
    transaction = WalletTransaction.objects.create(
        wallet_transaction_type='credit',
        amount=amount,
        description=description,
        reference_id=reference_id,
        created_by=request.user
    )
    
    # Update wallet balance
    wallet.balance += float(amount)
    wallet.save()
    
    # Attach transaction to wallet
    wallet.attach_wallet_transaction(transaction)
    
    return Response({
        'message': 'Balance added successfully',
        'transaction': WalletTransactionSerializer(transaction).data,
        'new_balance': float(wallet.balance)
    }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='post',
    operation_summary='Deduct Wallet Balance',
    operation_description='Deduct Wallet Balance endpoint',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'data': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Request data'
            )
        }
    ),
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deduct_wallet_balance(request):
    """
    Deduct balance from user's wallet.
    """
    amount = request.data.get('amount')
    description = request.data.get('description', 'Wallet deduction')
    reference_id = request.data.get('reference_id')
    
    if not amount or float(amount) <= 0:
        return Response({
            'error': 'Valid amount is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        wallet = Wallet.objects.get(created_by=request.user)
    except Wallet.DoesNotExist:
        wallet = Wallet.objects.create(created_by=request.user)
    
    # Check if sufficient balance
    if wallet.balance < float(amount):
        return Response({
            'error': 'Insufficient wallet balance'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create debit transaction
    transaction = WalletTransaction.objects.create(
        wallet_transaction_type='debit',
        amount=amount,
        description=description,
        reference_id=reference_id,
        created_by=request.user
    )
    
    # Update wallet balance
    wallet.balance -= float(amount)
    wallet.save()
    
    # Attach transaction to wallet
    wallet.attach_wallet_transaction(transaction)
    
    return Response({
        'message': 'Balance deducted successfully',
        'transaction': WalletTransactionSerializer(transaction).data,
        'new_balance': float(wallet.balance)
    }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='post',
    operation_summary='Create Withdrawal Request',
    operation_description='Create a withdrawal request from wallet balance.',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'amount': openapi.Schema(
                type=openapi.TYPE_NUMBER,
                description='Amount to withdraw',
                example=100.00
            ),
            'reason': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Reason for withdrawal',
                example='Monthly payout request'
            )
        },
        required=['amount']
    ),
    responses={
        201: openapi.Response(
            description='Withdrawal request created successfully',
            examples={
                'application/json': {
                    'message': 'Withdrawal request created successfully',
                    'withdrawal_request': {
                        'id': 1,
                        'amount': 100.00,
                        'status': 'pending',
                        'reason': 'Monthly payout request',
                        'created_at': '2024-01-01T00:00:00Z'
                    }
                }
            }
        ),
        400: openapi.Response(description='Bad request - insufficient balance or pending request exists'),
        401: openapi.Response(description='Unauthorized - authentication required')
    },
    tags=['Wallet']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_withdrawal_request(request):
    """
    Create a withdrawal request from wallet.
    """
    amount = request.data.get('amount')
    reason = request.data.get('reason', '')
    
    if not amount or float(amount) <= 0:
        return Response({
            'error': 'Valid amount is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        wallet = Wallet.objects.get(created_by=request.user)
    except Wallet.DoesNotExist:
        wallet = Wallet.objects.create(created_by=request.user)
    
    # Check if sufficient balance
    if wallet.balance < float(amount):
        return Response({
            'error': 'Insufficient wallet balance'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check for pending withdrawal requests
    pending_requests = WalletWithdrawalRequest.objects.filter(
        wallet=wallet,
        status='pending'
    ).count()
    
    if pending_requests > 0:
        return Response({
            'error': 'You already have a pending withdrawal request'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Create withdrawal request
    withdrawal_request = WalletWithdrawalRequest.objects.create(
        wallet=wallet,
        amount=amount,
        reason=reason,
        created_by=request.user
    )
    
    return Response({
        'message': 'Withdrawal request created successfully',
        'withdrawal_request': WalletWithdrawalRequestSerializer(withdrawal_request).data
    }, status=status.HTTP_201_CREATED)


@swagger_auto_schema(
    method='get',
    operation_summary='Withdrawal Requests',
    operation_description='Withdrawal Requests endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def withdrawal_requests(request):
    """
    Get user's withdrawal requests.
    """
    try:
        wallet = Wallet.objects.get(created_by=request.user)
    except Wallet.DoesNotExist:
        wallet = Wallet.objects.create(created_by=request.user)
    
    requests = WalletWithdrawalRequest.objects.filter(
        wallet=wallet
    ).order_by('-created_at')
    
    return Response({
        'withdrawal_requests': WalletWithdrawalRequestSerializer(requests, many=True).data,
        'total_requests': requests.count()
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Withdrawal Request Detail',
    operation_description='Withdrawal Request Detail endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def withdrawal_request_detail(request, request_id):
    """
    Get details of a specific withdrawal request.
    """
    try:
        withdrawal_request = WalletWithdrawalRequest.objects.get(
            id=request_id,
            wallet__created_by=request.user
        )
        return Response({
            'withdrawal_request': WalletWithdrawalRequestSerializer(withdrawal_request).data
        })
    except WalletWithdrawalRequest.DoesNotExist:
        return Response({
            'error': 'Withdrawal request not found'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='post',
    operation_summary='Cancel Withdrawal Request',
    operation_description='Cancel Withdrawal Request endpoint',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'data': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Request data'
            )
        }
    ),
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_withdrawal_request(request, request_id):
    """
    Cancel a pending withdrawal request.
    """
    try:
        withdrawal_request = WalletWithdrawalRequest.objects.get(
            id=request_id,
            wallet__created_by=request.user,
            status='pending'
        )
        
        withdrawal_request.status = 'rejected'
        withdrawal_request.admin_remarks = 'Cancelled by user'
        withdrawal_request.save()
        
        return Response({
            'message': 'Withdrawal request cancelled successfully',
            'withdrawal_request': WalletWithdrawalRequestSerializer(withdrawal_request).data
        })
    
    except WalletWithdrawalRequest.DoesNotExist:
        return Response({
            'error': 'Withdrawal request not found or cannot be cancelled'
        }, status=status.HTTP_404_NOT_FOUND)


@swagger_auto_schema(
    method='get',
    operation_summary='Wallet Summary',
    operation_description='Wallet Summary endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_summary(request):
    """
    Get comprehensive wallet summary.
    """
    try:
        wallet = Wallet.objects.get(created_by=request.user)
    except Wallet.DoesNotExist:
        wallet = Wallet.objects.create(created_by=request.user)
    
    # Get transaction statistics
    transactions = WalletTransaction.objects.filter(created_by=request.user)
    
    credit_transactions = transactions.filter(wallet_transaction_type='credit')
    debit_transactions = transactions.filter(wallet_transaction_type='debit')
    
    total_credit = credit_transactions.aggregate(total=Sum('amount'))['total'] or 0
    total_debit = debit_transactions.aggregate(total=Sum('amount'))['total'] or 0
    
    # Get withdrawal requests
    withdrawal_requests = WalletWithdrawalRequest.objects.filter(wallet=wallet)
    pending_withdrawals = withdrawal_requests.filter(status='pending').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    try:
        wallet_data = WalletSerializer(wallet).data
    except Exception as e:
        # If serialization fails, return minimal wallet data
        wallet_data = {
            'id': wallet.id,
            'balance': float(wallet.balance),
            'created_at': wallet.created_at.isoformat() if wallet.created_at else None,
            'updated_at': wallet.updated_at.isoformat() if wallet.updated_at else None,
            'transactions': [],
            'withdrawal_requests': []
        }
    
    return Response({
        'wallet': wallet_data,
        'summary': {
            'current_balance': float(wallet.balance),
            'total_credit': float(total_credit),
            'total_debit': float(total_debit),
            'pending_withdrawals': float(pending_withdrawals),
            'total_transactions': transactions.count(),
            'credit_transactions': credit_transactions.count(),
            'debit_transactions': debit_transactions.count(),
            'withdrawal_requests': withdrawal_requests.count()
        }
    })


@swagger_auto_schema(
    method='get',
    operation_summary='Recent Transactions',
    operation_description='Recent Transactions endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recent_transactions(request):
    """
    Get recent wallet transactions.
    """
    try:
        wallet = Wallet.objects.get(created_by=request.user)
    except Wallet.DoesNotExist:
        wallet = Wallet.objects.create(created_by=request.user)
    
    limit = int(request.GET.get('limit', 10))
    transactions = WalletTransaction.objects.filter(
        created_by=request.user
    ).order_by('-created_at')[:limit]
    
    try:
        transactions_data = WalletTransactionSerializer(transactions, many=True).data
    except Exception as e:
        # If serialization fails, return empty list
        transactions_data = []
    
    return Response({
        'recent_transactions': transactions_data,
        'total_count': transactions.count()
    })


@swagger_auto_schema(
    method='post',
    operation_summary='Transfer To Wallet',
    operation_description='Transfer To Wallet endpoint',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'data': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Request data'
            )
        }
    ),
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def transfer_to_wallet(request):
    """
    Transfer amount from one user's wallet to another.
    """
    recipient_username = request.data.get('recipient_username')
    amount = request.data.get('amount')
    description = request.data.get('description', 'Wallet transfer')
    
    if not all([recipient_username, amount]):
        return Response({
            'error': 'Recipient username and amount are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if float(amount) <= 0:
        return Response({
            'error': 'Valid amount is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from django.contrib.auth.models import User
        recipient = User.objects.get(username=recipient_username)
    except User.DoesNotExist:
        return Response({
            'error': 'Recipient user not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Get sender's wallet
    try:
        sender_wallet = Wallet.objects.get(created_by=request.user)
    except Wallet.DoesNotExist:
        sender_wallet = Wallet.objects.create(created_by=request.user)
    
    # Check sender's balance
    if sender_wallet.balance < float(amount):
        return Response({
            'error': 'Insufficient wallet balance'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get or create recipient's wallet
    try:
        recipient_wallet = Wallet.objects.get(created_by=recipient)
    except Wallet.DoesNotExist:
        recipient_wallet = Wallet.objects.create(created_by=recipient)
    
    # Create debit transaction for sender
    sender_transaction = WalletTransaction.objects.create(
        wallet_transaction_type='debit',
        amount=amount,
        description=f"Transfer to {recipient_username}: {description}",
        reference_id=f"transfer_{request.user.id}_{recipient.id}",
        created_by=request.user
    )
    
    # Create credit transaction for recipient
    recipient_transaction = WalletTransaction.objects.create(
        wallet_transaction_type='credit',
        amount=amount,
        description=f"Transfer from {request.user.username}: {description}",
        reference_id=f"transfer_{request.user.id}_{recipient.id}",
        created_by=recipient
    )
    
    # Update wallet balances
    sender_wallet.balance -= float(amount)
    sender_wallet.save()
    
    recipient_wallet.balance += float(amount)
    recipient_wallet.save()
    
    # Attach transactions to wallets
    sender_wallet.attach_wallet_transaction(sender_transaction)
    recipient_wallet.attach_wallet_transaction(recipient_transaction)
    
    return Response({
        'message': 'Transfer completed successfully',
        'sender_transaction': WalletTransactionSerializer(sender_transaction).data,
        'recipient_transaction': WalletTransactionSerializer(recipient_transaction).data,
        'sender_balance': float(sender_wallet.balance)
    }, status=status.HTTP_201_CREATED)


# ==================== DESIGNER CONSOLE - SETTLEMENT & PAYOUTS ====================

@swagger_auto_schema(
    method='get',
    operation_summary='Settlement Status',
    operation_description='Settlement Status endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def settlement_status(request):
    """
    Get current settlement status and check if settlement window is active.
    """
    from datetime import datetime
    import pytz
    
    # Get current date in Asia/Kolkata timezone
    kolkata_tz = pytz.timezone('Asia/Kolkata')
    current_date = datetime.now(kolkata_tz)
    current_day = current_date.day
    
    # Check if we're in settlement window (days 5-10)
    settlement_window_active = 5 <= current_day <= 10
    
    # TODO: Get settlement request for current period
    # settlement_request = SettlementRequest.objects.filter(
    #     designer=request.user,
    #     status='PENDING'
    # ).first()
    
    settlement_data = {
        'settlement_window_active': settlement_window_active,
        'current_day': current_day,
        'settlement_window_days': [5, 6, 7, 8, 9, 10],
        'settlement_request': None,  # TODO: Get from SettlementRequest model
        'can_accept_settlement': False,
        'linked_account_verified': False  # TODO: Check Razorpay account verification
    }
    
    if settlement_window_active:
        # TODO: Check if designer has pending settlement
        # if settlement_request:
        #     settlement_data['settlement_request'] = SettlementRequestSerializer(settlement_request).data
        #     settlement_data['can_accept_settlement'] = True
        pass
    
    return Response(settlement_data)


@swagger_auto_schema(
    method='post',
    operation_summary='Accept Settlement',
    operation_description='Accept Settlement endpoint',
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'data': openapi.Schema(
                type=openapi.TYPE_STRING,
                description='Request data'
            )
        }
    ),
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_settlement(request):
    """
    Accept settlement during the settlement window (days 5-10).
    """
    from datetime import datetime
    import pytz
    
    # Check if we're in settlement window
    kolkata_tz = pytz.timezone('Asia/Kolkata')
    current_date = datetime.now(kolkata_tz)
    current_day = current_date.day
    
    if not (5 <= current_day <= 10):
        return Response({
            'error': 'Settlement window is not active. Settlement can only be accepted between days 5-10 of each month.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # TODO: Get settlement request
    # try:
    #     settlement_request = SettlementRequest.objects.get(
    #         designer=request.user,
    #         status='PENDING'
    #     )
    # except SettlementRequest.DoesNotExist:
    #     return Response({
    #         'error': 'No pending settlement request found'
    #     }, status=status.HTTP_404_NOT_FOUND)
    
    # TODO: Check if linked account is verified
    # if not razorpay_service.is_account_verified(request.user):
    #     return Response({
    #         'error': 'Razorpay account is not verified. Please complete verification first.'
    #     }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # TODO: Accept settlement
        # settlement_request.status = 'ACCEPTED'
        # settlement_request.accepted_at = timezone.now()
        # settlement_request.save()
        
        # TODO: Schedule payout for day 11
        # payout_date = current_date.replace(day=11)
        # payments.tasks.schedule_payout.delay(
        #     settlement_request.id,
        #     payout_date
        # )
        
        # Send confirmation notifications (handled by signals)
        # The post_save signal will automatically send the notification
        
        return Response({
            'message': 'Settlement accepted successfully',
            'scheduled_payout_date': 'Day 11 of current month',  # TODO: Calculate actual date
            'settlement_reference_id': 'SETTLEMENT_REF_123',  # TODO: Generate actual reference
            'payout_breakdown': {
                'gross_earnings': 0,  # TODO: Calculate from settlement
                'platform_fee': 0,   # TODO: Calculate platform fee
                'net_payable': 0     # TODO: Calculate net amount
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'Failed to accept settlement: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@swagger_auto_schema(
    method='get',
    operation_summary='Settlement History',
    operation_description='Settlement History endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def settlement_history(request):
    """
    Get settlement history for the designer.
    """
    # TODO: Get settlement history from SettlementRequest model
    # settlements = SettlementRequest.objects.filter(
    #     designer=request.user
    # ).order_by('-created_at')
    
    settlement_history = {
        'settlements': [],  # TODO: Serialize settlement requests
        'total_settlements': 0,
        'total_paid': 0,
        'pending_settlements': 0
    }
    
    return Response(settlement_history)


@swagger_auto_schema(
    method='get',
    operation_summary='Payout History',
    operation_description='Payout History endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_history(request):
    """
    Get payout history for the designer.
    """
    # TODO: Get payout history from Payout model
    # payouts = Payout.objects.filter(
    #     designer=request.user
    # ).order_by('-created_at')
    
    payout_history = {
        'payouts': [],  # TODO: Serialize payouts
        'total_payouts': 0,
        'total_amount_paid': 0,
        'pending_payouts': 0
    }
    
    return Response(payout_history)


@swagger_auto_schema(
    method='get',
    operation_summary='Earnings Summary',
    operation_description='Earnings Summary endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def earnings_summary(request):
    """
    Get earnings summary for the designer.
    """
    from django.db.models import Sum
    from datetime import datetime, timedelta
    
    # Get current month earnings
    current_month = datetime.now().replace(day=1)
    monthly_earnings = WalletTransaction.objects.filter(
        created_by=request.user,
        wallet_transaction_type='credit',
        created_at__gte=current_month
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Get lifetime earnings
    lifetime_earnings = WalletTransaction.objects.filter(
        created_by=request.user,
        wallet_transaction_type='credit'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Get pending withdrawals
    pending_withdrawals = WalletWithdrawalRequest.objects.filter(
        wallet__created_by=request.user,
        status='pending'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # TODO: Get earnings from last withdrawal to now for settlement
    # last_withdrawal_date = get_last_withdrawal_date(request.user)
    # earnings_since_last_withdrawal = calculate_earnings_since(request.user, last_withdrawal_date)
    
    earnings_summary = {
        'monthly_earnings': float(monthly_earnings),
        'lifetime_earnings': float(lifetime_earnings),
        'pending_withdrawals': float(pending_withdrawals),
        'current_wallet_balance': float(Wallet.objects.get(created_by=request.user).balance),
        'earnings_since_last_settlement': 0,  # TODO: Calculate
        'platform_fee_percentage': 10,  # TODO: Get from settings
        'next_settlement_eligible': True  # TODO: Check if eligible for next settlement
    }
    
    return Response(earnings_summary)


@swagger_auto_schema(
    method='get',
    operation_summary='Linked Account Status',
    operation_description='Linked Account Status endpoint',
    responses={
        200: openapi.Response(
            description='Success',
            examples={
                'application/json': {
                    'message': 'Success',
                    'data': {}
                }
            }
        ),
        400: openapi.Response(description='Bad request')
    },
    tags=['API']
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def linked_account_status(request):
    """
    Get Razorpay linked account status and verification details.
    """
    # TODO: Get linked account status from Razorpay
    # account_status = razorpay_service.get_linked_account_status(request.user)
    
    account_status = {
        'account_created': False,  # TODO: Check if account exists
        'verification_status': 'pending',  # TODO: Get from Razorpay
        'verification_documents_required': [],  # TODO: Get required documents
        'verification_documents_submitted': [],  # TODO: Get submitted documents
        'account_id': None,  # TODO: Get Razorpay account ID
        'payouts_enabled': False,  # TODO: Check if payouts are enabled
        'verification_errors': []  # TODO: Get any verification errors
    }
    
    return Response(account_status)
