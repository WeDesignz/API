"""
Comprehensive tests for Wallet app
Tests wallet management, transactions, and withdrawals
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json
from unittest.mock import patch, MagicMock
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from decimal import Decimal

from .models import Wallet, WalletTransaction, WalletWithdrawalRequest


class WalletAPITestCase(APITestCase):
    """Test cases for Wallet API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User',
            is_active=True
        )
        
        self.designer = User.objects.create_user(
            username='designer',
            email='designer@example.com',
            password='password123',
            first_name='Designer',
            last_name='User',
            is_active=True
        )
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin123',
            first_name='Admin',
            last_name='User',
            is_active=True,
            is_staff=True
        )
        
        # Create wallet
        self.wallet = Wallet.objects.create(
            user=self.designer,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        # Create wallet transaction
        self.wallet_transaction = WalletTransaction.objects.create(
            wallet=self.wallet,
            transaction_type='credit',
            amount=Decimal('500.00'),
            description='Design sale payment',
            reference_id='TXN123456',
            status='completed'
        )
        
        # Create withdrawal request
        self.withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=self.wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='pending'
        )
    
    def test_wallet_list_success(self):
        """Test successful wallet list retrieval"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_wallet_list_with_filters(self):
        """Test wallet list with filters"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_list')
        params = {
            'is_active': 'true',
            'min_balance': '100.00',
            'max_balance': '2000.00',
            'user': self.designer.id
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_wallet_detail_success(self):
        """Test successful wallet detail retrieval"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_detail', kwargs={'wallet_id': self.wallet.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('user', response.data)
        self.assertIn('balance', response.data)
        self.assertIn('is_active', response.data)
        self.assertIn('created_at', response.data)
    
    def test_wallet_detail_not_found(self):
        """Test wallet detail with non-existent wallet"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_detail', kwargs={'wallet_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_wallet_create_success(self):
        """Test successful wallet creation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_create')
        data = {
            'balance': '0.00',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('wallet', response.data)
    
    def test_wallet_create_unauthorized(self):
        """Test wallet creation without authentication"""
        url = reverse('wallet_create')
        data = {
            'balance': '0.00',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_update_success(self):
        """Test successful wallet update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_update', kwargs={'wallet_id': self.wallet.id})
        data = {
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('wallet', response.data)
    
    def test_wallet_update_unauthorized(self):
        """Test wallet update without authentication"""
        url = reverse('wallet_update', kwargs={'wallet_id': self.wallet.id})
        data = {
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_balance_update_success(self):
        """Test successful wallet balance update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_balance_update', kwargs={'wallet_id': self.wallet.id})
        data = {
            'amount': '100.00',
            'transaction_type': 'credit',
            'description': 'Manual balance adjustment',
            'reference_id': 'ADJ123456'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('wallet', response.data)
        self.assertIn('transaction', response.data)
    
    def test_wallet_balance_update_unauthorized(self):
        """Test wallet balance update without authentication"""
        url = reverse('wallet_balance_update', kwargs={'wallet_id': self.wallet.id})
        data = {
            'amount': '100.00',
            'transaction_type': 'credit',
            'description': 'Manual balance adjustment',
            'reference_id': 'ADJ123456'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_transaction_list_success(self):
        """Test successful wallet transaction list retrieval"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_transaction_list', kwargs={'wallet_id': self.wallet.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_wallet_transaction_list_with_filters(self):
        """Test wallet transaction list with filters"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_transaction_list', kwargs={'wallet_id': self.wallet.id})
        params = {
            'transaction_type': 'credit',
            'status': 'completed',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'min_amount': '100.00',
            'max_amount': '1000.00'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_wallet_transaction_list_unauthorized(self):
        """Test wallet transaction list without authentication"""
        url = reverse('wallet_transaction_list', kwargs={'wallet_id': self.wallet.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_transaction_detail_success(self):
        """Test successful wallet transaction detail retrieval"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_transaction_detail', kwargs={'transaction_id': self.wallet_transaction.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('wallet', response.data)
        self.assertIn('transaction_type', response.data)
        self.assertIn('amount', response.data)
        self.assertIn('description', response.data)
        self.assertIn('reference_id', response.data)
        self.assertIn('status', response.data)
        self.assertIn('created_at', response.data)
    
    def test_wallet_transaction_detail_not_found(self):
        """Test wallet transaction detail with non-existent transaction"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_transaction_detail', kwargs={'transaction_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_wallet_transaction_create_success(self):
        """Test successful wallet transaction creation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_transaction_create', kwargs={'wallet_id': self.wallet.id})
        data = {
            'transaction_type': 'debit',
            'amount': '50.00',
            'description': 'Design purchase',
            'reference_id': 'PUR123456',
            'status': 'completed'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('transaction', response.data)
    
    def test_wallet_transaction_create_unauthorized(self):
        """Test wallet transaction creation without authentication"""
        url = reverse('wallet_transaction_create', kwargs={'wallet_id': self.wallet.id})
        data = {
            'transaction_type': 'debit',
            'amount': '50.00',
            'description': 'Design purchase',
            'reference_id': 'PUR123456',
            'status': 'completed'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_transaction_update_success(self):
        """Test successful wallet transaction update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_transaction_update', kwargs={'transaction_id': self.wallet_transaction.id})
        data = {
            'status': 'failed',
            'failure_reason': 'Insufficient funds'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('transaction', response.data)
    
    def test_wallet_transaction_update_unauthorized(self):
        """Test wallet transaction update without authentication"""
        url = reverse('wallet_transaction_update', kwargs={'transaction_id': self.wallet_transaction.id})
        data = {
            'status': 'failed',
            'failure_reason': 'Insufficient funds'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_withdrawal_request_list_success(self):
        """Test successful wallet withdrawal request list retrieval"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_withdrawal_request_list', kwargs={'wallet_id': self.wallet.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_wallet_withdrawal_request_list_with_filters(self):
        """Test wallet withdrawal request list with filters"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_withdrawal_request_list', kwargs={'wallet_id': self.wallet.id})
        params = {
            'status': 'pending',
            'withdrawal_method': 'bank_transfer',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'min_amount': '100.00',
            'max_amount': '500.00'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_wallet_withdrawal_request_list_unauthorized(self):
        """Test wallet withdrawal request list without authentication"""
        url = reverse('wallet_withdrawal_request_list', kwargs={'wallet_id': self.wallet.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_withdrawal_request_detail_success(self):
        """Test successful wallet withdrawal request detail retrieval"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_withdrawal_request_detail', kwargs={'request_id': self.withdrawal_request.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('wallet', response.data)
        self.assertIn('amount', response.data)
        self.assertIn('withdrawal_method', response.data)
        self.assertIn('account_details', response.data)
        self.assertIn('status', response.data)
        self.assertIn('created_at', response.data)
    
    def test_wallet_withdrawal_request_detail_not_found(self):
        """Test wallet withdrawal request detail with non-existent request"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_withdrawal_request_detail', kwargs={'request_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_wallet_withdrawal_request_create_success(self):
        """Test successful wallet withdrawal request creation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_withdrawal_request_create', kwargs={'wallet_id': self.wallet.id})
        data = {
            'amount': '300.00',
            'withdrawal_method': 'bank_transfer',
            'account_details': 'Bank: XYZ Bank, Account: 9876543210',
            'notes': 'Monthly withdrawal request'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('withdrawal_request', response.data)
    
    def test_wallet_withdrawal_request_create_unauthorized(self):
        """Test wallet withdrawal request creation without authentication"""
        url = reverse('wallet_withdrawal_request_create', kwargs={'wallet_id': self.wallet.id})
        data = {
            'amount': '300.00',
            'withdrawal_method': 'bank_transfer',
            'account_details': 'Bank: XYZ Bank, Account: 9876543210',
            'notes': 'Monthly withdrawal request'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_withdrawal_request_update_success(self):
        """Test successful wallet withdrawal request update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_withdrawal_request_update', kwargs={'request_id': self.withdrawal_request.id})
        data = {
            'amount': '250.00',
            'account_details': 'Updated bank details',
            'notes': 'Updated withdrawal request'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('withdrawal_request', response.data)
    
    def test_wallet_withdrawal_request_update_unauthorized(self):
        """Test wallet withdrawal request update without authentication"""
        url = reverse('wallet_withdrawal_request_update', kwargs={'request_id': self.withdrawal_request.id})
        data = {
            'amount': '250.00',
            'account_details': 'Updated bank details',
            'notes': 'Updated withdrawal request'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_withdrawal_request_cancel_success(self):
        """Test successful wallet withdrawal request cancellation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_withdrawal_request_cancel', kwargs={'request_id': self.withdrawal_request.id})
        data = {
            'cancellation_reason': 'Changed my mind',
            'notes': 'Customer requested cancellation'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify withdrawal request was cancelled
        self.withdrawal_request.refresh_from_db()
        self.assertEqual(self.withdrawal_request.status, 'cancelled')
    
    def test_wallet_withdrawal_request_cancel_unauthorized(self):
        """Test wallet withdrawal request cancellation without authentication"""
        url = reverse('wallet_withdrawal_request_cancel', kwargs={'request_id': self.withdrawal_request.id})
        data = {
            'cancellation_reason': 'Changed my mind',
            'notes': 'Customer requested cancellation'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_wallet_withdrawal_request_approve_success(self):
        """Test successful wallet withdrawal request approval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('wallet_withdrawal_request_approve', kwargs={'request_id': self.withdrawal_request.id})
        data = {
            'admin_notes': 'Approved for processing',
            'processing_fee': '5.00'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify withdrawal request was approved
        self.withdrawal_request.refresh_from_db()
        self.assertEqual(self.withdrawal_request.status, 'approved')
    
    def test_wallet_withdrawal_request_approve_unauthorized(self):
        """Test wallet withdrawal request approval without admin authentication"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_withdrawal_request_approve', kwargs={'request_id': self.withdrawal_request.id})
        data = {
            'admin_notes': 'Approved for processing',
            'processing_fee': '5.00'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_wallet_withdrawal_request_reject_success(self):
        """Test successful wallet withdrawal request rejection"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('wallet_withdrawal_request_reject', kwargs={'request_id': self.withdrawal_request.id})
        data = {
            'rejection_reason': 'Insufficient documentation',
            'admin_notes': 'Please provide additional bank statements'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify withdrawal request was rejected
        self.withdrawal_request.refresh_from_db()
        self.assertEqual(self.withdrawal_request.status, 'rejected')
    
    def test_wallet_withdrawal_request_reject_unauthorized(self):
        """Test wallet withdrawal request rejection without admin authentication"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_withdrawal_request_reject', kwargs={'request_id': self.withdrawal_request.id})
        data = {
            'rejection_reason': 'Insufficient documentation',
            'admin_notes': 'Please provide additional bank statements'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_wallet_withdrawal_request_process_success(self):
        """Test successful wallet withdrawal request processing"""
        self.client.force_authenticate(user=self.admin_user)
        
        # First approve the request
        self.withdrawal_request.status = 'approved'
        self.withdrawal_request.save()
        
        url = reverse('wallet_withdrawal_request_process', kwargs={'request_id': self.withdrawal_request.id})
        data = {
            'processing_notes': 'Processed via bank transfer',
            'transaction_reference': 'TXN789012'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify withdrawal request was processed
        self.withdrawal_request.refresh_from_db()
        self.assertEqual(self.withdrawal_request.status, 'processed')
    
    def test_wallet_withdrawal_request_process_unauthorized(self):
        """Test wallet withdrawal request processing without admin authentication"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_withdrawal_request_process', kwargs={'request_id': self.withdrawal_request.id})
        data = {
            'processing_notes': 'Processed via bank transfer',
            'transaction_reference': 'TXN789012'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_wallet_analytics_success(self):
        """Test successful wallet analytics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('wallet_analytics')
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'group_by': 'day'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_wallets', response.data)
        self.assertIn('active_wallets', response.data)
        self.assertIn('total_balance', response.data)
        self.assertIn('average_balance', response.data)
        self.assertIn('total_transactions', response.data)
        self.assertIn('total_withdrawals', response.data)
        self.assertIn('daily_breakdown', response.data)
    
    def test_wallet_analytics_unauthorized(self):
        """Test wallet analytics without admin authentication"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_create')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_create')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_large_amount(self):
        """Test edge case with very large amount"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_balance_update', kwargs={'wallet_id': self.wallet.id})
        data = {
            'amount': '999999.99',  # Very large amount
            'transaction_type': 'credit',
            'description': 'Large balance adjustment',
            'reference_id': 'ADJ999999'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_edge_case_special_characters_in_description(self):
        """Test edge case with special characters in description"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_balance_update', kwargs={'wallet_id': self.wallet.id})
        data = {
            'amount': '100.00',
            'transaction_type': 'credit',
            'description': 'Balance adjustment! 💰 #money',
            'reference_id': 'ADJ123456'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_edge_case_unicode_in_description(self):
        """Test edge case with unicode characters in description"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('wallet_balance_update', kwargs={'wallet_id': self.wallet.id})
        data = {
            'amount': '100.00',
            'transaction_type': 'credit',
            'description': 'Ajuste de saldo con caracteres unicode ✅',
            'reference_id': 'ADJ123456'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class WalletModelTestCase(TestCase):
    """Test cases for Wallet models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
    
    def test_wallet_creation(self):
        """Test Wallet creation"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        self.assertEqual(wallet.user, self.user)
        self.assertEqual(wallet.balance, Decimal('1000.00'))
        self.assertTrue(wallet.is_active)
        self.assertIsNotNone(wallet.created_at)
        self.assertIsNotNone(wallet.updated_at)
    
    def test_wallet_str(self):
        """Test Wallet string representation"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        expected_str = f"Wallet {wallet.id} - {self.user.username} (₹{wallet.balance})"
        self.assertEqual(str(wallet), expected_str)
    
    def test_wallet_get_balance_display(self):
        """Test Wallet get_balance_display method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        balance_display = wallet.get_balance_display()
        self.assertEqual(balance_display, '₹1,000.00')
    
    def test_wallet_get_wallet_summary(self):
        """Test Wallet get_wallet_summary method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        summary = wallet.get_wallet_summary()
        
        self.assertEqual(summary['user'], self.user.id)
        self.assertEqual(summary['balance'], Decimal('1000.00'))
        self.assertTrue(summary['is_active'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_wallet_transaction_creation(self):
        """Test WalletTransaction creation"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='credit',
            amount=Decimal('500.00'),
            description='Design sale payment',
            reference_id='TXN123456',
            status='completed'
        )
        
        self.assertEqual(transaction.wallet, wallet)
        self.assertEqual(transaction.transaction_type, 'credit')
        self.assertEqual(transaction.amount, Decimal('500.00'))
        self.assertEqual(transaction.description, 'Design sale payment')
        self.assertEqual(transaction.reference_id, 'TXN123456')
        self.assertEqual(transaction.status, 'completed')
        self.assertIsNotNone(transaction.created_at)
        self.assertIsNotNone(transaction.updated_at)
    
    def test_wallet_transaction_str(self):
        """Test WalletTransaction string representation"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='credit',
            amount=Decimal('500.00'),
            description='Design sale payment',
            reference_id='TXN123456',
            status='completed'
        )
        
        expected_str = f"Wallet Transaction {transaction.id} - {transaction.transaction_type} ₹{transaction.amount} ({transaction.status})"
        self.assertEqual(str(transaction), expected_str)
    
    def test_wallet_transaction_transaction_type_choices(self):
        """Test WalletTransaction transaction type choices"""
        choices = WalletTransaction.TRANSACTION_TYPE_CHOICES
        
        self.assertIn(('credit', 'Credit'), choices)
        self.assertIn(('debit', 'Debit'), choices)
        self.assertIn(('transfer', 'Transfer'), choices)
        self.assertIn(('refund', 'Refund'), choices)
        self.assertIn(('adjustment', 'Adjustment'), choices)
    
    def test_wallet_transaction_status_choices(self):
        """Test WalletTransaction status choices"""
        choices = WalletTransaction.STATUS_CHOICES
        
        self.assertIn(('pending', 'Pending'), choices)
        self.assertIn(('completed', 'Completed'), choices)
        self.assertIn(('failed', 'Failed'), choices)
        self.assertIn(('cancelled', 'Cancelled'), choices)
        self.assertIn(('reversed', 'Reversed'), choices)
    
    def test_wallet_transaction_get_transaction_summary(self):
        """Test WalletTransaction get_transaction_summary method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        transaction = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='credit',
            amount=Decimal('500.00'),
            description='Design sale payment',
            reference_id='TXN123456',
            status='completed'
        )
        
        summary = transaction.get_transaction_summary()
        
        self.assertEqual(summary['wallet'], wallet.id)
        self.assertEqual(summary['transaction_type'], 'credit')
        self.assertEqual(summary['amount'], Decimal('500.00'))
        self.assertEqual(summary['description'], 'Design sale payment')
        self.assertEqual(summary['reference_id'], 'TXN123456')
        self.assertEqual(summary['status'], 'completed')
        self.assertIsNotNone(summary['created_at'])
    
    def test_wallet_withdrawal_request_creation(self):
        """Test WalletWithdrawalRequest creation"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='pending'
        )
        
        self.assertEqual(withdrawal_request.wallet, wallet)
        self.assertEqual(withdrawal_request.amount, Decimal('200.00'))
        self.assertEqual(withdrawal_request.withdrawal_method, 'bank_transfer')
        self.assertEqual(withdrawal_request.account_details, 'Bank: ABC Bank, Account: 1234567890')
        self.assertEqual(withdrawal_request.status, 'pending')
        self.assertIsNotNone(withdrawal_request.created_at)
        self.assertIsNotNone(withdrawal_request.updated_at)
    
    def test_wallet_withdrawal_request_str(self):
        """Test WalletWithdrawalRequest string representation"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='pending'
        )
        
        expected_str = f"Wallet Withdrawal Request {withdrawal_request.id} - ₹{withdrawal_request.amount} ({withdrawal_request.status})"
        self.assertEqual(str(withdrawal_request), expected_str)
    
    def test_wallet_withdrawal_request_withdrawal_method_choices(self):
        """Test WalletWithdrawalRequest withdrawal method choices"""
        choices = WalletWithdrawalRequest.WITHDRAWAL_METHOD_CHOICES
        
        self.assertIn(('bank_transfer', 'Bank Transfer'), choices)
        self.assertIn(('paypal', 'PayPal'), choices)
        self.assertIn(('stripe', 'Stripe'), choices)
        self.assertIn(('razorpay', 'Razorpay'), choices)
        self.assertIn(('other', 'Other'), choices)
    
    def test_wallet_withdrawal_request_status_choices(self):
        """Test WalletWithdrawalRequest status choices"""
        choices = WalletWithdrawalRequest.STATUS_CHOICES
        
        self.assertIn(('pending', 'Pending'), choices)
        self.assertIn(('approved', 'Approved'), choices)
        self.assertIn(('rejected', 'Rejected'), choices)
        self.assertIn(('processed', 'Processed'), choices)
        self.assertIn(('cancelled', 'Cancelled'), choices)
    
    def test_wallet_withdrawal_request_get_withdrawal_summary(self):
        """Test WalletWithdrawalRequest get_withdrawal_summary method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='pending'
        )
        
        summary = withdrawal_request.get_withdrawal_summary()
        
        self.assertEqual(summary['wallet'], wallet.id)
        self.assertEqual(summary['amount'], Decimal('200.00'))
        self.assertEqual(summary['withdrawal_method'], 'bank_transfer')
        self.assertEqual(summary['account_details'], 'Bank: ABC Bank, Account: 1234567890')
        self.assertEqual(summary['status'], 'pending')
        self.assertIsNotNone(summary['created_at'])
    
    def test_wallet_withdrawal_request_can_be_cancelled(self):
        """Test WalletWithdrawalRequest can_be_cancelled method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        # Test pending withdrawal request
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='pending'
        )
        
        self.assertTrue(withdrawal_request.can_be_cancelled())
        
        # Test processed withdrawal request
        processed_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='processed'
        )
        
        self.assertFalse(processed_request.can_be_cancelled())
    
    def test_wallet_withdrawal_request_can_be_approved(self):
        """Test WalletWithdrawalRequest can_be_approved method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        # Test pending withdrawal request
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='pending'
        )
        
        self.assertTrue(withdrawal_request.can_be_approved())
        
        # Test approved withdrawal request
        approved_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='approved'
        )
        
        self.assertFalse(approved_request.can_be_approved())
    
    def test_wallet_withdrawal_request_can_be_rejected(self):
        """Test WalletWithdrawalRequest can_be_rejected method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        # Test pending withdrawal request
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='pending'
        )
        
        self.assertTrue(withdrawal_request.can_be_rejected())
        
        # Test rejected withdrawal request
        rejected_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='rejected'
        )
        
        self.assertFalse(rejected_request.can_be_rejected())
    
    def test_wallet_withdrawal_request_can_be_processed(self):
        """Test WalletWithdrawalRequest can_be_processed method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        # Test approved withdrawal request
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='approved'
        )
        
        self.assertTrue(withdrawal_request.can_be_processed())
        
        # Test processed withdrawal request
        processed_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='processed'
        )
        
        self.assertFalse(processed_request.can_be_processed())
    
    def test_wallet_withdrawal_request_approve(self):
        """Test WalletWithdrawalRequest approve method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='pending'
        )
        
        withdrawal_request.approve('Approved for processing', '5.00')
        
        self.assertEqual(withdrawal_request.status, 'approved')
        self.assertEqual(withdrawal_request.admin_notes, 'Approved for processing')
        self.assertEqual(withdrawal_request.processing_fee, Decimal('5.00'))
    
    def test_wallet_withdrawal_request_reject(self):
        """Test WalletWithdrawalRequest reject method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='pending'
        )
        
        withdrawal_request.reject('Insufficient documentation', 'Please provide additional bank statements')
        
        self.assertEqual(withdrawal_request.status, 'rejected')
        self.assertEqual(withdrawal_request.rejection_reason, 'Insufficient documentation')
        self.assertEqual(withdrawal_request.admin_notes, 'Please provide additional bank statements')
    
    def test_wallet_withdrawal_request_process(self):
        """Test WalletWithdrawalRequest process method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='approved'
        )
        
        withdrawal_request.process('Processed via bank transfer', 'TXN789012')
        
        self.assertEqual(withdrawal_request.status, 'processed')
        self.assertEqual(withdrawal_request.processing_notes, 'Processed via bank transfer')
        self.assertEqual(withdrawal_request.transaction_reference, 'TXN789012')
    
    def test_wallet_withdrawal_request_cancel(self):
        """Test WalletWithdrawalRequest cancel method"""
        wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal('1000.00'),
            is_active=True
        )
        
        withdrawal_request = WalletWithdrawalRequest.objects.create(
            wallet=wallet,
            amount=Decimal('200.00'),
            withdrawal_method='bank_transfer',
            account_details='Bank: ABC Bank, Account: 1234567890',
            status='pending'
        )
        
        withdrawal_request.cancel('Customer requested cancellation')
        
        self.assertEqual(withdrawal_request.status, 'cancelled')
        self.assertEqual(withdrawal_request.cancellation_reason, 'Customer requested cancellation')