"""
Comprehensive tests for Razorpay app
Tests Razorpay integration, payments, and webhooks
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

from .models import RazorpayPayment, RazorpayWebhookEvent, RazorpayRefund, RazorpayPayout


class RazorpayAPITestCase(APITestCase):
    """Test cases for Razorpay API endpoints"""
    
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
        
        # Create Razorpay payment
        self.razorpay_payment = RazorpayPayment.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            razorpay_payment_id='pay_1234567890',
            razorpay_order_id='order_1234567890',
            status='captured',
            payment_method='card',
            description='Test payment'
        )
        
        # Create Razorpay webhook event
        self.webhook_event = RazorpayWebhookEvent.objects.create(
            event_id='evt_1234567890',
            event_type='payment.captured',
            event_data={'payment_id': 'pay_1234567890'},
            processed=False
        )
        
        # Create Razorpay refund
        self.razorpay_refund = RazorpayRefund.objects.create(
            payment=self.razorpay_payment,
            amount=Decimal('50.00'),
            razorpay_refund_id='rfnd_1234567890',
            status='processed',
            reason='Customer requested refund'
        )
        
        # Create Razorpay payout
        self.razorpay_payout = RazorpayPayout.objects.create(
            user=self.designer,
            amount=Decimal('200.00'),
            razorpay_payout_id='pout_1234567890',
            status='processed',
            payout_method='bank_transfer'
        )
    
    def test_razorpay_payment_list_success(self):
        """Test successful Razorpay payment list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_razorpay_payment_list_with_filters(self):
        """Test Razorpay payment list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_list')
        params = {
            'status': 'captured',
            'payment_method': 'card',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'min_amount': '50.00',
            'max_amount': '500.00'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_razorpay_payment_list_unauthorized(self):
        """Test Razorpay payment list without authentication"""
        url = reverse('razorpay_payment_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_payment_detail_success(self):
        """Test successful Razorpay payment detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_detail', kwargs={'payment_id': self.razorpay_payment.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('user', response.data)
        self.assertIn('amount', response.data)
        self.assertIn('currency', response.data)
        self.assertIn('razorpay_payment_id', response.data)
        self.assertIn('razorpay_order_id', response.data)
        self.assertIn('status', response.data)
        self.assertIn('payment_method', response.data)
        self.assertIn('description', response.data)
        self.assertIn('created_at', response.data)
    
    def test_razorpay_payment_detail_not_found(self):
        """Test Razorpay payment detail with non-existent payment"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_detail', kwargs={'payment_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_razorpay_payment_create_success(self):
        """Test successful Razorpay payment creation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_create')
        data = {
            'amount': '150.00',
            'currency': 'INR',
            'description': 'New payment',
            'payment_method': 'card'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('payment', response.data)
    
    def test_razorpay_payment_create_unauthorized(self):
        """Test Razorpay payment creation without authentication"""
        url = reverse('razorpay_payment_create')
        data = {
            'amount': '150.00',
            'currency': 'INR',
            'description': 'New payment',
            'payment_method': 'card'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_payment_update_success(self):
        """Test successful Razorpay payment update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_update', kwargs={'payment_id': self.razorpay_payment.id})
        data = {
            'status': 'failed',
            'failure_reason': 'Payment declined by bank'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('payment', response.data)
    
    def test_razorpay_payment_update_unauthorized(self):
        """Test Razorpay payment update without authentication"""
        url = reverse('razorpay_payment_update', kwargs={'payment_id': self.razorpay_payment.id})
        data = {
            'status': 'failed',
            'failure_reason': 'Payment declined by bank'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_payment_capture_success(self):
        """Test successful Razorpay payment capture"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_capture', kwargs={'payment_id': self.razorpay_payment.id})
        data = {
            'amount': '100.00',
            'currency': 'INR'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('payment', response.data)
    
    def test_razorpay_payment_capture_unauthorized(self):
        """Test Razorpay payment capture without authentication"""
        url = reverse('razorpay_payment_capture', kwargs={'payment_id': self.razorpay_payment.id})
        data = {
            'amount': '100.00',
            'currency': 'INR'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_payment_refund_success(self):
        """Test successful Razorpay payment refund"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_refund', kwargs={'payment_id': self.razorpay_payment.id})
        data = {
            'amount': '50.00',
            'reason': 'Customer requested refund',
            'notes': 'Partial refund for design purchase'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('refund', response.data)
    
    def test_razorpay_payment_refund_unauthorized(self):
        """Test Razorpay payment refund without authentication"""
        url = reverse('razorpay_payment_refund', kwargs={'payment_id': self.razorpay_payment.id})
        data = {
            'amount': '50.00',
            'reason': 'Customer requested refund',
            'notes': 'Partial refund for design purchase'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_webhook_event_list_success(self):
        """Test successful Razorpay webhook event list retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('razorpay_webhook_event_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_razorpay_webhook_event_list_with_filters(self):
        """Test Razorpay webhook event list with filters"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('razorpay_webhook_event_list')
        params = {
            'event_type': 'payment.captured',
            'processed': 'false',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_razorpay_webhook_event_list_unauthorized(self):
        """Test Razorpay webhook event list without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_webhook_event_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_razorpay_webhook_event_detail_success(self):
        """Test successful Razorpay webhook event detail retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('razorpay_webhook_event_detail', kwargs={'event_id': self.webhook_event.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('event_id', response.data)
        self.assertIn('event_type', response.data)
        self.assertIn('event_data', response.data)
        self.assertIn('processed', response.data)
        self.assertIn('created_at', response.data)
    
    def test_razorpay_webhook_event_detail_not_found(self):
        """Test Razorpay webhook event detail with non-existent event"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('razorpay_webhook_event_detail', kwargs={'event_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_razorpay_webhook_event_process_success(self):
        """Test successful Razorpay webhook event processing"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('razorpay_webhook_event_process', kwargs={'event_id': self.webhook_event.id})
        data = {
            'admin_notes': 'Event processed successfully'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('event', response.data)
    
    def test_razorpay_webhook_event_process_unauthorized(self):
        """Test Razorpay webhook event processing without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_webhook_event_process', kwargs={'event_id': self.webhook_event.id})
        data = {
            'admin_notes': 'Event processed successfully'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_razorpay_refund_list_success(self):
        """Test successful Razorpay refund list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_refund_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_razorpay_refund_list_with_filters(self):
        """Test Razorpay refund list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_refund_list')
        params = {
            'status': 'processed',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'min_amount': '10.00',
            'max_amount': '100.00'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_razorpay_refund_list_unauthorized(self):
        """Test Razorpay refund list without authentication"""
        url = reverse('razorpay_refund_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_refund_detail_success(self):
        """Test successful Razorpay refund detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_refund_detail', kwargs={'refund_id': self.razorpay_refund.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('payment', response.data)
        self.assertIn('amount', response.data)
        self.assertIn('razorpay_refund_id', response.data)
        self.assertIn('status', response.data)
        self.assertIn('reason', response.data)
        self.assertIn('created_at', response.data)
    
    def test_razorpay_refund_detail_not_found(self):
        """Test Razorpay refund detail with non-existent refund"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_refund_detail', kwargs={'refund_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_razorpay_refund_create_success(self):
        """Test successful Razorpay refund creation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_refund_create')
        data = {
            'payment': self.razorpay_payment.id,
            'amount': '75.00',
            'reason': 'Customer requested refund',
            'notes': 'Partial refund for design purchase'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('refund', response.data)
    
    def test_razorpay_refund_create_unauthorized(self):
        """Test Razorpay refund creation without authentication"""
        url = reverse('razorpay_refund_create')
        data = {
            'payment': self.razorpay_payment.id,
            'amount': '75.00',
            'reason': 'Customer requested refund',
            'notes': 'Partial refund for design purchase'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_refund_update_success(self):
        """Test successful Razorpay refund update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_refund_update', kwargs={'refund_id': self.razorpay_refund.id})
        data = {
            'status': 'failed',
            'failure_reason': 'Refund failed due to insufficient funds'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('refund', response.data)
    
    def test_razorpay_refund_update_unauthorized(self):
        """Test Razorpay refund update without authentication"""
        url = reverse('razorpay_refund_update', kwargs={'refund_id': self.razorpay_refund.id})
        data = {
            'status': 'failed',
            'failure_reason': 'Refund failed due to insufficient funds'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_payout_list_success(self):
        """Test successful Razorpay payout list retrieval"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('razorpay_payout_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_razorpay_payout_list_with_filters(self):
        """Test Razorpay payout list with filters"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('razorpay_payout_list')
        params = {
            'status': 'processed',
            'payout_method': 'bank_transfer',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'min_amount': '100.00',
            'max_amount': '500.00'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_razorpay_payout_list_unauthorized(self):
        """Test Razorpay payout list without authentication"""
        url = reverse('razorpay_payout_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_payout_detail_success(self):
        """Test successful Razorpay payout detail retrieval"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('razorpay_payout_detail', kwargs={'payout_id': self.razorpay_payout.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('user', response.data)
        self.assertIn('amount', response.data)
        self.assertIn('razorpay_payout_id', response.data)
        self.assertIn('status', response.data)
        self.assertIn('payout_method', response.data)
        self.assertIn('created_at', response.data)
    
    def test_razorpay_payout_detail_not_found(self):
        """Test Razorpay payout detail with non-existent payout"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('razorpay_payout_detail', kwargs={'payout_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_razorpay_payout_create_success(self):
        """Test successful Razorpay payout creation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('razorpay_payout_create')
        data = {
            'amount': '300.00',
            'payout_method': 'bank_transfer',
            'account_details': 'Bank: ABC Bank, Account: 1234567890',
            'notes': 'Monthly payout request'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('payout', response.data)
    
    def test_razorpay_payout_create_unauthorized(self):
        """Test Razorpay payout creation without authentication"""
        url = reverse('razorpay_payout_create')
        data = {
            'amount': '300.00',
            'payout_method': 'bank_transfer',
            'account_details': 'Bank: ABC Bank, Account: 1234567890',
            'notes': 'Monthly payout request'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_payout_update_success(self):
        """Test successful Razorpay payout update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('razorpay_payout_update', kwargs={'payout_id': self.razorpay_payout.id})
        data = {
            'status': 'failed',
            'failure_reason': 'Payout failed due to invalid account details'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('payout', response.data)
    
    def test_razorpay_payout_update_unauthorized(self):
        """Test Razorpay payout update without authentication"""
        url = reverse('razorpay_payout_update', kwargs={'payout_id': self.razorpay_payout.id})
        data = {
            'status': 'failed',
            'failure_reason': 'Payout failed due to invalid account details'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_razorpay_analytics_success(self):
        """Test successful Razorpay analytics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('razorpay_analytics')
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'group_by': 'day'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_payments', response.data)
        self.assertIn('successful_payments', response.data)
        self.assertIn('failed_payments', response.data)
        self.assertIn('total_amount', response.data)
        self.assertIn('total_refunds', response.data)
        self.assertIn('total_payouts', response.data)
        self.assertIn('daily_breakdown', response.data)
    
    def test_razorpay_analytics_unauthorized(self):
        """Test Razorpay analytics without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_create')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_create')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_large_amount(self):
        """Test edge case with very large amount"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_create')
        data = {
            'amount': '999999.99',  # Very large amount
            'currency': 'INR',
            'description': 'Large payment',
            'payment_method': 'card'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_special_characters_in_description(self):
        """Test edge case with special characters in description"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_create')
        data = {
            'amount': '100.00',
            'currency': 'INR',
            'description': 'Payment for design! 🎨 #creative',
            'payment_method': 'card'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_unicode_in_description(self):
        """Test edge case with unicode characters in description"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('razorpay_payment_create')
        data = {
            'amount': '100.00',
            'currency': 'INR',
            'description': 'Pago por diseño con caracteres unicode ✅',
            'payment_method': 'card'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class RazorpayModelTestCase(TestCase):
    """Test cases for Razorpay models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
    
    def test_razorpay_payment_creation(self):
        """Test RazorpayPayment creation"""
        payment = RazorpayPayment.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            razorpay_payment_id='pay_1234567890',
            razorpay_order_id='order_1234567890',
            status='captured',
            payment_method='card',
            description='Test payment'
        )
        
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.amount, Decimal('100.00'))
        self.assertEqual(payment.currency, 'INR')
        self.assertEqual(payment.razorpay_payment_id, 'pay_1234567890')
        self.assertEqual(payment.razorpay_order_id, 'order_1234567890')
        self.assertEqual(payment.status, 'captured')
        self.assertEqual(payment.payment_method, 'card')
        self.assertEqual(payment.description, 'Test payment')
        self.assertIsNotNone(payment.created_at)
        self.assertIsNotNone(payment.updated_at)
    
    def test_razorpay_payment_str(self):
        """Test RazorpayPayment string representation"""
        payment = RazorpayPayment.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            razorpay_payment_id='pay_1234567890',
            razorpay_order_id='order_1234567890',
            status='captured',
            payment_method='card',
            description='Test payment'
        )
        
        expected_str = f"Razorpay Payment {payment.id} - {payment.razorpay_payment_id} ({payment.status})"
        self.assertEqual(str(payment), expected_str)
    
    def test_razorpay_payment_status_choices(self):
        """Test RazorpayPayment status choices"""
        choices = RazorpayPayment.STATUS_CHOICES
        
        self.assertIn(('authorized', 'Authorized'), choices)
        self.assertIn(('captured', 'Captured'), choices)
        self.assertIn(('refunded', 'Refunded'), choices)
        self.assertIn(('failed', 'Failed'), choices)
        self.assertIn(('cancelled', 'Cancelled'), choices)
    
    def test_razorpay_payment_payment_method_choices(self):
        """Test RazorpayPayment payment method choices"""
        choices = RazorpayPayment.PAYMENT_METHOD_CHOICES
        
        self.assertIn(('card', 'Card'), choices)
        self.assertIn(('netbanking', 'Net Banking'), choices)
        self.assertIn(('wallet', 'Wallet'), choices)
        self.assertIn(('upi', 'UPI'), choices)
        self.assertIn(('emi', 'EMI'), choices)
    
    def test_razorpay_payment_get_payment_summary(self):
        """Test RazorpayPayment get_payment_summary method"""
        payment = RazorpayPayment.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            razorpay_payment_id='pay_1234567890',
            razorpay_order_id='order_1234567890',
            status='captured',
            payment_method='card',
            description='Test payment'
        )
        
        summary = payment.get_payment_summary()
        
        self.assertEqual(summary['user'], self.user.id)
        self.assertEqual(summary['amount'], Decimal('100.00'))
        self.assertEqual(summary['currency'], 'INR')
        self.assertEqual(summary['razorpay_payment_id'], 'pay_1234567890')
        self.assertEqual(summary['razorpay_order_id'], 'order_1234567890')
        self.assertEqual(summary['status'], 'captured')
        self.assertEqual(summary['payment_method'], 'card')
        self.assertEqual(summary['description'], 'Test payment')
        self.assertIsNotNone(summary['created_at'])
    
    def test_razorpay_webhook_event_creation(self):
        """Test RazorpayWebhookEvent creation"""
        event = RazorpayWebhookEvent.objects.create(
            event_id='evt_1234567890',
            event_type='payment.captured',
            event_data={'payment_id': 'pay_1234567890'},
            processed=False
        )
        
        self.assertEqual(event.event_id, 'evt_1234567890')
        self.assertEqual(event.event_type, 'payment.captured')
        self.assertEqual(event.event_data, {'payment_id': 'pay_1234567890'})
        self.assertFalse(event.processed)
        self.assertIsNotNone(event.created_at)
        self.assertIsNotNone(event.updated_at)
    
    def test_razorpay_webhook_event_str(self):
        """Test RazorpayWebhookEvent string representation"""
        event = RazorpayWebhookEvent.objects.create(
            event_id='evt_1234567890',
            event_type='payment.captured',
            event_data={'payment_id': 'pay_1234567890'},
            processed=False
        )
        
        expected_str = f"Razorpay Webhook Event {event.id} - {event.event_type} ({event.event_id})"
        self.assertEqual(str(event), expected_str)
    
    def test_razorpay_webhook_event_get_event_summary(self):
        """Test RazorpayWebhookEvent get_event_summary method"""
        event = RazorpayWebhookEvent.objects.create(
            event_id='evt_1234567890',
            event_type='payment.captured',
            event_data={'payment_id': 'pay_1234567890'},
            processed=False
        )
        
        summary = event.get_event_summary()
        
        self.assertEqual(summary['event_id'], 'evt_1234567890')
        self.assertEqual(summary['event_type'], 'payment.captured')
        self.assertEqual(summary['event_data'], {'payment_id': 'pay_1234567890'})
        self.assertFalse(summary['processed'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_razorpay_refund_creation(self):
        """Test RazorpayRefund creation"""
        payment = RazorpayPayment.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            razorpay_payment_id='pay_1234567890',
            razorpay_order_id='order_1234567890',
            status='captured',
            payment_method='card',
            description='Test payment'
        )
        
        refund = RazorpayRefund.objects.create(
            payment=payment,
            amount=Decimal('50.00'),
            razorpay_refund_id='rfnd_1234567890',
            status='processed',
            reason='Customer requested refund'
        )
        
        self.assertEqual(refund.payment, payment)
        self.assertEqual(refund.amount, Decimal('50.00'))
        self.assertEqual(refund.razorpay_refund_id, 'rfnd_1234567890')
        self.assertEqual(refund.status, 'processed')
        self.assertEqual(refund.reason, 'Customer requested refund')
        self.assertIsNotNone(refund.created_at)
        self.assertIsNotNone(refund.updated_at)
    
    def test_razorpay_refund_str(self):
        """Test RazorpayRefund string representation"""
        payment = RazorpayPayment.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            razorpay_payment_id='pay_1234567890',
            razorpay_order_id='order_1234567890',
            status='captured',
            payment_method='card',
            description='Test payment'
        )
        
        refund = RazorpayRefund.objects.create(
            payment=payment,
            amount=Decimal('50.00'),
            razorpay_refund_id='rfnd_1234567890',
            status='processed',
            reason='Customer requested refund'
        )
        
        expected_str = f"Razorpay Refund {refund.id} - {refund.razorpay_refund_id} ({refund.status})"
        self.assertEqual(str(refund), expected_str)
    
    def test_razorpay_refund_status_choices(self):
        """Test RazorpayRefund status choices"""
        choices = RazorpayRefund.STATUS_CHOICES
        
        self.assertIn(('pending', 'Pending'), choices)
        self.assertIn(('processed', 'Processed'), choices)
        self.assertIn(('failed', 'Failed'), choices)
        self.assertIn(('cancelled', 'Cancelled'), choices)
    
    def test_razorpay_refund_get_refund_summary(self):
        """Test RazorpayRefund get_refund_summary method"""
        payment = RazorpayPayment.objects.create(
            user=self.user,
            amount=Decimal('100.00'),
            currency='INR',
            razorpay_payment_id='pay_1234567890',
            razorpay_order_id='order_1234567890',
            status='captured',
            payment_method='card',
            description='Test payment'
        )
        
        refund = RazorpayRefund.objects.create(
            payment=payment,
            amount=Decimal('50.00'),
            razorpay_refund_id='rfnd_1234567890',
            status='processed',
            reason='Customer requested refund'
        )
        
        summary = refund.get_refund_summary()
        
        self.assertEqual(summary['payment'], payment.id)
        self.assertEqual(summary['amount'], Decimal('50.00'))
        self.assertEqual(summary['razorpay_refund_id'], 'rfnd_1234567890')
        self.assertEqual(summary['status'], 'processed')
        self.assertEqual(summary['reason'], 'Customer requested refund')
        self.assertIsNotNone(summary['created_at'])
    
    def test_razorpay_payout_creation(self):
        """Test RazorpayPayout creation"""
        payout = RazorpayPayout.objects.create(
            user=self.user,
            amount=Decimal('200.00'),
            razorpay_payout_id='pout_1234567890',
            status='processed',
            payout_method='bank_transfer'
        )
        
        self.assertEqual(payout.user, self.user)
        self.assertEqual(payout.amount, Decimal('200.00'))
        self.assertEqual(payout.razorpay_payout_id, 'pout_1234567890')
        self.assertEqual(payout.status, 'processed')
        self.assertEqual(payout.payout_method, 'bank_transfer')
        self.assertIsNotNone(payout.created_at)
        self.assertIsNotNone(payout.updated_at)
    
    def test_razorpay_payout_str(self):
        """Test RazorpayPayout string representation"""
        payout = RazorpayPayout.objects.create(
            user=self.user,
            amount=Decimal('200.00'),
            razorpay_payout_id='pout_1234567890',
            status='processed',
            payout_method='bank_transfer'
        )
        
        expected_str = f"Razorpay Payout {payout.id} - {payout.razorpay_payout_id} ({payout.status})"
        self.assertEqual(str(payout), expected_str)
    
    def test_razorpay_payout_status_choices(self):
        """Test RazorpayPayout status choices"""
        choices = RazorpayPayout.STATUS_CHOICES
        
        self.assertIn(('pending', 'Pending'), choices)
        self.assertIn(('processed', 'Processed'), choices)
        self.assertIn(('failed', 'Failed'), choices)
        self.assertIn(('cancelled', 'Cancelled'), choices)
    
    def test_razorpay_payout_payout_method_choices(self):
        """Test RazorpayPayout payout method choices"""
        choices = RazorpayPayout.PAYOUT_METHOD_CHOICES
        
        self.assertIn(('bank_transfer', 'Bank Transfer'), choices)
        self.assertIn(('upi', 'UPI'), choices)
        self.assertIn(('wallet', 'Wallet'), choices)
        self.assertIn(('other', 'Other'), choices)
    
    def test_razorpay_payout_get_payout_summary(self):
        """Test RazorpayPayout get_payout_summary method"""
        payout = RazorpayPayout.objects.create(
            user=self.user,
            amount=Decimal('200.00'),
            razorpay_payout_id='pout_1234567890',
            status='processed',
            payout_method='bank_transfer'
        )
        
        summary = payout.get_payout_summary()
        
        self.assertEqual(summary['user'], self.user.id)
        self.assertEqual(summary['amount'], Decimal('200.00'))
        self.assertEqual(summary['razorpay_payout_id'], 'pout_1234567890')
        self.assertEqual(summary['status'], 'processed')
        self.assertEqual(summary['payout_method'], 'bank_transfer')
        self.assertIsNotNone(summary['created_at'])