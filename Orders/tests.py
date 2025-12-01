"""
Comprehensive tests for Orders app
Tests order management, transactions, and order processing
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

from .models import Order, OrderTransaction, OrderItem, OrderStatus
from common.relations import attach_relation


class OrdersAPITestCase(APITestCase):
    """Test cases for Orders API endpoints"""
    
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
        
        # Create order
        self.order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        # Create order transaction
        self.order_transaction = OrderTransaction.objects.create(
            order=self.order,
            transaction_type='payment',
            amount=Decimal('99.99'),
            status='pending',
            payment_method='card',
            transaction_id='txn_123456789',
            gateway_response={
                'status': 'pending',
                'gateway_id': 'pay_123456789'
            }
        )
        
        # Create order item
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product_type='design',
            product_id=1,
            product_name='Modern Logo Template',
            quantity=1,
            unit_price=Decimal('99.99'),
            total_price=Decimal('99.99')
        )
        
        # Create order status
        self.order_status = OrderStatus.objects.create(
            order=self.order,
            status='pending',
            notes='Order created',
            updated_by=self.user
        )
    
    def test_order_list_success(self):
        """Test successful order list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_order_list_with_filters(self):
        """Test order list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_list')
        params = {
            'status': 'pending',
            'payment_status': 'pending',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'min_amount': '50.00',
            'max_amount': '200.00',
            'search': 'ORD-2024'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_order_detail_success(self):
        """Test successful order detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_detail', kwargs={'order_id': self.order.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('order_number', response.data)
        self.assertIn('total_amount', response.data)
        self.assertIn('status', response.data)
        self.assertIn('payment_status', response.data)
        self.assertIn('shipping_address', response.data)
        self.assertIn('billing_address', response.data)
        self.assertIn('notes', response.data)
        self.assertIn('created_at', response.data)
    
    def test_order_detail_not_found(self):
        """Test order detail with non-existent order"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_detail', kwargs={'order_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_order_create_success(self):
        """Test successful order creation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_create')
        data = {
            'total_amount': '149.99',
            'shipping_address': '456 New Street, New City',
            'billing_address': '456 New Street, New City',
            'notes': 'New order notes',
            'items': [
                {
                    'product_type': 'design',
                    'product_id': 2,
                    'product_name': 'Creative Logo Template',
                    'quantity': 1,
                    'unit_price': '149.99',
                    'total_price': '149.99'
                }
            ]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('order', response.data)
    
    def test_order_create_unauthorized(self):
        """Test order creation without authentication"""
        url = reverse('order_create')
        data = {
            'total_amount': '149.99',
            'shipping_address': '456 New Street, New City',
            'billing_address': '456 New Street, New City',
            'notes': 'New order notes'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_update_success(self):
        """Test successful order update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_update', kwargs={'order_id': self.order.id})
        data = {
            'status': 'processing',
            'shipping_address': 'Updated Shipping Address',
            'billing_address': 'Updated Billing Address',
            'notes': 'Updated order notes'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('order', response.data)
    
    def test_order_update_unauthorized(self):
        """Test order update without authentication"""
        url = reverse('order_update', kwargs={'order_id': self.order.id})
        data = {
            'status': 'processing',
            'notes': 'Updated order notes'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_cancel_success(self):
        """Test successful order cancellation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_cancel', kwargs={'order_id': self.order.id})
        data = {
            'cancellation_reason': 'Customer requested cancellation',
            'notes': 'Order cancelled by customer'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify order was cancelled
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'cancelled')
    
    def test_order_cancel_unauthorized(self):
        """Test order cancellation without authentication"""
        url = reverse('order_cancel', kwargs={'order_id': self.order.id})
        data = {
            'cancellation_reason': 'Customer requested cancellation',
            'notes': 'Order cancelled by customer'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_status_update_success(self):
        """Test successful order status update"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('order_status_update', kwargs={'order_id': self.order.id})
        data = {
            'status': 'shipped',
            'notes': 'Order has been shipped',
            'tracking_number': 'TRK123456789'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify order status was updated
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'shipped')
    
    def test_order_status_update_unauthorized(self):
        """Test order status update without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_status_update', kwargs={'order_id': self.order.id})
        data = {
            'status': 'shipped',
            'notes': 'Order has been shipped'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_order_transaction_list_success(self):
        """Test successful order transaction list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_transaction_list', kwargs={'order_id': self.order.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_order_transaction_list_unauthorized(self):
        """Test order transaction list without authentication"""
        url = reverse('order_transaction_list', kwargs={'order_id': self.order.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_transaction_detail_success(self):
        """Test successful order transaction detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_transaction_detail', kwargs={'transaction_id': self.order_transaction.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('transaction_type', response.data)
        self.assertIn('amount', response.data)
        self.assertIn('status', response.data)
        self.assertIn('payment_method', response.data)
        self.assertIn('transaction_id', response.data)
        self.assertIn('gateway_response', response.data)
        self.assertIn('created_at', response.data)
    
    def test_order_transaction_detail_not_found(self):
        """Test order transaction detail with non-existent transaction"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_transaction_detail', kwargs={'transaction_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_order_transaction_create_success(self):
        """Test successful order transaction creation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_transaction_create', kwargs={'order_id': self.order.id})
        data = {
            'transaction_type': 'refund',
            'amount': '50.00',
            'status': 'pending',
            'payment_method': 'card',
            'transaction_id': 'txn_refund_123',
            'gateway_response': {
                'status': 'pending',
                'gateway_id': 'refund_123456789'
            }
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('transaction', response.data)
    
    def test_order_transaction_create_unauthorized(self):
        """Test order transaction creation without authentication"""
        url = reverse('order_transaction_create', kwargs={'order_id': self.order.id})
        data = {
            'transaction_type': 'refund',
            'amount': '50.00',
            'status': 'pending',
            'payment_method': 'card'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_transaction_update_success(self):
        """Test successful order transaction update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_transaction_update', kwargs={'transaction_id': self.order_transaction.id})
        data = {
            'status': 'completed',
            'gateway_response': {
                'status': 'completed',
                'gateway_id': 'pay_123456789',
                'completion_time': '2024-01-01T12:00:00Z'
            }
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('transaction', response.data)
    
    def test_order_transaction_update_unauthorized(self):
        """Test order transaction update without authentication"""
        url = reverse('order_transaction_update', kwargs={'transaction_id': self.order_transaction.id})
        data = {
            'status': 'completed'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_item_list_success(self):
        """Test successful order item list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_item_list', kwargs={'order_id': self.order.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_order_item_list_unauthorized(self):
        """Test order item list without authentication"""
        url = reverse('order_item_list', kwargs={'order_id': self.order.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_item_detail_success(self):
        """Test successful order item detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_item_detail', kwargs={'item_id': self.order_item.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('product_type', response.data)
        self.assertIn('product_id', response.data)
        self.assertIn('product_name', response.data)
        self.assertIn('quantity', response.data)
        self.assertIn('unit_price', response.data)
        self.assertIn('total_price', response.data)
        self.assertIn('created_at', response.data)
    
    def test_order_item_detail_not_found(self):
        """Test order item detail with non-existent item"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_item_detail', kwargs={'item_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_order_item_create_success(self):
        """Test successful order item creation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_item_create', kwargs={'order_id': self.order.id})
        data = {
            'product_type': 'bundle',
            'product_id': 2,
            'product_name': 'Design Bundle',
            'quantity': 1,
            'unit_price': '199.99',
            'total_price': '199.99'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('item', response.data)
    
    def test_order_item_create_unauthorized(self):
        """Test order item creation without authentication"""
        url = reverse('order_item_create', kwargs={'order_id': self.order.id})
        data = {
            'product_type': 'bundle',
            'product_id': 2,
            'product_name': 'Design Bundle',
            'quantity': 1,
            'unit_price': '199.99',
            'total_price': '199.99'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_item_update_success(self):
        """Test successful order item update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_item_update', kwargs={'item_id': self.order_item.id})
        data = {
            'quantity': 2,
            'unit_price': '89.99',
            'total_price': '179.98'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('item', response.data)
    
    def test_order_item_update_unauthorized(self):
        """Test order item update without authentication"""
        url = reverse('order_item_update', kwargs={'item_id': self.order_item.id})
        data = {
            'quantity': 2,
            'unit_price': '89.99',
            'total_price': '179.98'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_item_delete_success(self):
        """Test successful order item deletion"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_item_delete', kwargs={'item_id': self.order_item.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_order_item_delete_unauthorized(self):
        """Test order item deletion without authentication"""
        url = reverse('order_item_delete', kwargs={'item_id': self.order_item.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_status_list_success(self):
        """Test successful order status list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_status_list', kwargs={'order_id': self.order.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_order_status_list_unauthorized(self):
        """Test order status list without authentication"""
        url = reverse('order_status_list', kwargs={'order_id': self.order.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_order_status_detail_success(self):
        """Test successful order status detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_status_detail', kwargs={'status_id': self.order_status.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('status', response.data)
        self.assertIn('notes', response.data)
        self.assertIn('updated_by', response.data)
        self.assertIn('created_at', response.data)
    
    def test_order_status_detail_not_found(self):
        """Test order status detail with non-existent status"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_status_detail', kwargs={'status_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_order_status_create_success(self):
        """Test successful order status creation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('order_status_create', kwargs={'order_id': self.order.id})
        data = {
            'status': 'processing',
            'notes': 'Order is being processed',
            'tracking_number': 'TRK123456789'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('status', response.data)
    
    def test_order_status_create_unauthorized(self):
        """Test order status creation without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_status_create', kwargs={'order_id': self.order.id})
        data = {
            'status': 'processing',
            'notes': 'Order is being processed'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_order_analytics_success(self):
        """Test successful order analytics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('order_analytics')
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'group_by': 'day'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_orders', response.data)
        self.assertIn('total_revenue', response.data)
        self.assertIn('average_order_value', response.data)
        self.assertIn('order_status_breakdown', response.data)
        self.assertIn('payment_status_breakdown', response.data)
        self.assertIn('daily_breakdown', response.data)
    
    def test_order_analytics_unauthorized(self):
        """Test order analytics without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_order_search_success(self):
        """Test successful order search"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_search')
        params = {
            'query': 'ORD-2024',
            'status': 'pending',
            'payment_status': 'pending'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_create')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_create')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_large_amount(self):
        """Test edge case with very large amount"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_create')
        data = {
            'total_amount': '999999999.99',  # Very large amount
            'shipping_address': '123 Test Street, Test City',
            'billing_address': '123 Test Street, Test City',
            'notes': 'Large amount order'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_special_characters_in_notes(self):
        """Test edge case with special characters in notes"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_create')
        data = {
            'total_amount': '99.99',
            'shipping_address': '123 Test Street, Test City',
            'billing_address': '123 Test Street, Test City',
            'notes': 'Order with special characters! 🎉 #success'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_unicode_in_address(self):
        """Test edge case with unicode characters in address"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('order_create')
        data = {
            'total_amount': '99.99',
            'shipping_address': 'Calle de Prueba 123, Ciudad de Prueba ✅',
            'billing_address': 'Calle de Prueba 123, Ciudad de Prueba ✅',
            'notes': 'Order with unicode address'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class OrdersModelTestCase(TestCase):
    """Test cases for Orders models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        
        self.designer = User.objects.create_user(
            username='designer',
            email='designer@example.com',
            password='password123',
            first_name='Designer',
            last_name='User'
        )
    
    def test_order_creation(self):
        """Test Order creation"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        self.assertEqual(order.order_number, 'ORD-2024-001')
        self.assertEqual(order.total_amount, Decimal('99.99'))
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.payment_status, 'pending')
        self.assertEqual(order.shipping_address, '123 Test Street, Test City')
        self.assertEqual(order.billing_address, '123 Test Street, Test City')
        self.assertEqual(order.notes, 'Test order notes')
        self.assertEqual(order.created_by, self.user)
        self.assertIsNotNone(order.created_at)
        self.assertIsNotNone(order.updated_at)
    
    def test_order_str(self):
        """Test Order string representation"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        expected_str = f"Order {order.id} - {order.order_number}"
        self.assertEqual(str(order), expected_str)
    
    def test_order_status_choices(self):
        """Test Order status choices"""
        choices = Order.STATUS_CHOICES
        
        self.assertIn(('pending', 'Pending'), choices)
        self.assertIn(('processing', 'Processing'), choices)
        self.assertIn(('shipped', 'Shipped'), choices)
        self.assertIn(('delivered', 'Delivered'), choices)
        self.assertIn(('cancelled', 'Cancelled'), choices)
        self.assertIn(('refunded', 'Refunded'), choices)
    
    def test_order_payment_status_choices(self):
        """Test Order payment status choices"""
        choices = Order.PAYMENT_STATUS_CHOICES
        
        self.assertIn(('pending', 'Pending'), choices)
        self.assertIn(('paid', 'Paid'), choices)
        self.assertIn(('failed', 'Failed'), choices)
        self.assertIn(('refunded', 'Refunded'), choices)
        self.assertIn(('partially_refunded', 'Partially Refunded'), choices)
    
    def test_order_update_status(self):
        """Test Order update_status method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        order.update_status(
            status='processing',
            updated_by_id=self.user.id,
            notes='Order is being processed'
        )
        
        self.assertEqual(order.status, 'processing')
        self.assertEqual(order.updated_by_id, self.user.id)
        self.assertEqual(order.notes, 'Order is being processed')
        self.assertIsNotNone(order.updated_at)
    
    def test_order_update_payment_status(self):
        """Test Order update_payment_status method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        order.update_payment_status(
            payment_status='paid',
            updated_by_id=self.user.id,
            notes='Payment completed'
        )
        
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.updated_by_id, self.user.id)
        self.assertEqual(order.notes, 'Payment completed')
        self.assertIsNotNone(order.updated_at)
    
    def test_order_cancel_order(self):
        """Test Order cancel_order method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        order.cancel_order(
            cancelled_by_id=self.user.id,
            cancellation_reason='Customer requested cancellation',
            notes='Order cancelled by customer'
        )
        
        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(order.cancelled_by_id, self.user.id)
        self.assertEqual(order.cancellation_reason, 'Customer requested cancellation')
        self.assertEqual(order.notes, 'Order cancelled by customer')
        self.assertIsNotNone(order.cancelled_at)
    
    def test_order_get_order_summary(self):
        """Test Order get_order_summary method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        summary = order.get_order_summary()
        
        self.assertEqual(summary['order_number'], 'ORD-2024-001')
        self.assertEqual(summary['total_amount'], Decimal('99.99'))
        self.assertEqual(summary['status'], 'pending')
        self.assertEqual(summary['payment_status'], 'pending')
        self.assertEqual(summary['shipping_address'], '123 Test Street, Test City')
        self.assertEqual(summary['billing_address'], '123 Test Street, Test City')
        self.assertEqual(summary['notes'], 'Test order notes')
        self.assertIsNotNone(summary['created_at'])
    
    def test_order_transaction_creation(self):
        """Test OrderTransaction creation"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        transaction = OrderTransaction.objects.create(
            order=order,
            transaction_type='payment',
            amount=Decimal('99.99'),
            status='pending',
            payment_method='card',
            transaction_id='txn_123456789',
            gateway_response={
                'status': 'pending',
                'gateway_id': 'pay_123456789'
            }
        )
        
        self.assertEqual(transaction.order, order)
        self.assertEqual(transaction.transaction_type, 'payment')
        self.assertEqual(transaction.amount, Decimal('99.99'))
        self.assertEqual(transaction.status, 'pending')
        self.assertEqual(transaction.payment_method, 'card')
        self.assertEqual(transaction.transaction_id, 'txn_123456789')
        self.assertEqual(transaction.gateway_response, {
            'status': 'pending',
            'gateway_id': 'pay_123456789'
        })
        self.assertIsNotNone(transaction.created_at)
        self.assertIsNotNone(transaction.updated_at)
    
    def test_order_transaction_str(self):
        """Test OrderTransaction string representation"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        transaction = OrderTransaction.objects.create(
            order=order,
            transaction_type='payment',
            amount=Decimal('99.99'),
            status='pending',
            payment_method='card',
            transaction_id='txn_123456789'
        )
        
        expected_str = f"Order Transaction {transaction.id} - {transaction.transaction_type}"
        self.assertEqual(str(transaction), expected_str)
    
    def test_order_transaction_transaction_type_choices(self):
        """Test OrderTransaction transaction type choices"""
        choices = OrderTransaction.TRANSACTION_TYPE_CHOICES
        
        self.assertIn(('payment', 'Payment'), choices)
        self.assertIn(('refund', 'Refund'), choices)
        self.assertIn(('partial_refund', 'Partial Refund'), choices)
        self.assertIn(('chargeback', 'Chargeback'), choices)
        self.assertIn(('adjustment', 'Adjustment'), choices)
    
    def test_order_transaction_status_choices(self):
        """Test OrderTransaction status choices"""
        choices = OrderTransaction.STATUS_CHOICES
        
        self.assertIn(('pending', 'Pending'), choices)
        self.assertIn(('completed', 'Completed'), choices)
        self.assertIn(('failed', 'Failed'), choices)
        self.assertIn(('cancelled', 'Cancelled'), choices)
        self.assertIn(('refunded', 'Refunded'), choices)
    
    def test_order_transaction_payment_method_choices(self):
        """Test OrderTransaction payment method choices"""
        choices = OrderTransaction.PAYMENT_METHOD_CHOICES
        
        self.assertIn(('card', 'Card'), choices)
        self.assertIn(('bank_transfer', 'Bank Transfer'), choices)
        self.assertIn(('upi', 'UPI'), choices)
        self.assertIn(('wallet', 'Wallet'), choices)
        self.assertIn(('cash', 'Cash'), choices)
    
    def test_order_transaction_update_status(self):
        """Test OrderTransaction update_status method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        transaction = OrderTransaction.objects.create(
            order=order,
            transaction_type='payment',
            amount=Decimal('99.99'),
            status='pending',
            payment_method='card',
            transaction_id='txn_123456789'
        )
        
        transaction.update_status(
            status='completed',
            updated_by_id=self.user.id,
            notes='Transaction completed successfully'
        )
        
        self.assertEqual(transaction.status, 'completed')
        self.assertEqual(transaction.updated_by_id, self.user.id)
        self.assertEqual(transaction.notes, 'Transaction completed successfully')
        self.assertIsNotNone(transaction.updated_at)
    
    def test_order_transaction_get_transaction_summary(self):
        """Test OrderTransaction get_transaction_summary method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        transaction = OrderTransaction.objects.create(
            order=order,
            transaction_type='payment',
            amount=Decimal('99.99'),
            status='pending',
            payment_method='card',
            transaction_id='txn_123456789',
            gateway_response={
                'status': 'pending',
                'gateway_id': 'pay_123456789'
            }
        )
        
        summary = transaction.get_transaction_summary()
        
        self.assertEqual(summary['transaction_type'], 'payment')
        self.assertEqual(summary['amount'], Decimal('99.99'))
        self.assertEqual(summary['status'], 'pending')
        self.assertEqual(summary['payment_method'], 'card')
        self.assertEqual(summary['transaction_id'], 'txn_123456789')
        self.assertEqual(summary['gateway_response'], {
            'status': 'pending',
            'gateway_id': 'pay_123456789'
        })
        self.assertIsNotNone(summary['created_at'])
    
    def test_order_item_creation(self):
        """Test OrderItem creation"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        item = OrderItem.objects.create(
            order=order,
            product_type='design',
            product_id=1,
            product_name='Modern Logo Template',
            quantity=1,
            unit_price=Decimal('99.99'),
            total_price=Decimal('99.99')
        )
        
        self.assertEqual(item.order, order)
        self.assertEqual(item.product_type, 'design')
        self.assertEqual(item.product_id, 1)
        self.assertEqual(item.product_name, 'Modern Logo Template')
        self.assertEqual(item.quantity, 1)
        self.assertEqual(item.unit_price, Decimal('99.99'))
        self.assertEqual(item.total_price, Decimal('99.99'))
        self.assertIsNotNone(item.created_at)
        self.assertIsNotNone(item.updated_at)
    
    def test_order_item_str(self):
        """Test OrderItem string representation"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        item = OrderItem.objects.create(
            order=order,
            product_type='design',
            product_id=1,
            product_name='Modern Logo Template',
            quantity=1,
            unit_price=Decimal('99.99'),
            total_price=Decimal('99.99')
        )
        
        expected_str = f"Order Item {item.id} - {item.product_name}"
        self.assertEqual(str(item), expected_str)
    
    def test_order_item_product_type_choices(self):
        """Test OrderItem product type choices"""
        choices = OrderItem.PRODUCT_TYPE_CHOICES
        
        self.assertIn(('design', 'Design'), choices)
        self.assertIn(('bundle', 'Bundle'), choices)
        self.assertIn(('subscription', 'Subscription'), choices)
        self.assertIn(('custom', 'Custom'), choices)
        self.assertIn(('other', 'Other'), choices)
    
    def test_order_item_update_quantity(self):
        """Test OrderItem update_quantity method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        item = OrderItem.objects.create(
            order=order,
            product_type='design',
            product_id=1,
            product_name='Modern Logo Template',
            quantity=1,
            unit_price=Decimal('99.99'),
            total_price=Decimal('99.99')
        )
        
        item.update_quantity(
            quantity=2,
            updated_by_id=self.user.id,
            notes='Quantity updated'
        )
        
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.total_price, Decimal('199.98'))
        self.assertEqual(item.updated_by_id, self.user.id)
        self.assertEqual(item.notes, 'Quantity updated')
        self.assertIsNotNone(item.updated_at)
    
    def test_order_item_get_item_summary(self):
        """Test OrderItem get_item_summary method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        item = OrderItem.objects.create(
            order=order,
            product_type='design',
            product_id=1,
            product_name='Modern Logo Template',
            quantity=1,
            unit_price=Decimal('99.99'),
            total_price=Decimal('99.99')
        )
        
        summary = item.get_item_summary()
        
        self.assertEqual(summary['product_type'], 'design')
        self.assertEqual(summary['product_id'], 1)
        self.assertEqual(summary['product_name'], 'Modern Logo Template')
        self.assertEqual(summary['quantity'], 1)
        self.assertEqual(summary['unit_price'], Decimal('99.99'))
        self.assertEqual(summary['total_price'], Decimal('99.99'))
        self.assertIsNotNone(summary['created_at'])
    
    def test_order_status_creation(self):
        """Test OrderStatus creation"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        order_status = OrderStatus.objects.create(
            order=order,
            status='pending',
            notes='Order created',
            updated_by=self.user
        )
        
        self.assertEqual(order_status.order, order)
        self.assertEqual(order_status.status, 'pending')
        self.assertEqual(order_status.notes, 'Order created')
        self.assertEqual(order_status.updated_by, self.user)
        self.assertIsNotNone(order_status.created_at)
    
    def test_order_status_str(self):
        """Test OrderStatus string representation"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        order_status = OrderStatus.objects.create(
            order=order,
            status='pending',
            notes='Order created',
            updated_by=self.user
        )
        
        expected_str = f"Order Status {order_status.id} - {order_status.status}"
        self.assertEqual(str(order_status), expected_str)
    
    def test_order_status_get_status_summary(self):
        """Test OrderStatus get_status_summary method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        order_status = OrderStatus.objects.create(
            order=order,
            status='pending',
            notes='Order created',
            updated_by=self.user
        )
        
        summary = order_status.get_status_summary()
        
        self.assertEqual(summary['status'], 'pending')
        self.assertEqual(summary['notes'], 'Order created')
        self.assertEqual(summary['updated_by'], self.user.id)
        self.assertIsNotNone(summary['created_at'])
    
    def test_order_get_total_items(self):
        """Test Order get_total_items method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        # Create order items
        OrderItem.objects.create(
            order=order,
            product_type='design',
            product_id=1,
            product_name='Modern Logo Template',
            quantity=1,
            unit_price=Decimal('99.99'),
            total_price=Decimal('99.99')
        )
        
        OrderItem.objects.create(
            order=order,
            product_type='bundle',
            product_id=2,
            product_name='Design Bundle',
            quantity=1,
            unit_price=Decimal('199.99'),
            total_price=Decimal('199.99')
        )
        
        total_items = order.get_total_items()
        self.assertEqual(total_items, 2)
    
    def test_order_get_total_quantity(self):
        """Test Order get_total_quantity method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        # Create order items
        OrderItem.objects.create(
            order=order,
            product_type='design',
            product_id=1,
            product_name='Modern Logo Template',
            quantity=2,
            unit_price=Decimal('99.99'),
            total_price=Decimal('199.98')
        )
        
        OrderItem.objects.create(
            order=order,
            product_type='bundle',
            product_id=2,
            product_name='Design Bundle',
            quantity=1,
            unit_price=Decimal('199.99'),
            total_price=Decimal('199.99')
        )
        
        total_quantity = order.get_total_quantity()
        self.assertEqual(total_quantity, 3)
    
    def test_order_can_be_cancelled(self):
        """Test Order can_be_cancelled method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='pending',
            payment_status='pending',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        # Test pending order
        self.assertTrue(order.can_be_cancelled())
        
        # Test cancelled order
        order.status = 'cancelled'
        order.save()
        self.assertFalse(order.can_be_cancelled())
        
        # Test delivered order
        order.status = 'delivered'
        order.save()
        self.assertFalse(order.can_be_cancelled())
    
    def test_order_can_be_refunded(self):
        """Test Order can_be_refunded method"""
        order = Order.objects.create(
            order_number='ORD-2024-001',
            total_amount=Decimal('99.99'),
            status='delivered',
            payment_status='paid',
            shipping_address='123 Test Street, Test City',
            billing_address='123 Test Street, Test City',
            notes='Test order notes',
            created_by=self.user
        )
        
        # Test delivered and paid order
        self.assertTrue(order.can_be_refunded())
        
        # Test pending order
        order.status = 'pending'
        order.save()
        self.assertFalse(order.can_be_refunded())
        
        # Test already refunded order
        order.status = 'delivered'
        order.payment_status = 'refunded'
        order.save()
        self.assertFalse(order.can_be_refunded())