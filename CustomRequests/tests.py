"""
Comprehensive tests for CustomRequests app
Tests custom order requests, comments, and custom order management
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

from .models import CustomOrderRequest, CustomOrderFile
from common.relations import attach_relation


class CustomRequestsAPITestCase(APITestCase):
    """Test cases for CustomRequests API endpoints"""
    
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
        
        # Create custom order request
        self.custom_order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        # Comments are now handled through OrderComment model via Order
        
        # Create custom order file
        self.custom_order_file = CustomOrderFile.objects.create(
            custom_order_request=self.custom_order,
            file_name='logo_concept.jpg',
            file_url='https://example.com/logo_concept.jpg',
            file_type='image',
            file_size=1024000,
            uploaded_by=self.designer
        )
    
    def test_custom_order_list_success(self):
        """Test successful custom order list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_custom_order_list_with_filters(self):
        """Test custom order list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_list')
        params = {
            'status': 'pending',
            'min_budget': '100.00',
            'max_budget': '1000.00',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'search': 'logo'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_custom_order_detail_success(self):
        """Test successful custom order detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_detail', kwargs={'order_id': self.custom_order.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('title', response.data)
        self.assertIn('description', response.data)
        self.assertIn('budget', response.data)
        self.assertIn('status', response.data)
        self.assertIn('sla_deadline', response.data)
        self.assertIn('created_at', response.data)
    
    def test_custom_order_detail_not_found(self):
        """Test custom order detail with non-existent order"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_detail', kwargs={'order_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_custom_order_create_success(self):
        """Test successful custom order creation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_create')
        data = {
            'title': 'Custom Website Design',
            'description': 'I need a modern website for my business',
            'budget': '1500.00',
            'category': 'web_design',
            'urgency': 'medium',
            'timeline': '2 weeks',
            'requirements': 'Responsive design, modern look'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('order', response.data)
    
    def test_custom_order_create_unauthorized(self):
        """Test custom order creation without authentication"""
        url = reverse('custom_order_create')
        data = {
            'title': 'Custom Website Design',
            'description': 'I need a modern website for my business',
            'budget': '1500.00'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_custom_order_update_success(self):
        """Test successful custom order update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_update', kwargs={'order_id': self.custom_order.id})
        data = {
            'title': 'Updated Custom Logo Design',
            'description': 'Updated description for logo design',
            'budget': '750.00',
            'requirements': 'Updated requirements'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('order', response.data)
    
    def test_custom_order_update_unauthorized(self):
        """Test custom order update without authentication"""
        url = reverse('custom_order_update', kwargs={'order_id': self.custom_order.id})
        data = {
            'title': 'Updated Custom Logo Design',
            'description': 'Updated description for logo design'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_custom_order_cancel_success(self):
        """Test successful custom order cancellation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_cancel', kwargs={'order_id': self.custom_order.id})
        data = {
            'cancellation_reason': 'Changed my mind',
            'notes': 'Order cancelled by customer'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify order was cancelled
        self.custom_order.refresh_from_db()
        self.assertEqual(self.custom_order.status, 'cancelled')
    
    def test_custom_order_cancel_unauthorized(self):
        """Test custom order cancellation without authentication"""
        url = reverse('custom_order_cancel', kwargs={'order_id': self.custom_order.id})
        data = {
            'cancellation_reason': 'Changed my mind',
            'notes': 'Order cancelled by customer'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_custom_order_assign_success(self):
        """Test successful custom order assignment"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('custom_order_assign', kwargs={'order_id': self.custom_order.id})
        data = {
            'assigned_to': self.designer.id,
            'admin_notes': 'Order assigned to designer'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify order was assigned
        self.custom_order.refresh_from_db()
        self.assertEqual(self.custom_order.assigned_to_id, self.designer.id)
    
    def test_custom_order_assign_unauthorized(self):
        """Test custom order assignment without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_assign', kwargs={'order_id': self.custom_order.id})
        data = {
            'assigned_to': self.designer.id,
            'admin_notes': 'Order assigned to designer'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_custom_order_status_update_success(self):
        """Test successful custom order status update"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('custom_order_status_update', kwargs={'order_id': self.custom_order.id})
        data = {
            'status': 'in_progress',
            'admin_notes': 'Order is now in progress'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify order status was updated
        self.custom_order.refresh_from_db()
        self.assertEqual(self.custom_order.status, 'in_progress')
    
    def test_custom_order_status_update_unauthorized(self):
        """Test custom order status update without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_status_update', kwargs={'order_id': self.custom_order.id})
        data = {
            'status': 'in_progress',
            'admin_notes': 'Order is now in progress'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # CustomOrderComment tests removed - comments now use OrderComment via Order model
    
    def test_custom_order_file_list_success(self):
        """Test successful custom order file list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_file_list', kwargs={'order_id': self.custom_order.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_custom_order_file_list_unauthorized(self):
        """Test custom order file list without authentication"""
        url = reverse('custom_order_file_list', kwargs={'order_id': self.custom_order.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_custom_order_file_detail_success(self):
        """Test successful custom order file detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_file_detail', kwargs={'file_id': self.custom_order_file.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('file_name', response.data)
        self.assertIn('file_url', response.data)
        self.assertIn('file_type', response.data)
        self.assertIn('file_size', response.data)
        self.assertIn('uploaded_by', response.data)
        self.assertIn('created_at', response.data)
    
    def test_custom_order_file_detail_not_found(self):
        """Test custom order file detail with non-existent file"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_file_detail', kwargs={'file_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_custom_order_file_upload_success(self):
        """Test successful custom order file upload"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('custom_order_file_upload', kwargs={'order_id': self.custom_order.id})
        data = {
            'file_name': 'design_concept.png',
            'file_url': 'https://example.com/design_concept.png',
            'file_type': 'image',
            'file_size': 2048000,
            'description': 'Initial design concept'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('file', response.data)
    
    def test_custom_order_file_upload_unauthorized(self):
        """Test custom order file upload without authentication"""
        url = reverse('custom_order_file_upload', kwargs={'order_id': self.custom_order.id})
        data = {
            'file_name': 'design_concept.png',
            'file_url': 'https://example.com/design_concept.png',
            'file_type': 'image',
            'file_size': 2048000,
            'description': 'Initial design concept'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_custom_order_file_delete_success(self):
        """Test successful custom order file deletion"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('custom_order_file_delete', kwargs={'file_id': self.custom_order_file.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_custom_order_file_delete_unauthorized(self):
        """Test custom order file deletion without authentication"""
        url = reverse('custom_order_file_delete', kwargs={'file_id': self.custom_order_file.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_custom_order_analytics_success(self):
        """Test successful custom order analytics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('custom_order_analytics')
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'group_by': 'day'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_orders', response.data)
        self.assertIn('pending_orders', response.data)
        self.assertIn('in_progress_orders', response.data)
        self.assertIn('completed_orders', response.data)
        self.assertIn('cancelled_orders', response.data)
        self.assertIn('total_budget', response.data)
        self.assertIn('average_budget', response.data)
        self.assertIn('daily_breakdown', response.data)
    
    def test_custom_order_analytics_unauthorized(self):
        """Test custom order analytics without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_custom_order_search_success(self):
        """Test successful custom order search"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_search')
        params = {
            'query': 'logo',
            'status': 'pending',
            'min_budget': '100.00',
            'max_budget': '1000.00'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_create')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_create')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_large_budget(self):
        """Test edge case with very large budget"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_create')
        data = {
            'title': 'Expensive Custom Project',
            'description': 'Very expensive custom project',
            'budget': '999999.99'  # Very large budget
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_special_characters_in_title(self):
        """Test edge case with special characters in title"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_create')
        data = {
            'title': 'Custom Design Project! 🎨 #creative',
            'description': 'A creative design project',
            'budget': '500.00'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_unicode_in_description(self):
        """Test edge case with unicode characters in description"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('custom_order_create')
        data = {
            'title': 'Unicode Custom Project',
            'description': 'Proyecto de diseño personalizado con caracteres unicode ✅',
            'budget': '500.00'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class CustomRequestsModelTestCase(TestCase):
    """Test cases for CustomRequests models"""
    
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
    
    def test_custom_order_request_creation(self):
        """Test CustomOrderRequest creation"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        self.assertEqual(order.title, 'Custom Logo Design')
        self.assertEqual(order.description, 'I need a modern logo for my startup company')
        self.assertEqual(order.budget, Decimal('500.00'))
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.created_by, self.user)
        self.assertIsNotNone(order.sla_deadline)
        self.assertIsNotNone(order.created_at)
        self.assertIsNotNone(order.updated_at)
    
    def test_custom_order_request_str(self):
        """Test CustomOrderRequest string representation"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        expected_str = f"Custom Order {order.pk} - {order.title} ({order.status})"
        self.assertEqual(str(order), expected_str)
    
    def test_custom_order_request_status_choices(self):
        """Test CustomOrderRequest status choices"""
        choices = CustomOrderRequest.STATUS_CHOICES
        
        # Workflow status choices (payment status is separate)
        self.assertIn(('pending', 'Pending'), choices)
        self.assertIn(('completed', 'Completed'), choices)
        self.assertIn(('in_progress', 'In Progress'), choices)
        self.assertIn(('cancelled', 'Cancelled'), choices)
        self.assertIn(('delayed', 'Delayed'), choices)
        
        # Payment status should not be in workflow status choices
        self.assertNotIn(('success', 'Success'), choices)
        self.assertNotIn(('failed', 'Failed'), choices)
    
    def test_custom_order_request_payment_status_choices(self):
        """Test CustomOrderRequest payment status choices"""
        payment_choices = CustomOrderRequest.PAYMENT_STATUS_CHOICES
        
        self.assertIn(('pending', 'Pending'), payment_choices)
        self.assertIn(('success', 'Success'), payment_choices)
        self.assertIn(('failed', 'Failed'), payment_choices)
    
    def test_custom_order_request_start_order(self):
        """Test CustomOrderRequest start_order method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        order.start_order(self.designer)
        
        self.assertEqual(order.status, 'in_progress')
        self.assertEqual(order.assigned_to_id, self.designer.id)
        self.assertIsNotNone(order.started_at)
    
    def test_custom_order_request_complete_order(self):
        """Test CustomOrderRequest complete_order method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='in_progress',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        order.complete_order(self.designer)
        
        self.assertEqual(order.status, 'completed')
        self.assertEqual(order.updated_by, self.designer)
        self.assertIsNotNone(order.completed_at)
    
    def test_custom_order_request_deliver_order(self):
        """Test CustomOrderRequest deliver_order method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='completed',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user,
            delivery_files_uploaded=True
        )
        
        order.deliver_order(self.designer, 'Final deliverable ready for download')
        
        self.assertIsNotNone(order.delivered_at)
        self.assertEqual(order.delivery_message, 'Final deliverable ready for download')
        self.assertTrue(order.customer_notified)
        self.assertEqual(order.updated_by, self.designer)
    
    def test_custom_order_request_cancel_order(self):
        """Test CustomOrderRequest cancel_order method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        order.cancel_order(
            self.user,
            'Changed my mind',
            'customer',
            Decimal('250.00'),
            '50% refund for customer cancellation'
        )
        
        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(order.cancellation_reason, 'Changed my mind')
        self.assertEqual(order.cancellation_type, 'customer')
        self.assertEqual(order.refund_amount, Decimal('250.00'))
        self.assertEqual(order.refund_reason, '50% refund for customer cancellation')
        self.assertEqual(order.updated_by, self.user)
    
    def test_custom_order_request_mark_delayed(self):
        """Test CustomOrderRequest mark_delayed method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='in_progress',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        order.mark_delayed(self.designer)
        
        self.assertEqual(order.status, 'delayed')
        self.assertEqual(order.updated_by, self.designer)
    
    def test_custom_order_request_check_sla_breach(self):
        """Test CustomOrderRequest check_sla_breach method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() - timedelta(hours=1),  # Past deadline
            created_by=self.user
        )
        
        # Test SLA breach
        self.assertTrue(order.check_sla_breach())
        
        # Test completed order
        order.status = 'completed'
        order.save()
        self.assertFalse(order.check_sla_breach())
    
    def test_custom_order_request_get_time_remaining(self):
        """Test CustomOrderRequest get_time_remaining method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        time_remaining = order.get_time_remaining()
        self.assertIsNotNone(time_remaining)
        self.assertGreater(time_remaining.total_seconds(), 0)
    
    def test_custom_order_request_get_sla_status(self):
        """Test CustomOrderRequest get_sla_status method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        sla_status = order.get_sla_status()
        self.assertIn(sla_status, ['normal', 'warning', 'critical', 'breached', 'completed'])
    
    def test_custom_order_request_can_be_cancelled(self):
        """Test CustomOrderRequest can_be_cancelled method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        # Test pending order
        self.assertTrue(order.can_be_cancelled())
        
        # Test completed order
        order.status = 'completed'
        order.save()
        self.assertFalse(order.can_be_cancelled())
    
    def test_custom_order_request_can_be_delivered(self):
        """Test CustomOrderRequest can_be_delivered method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='completed',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user,
            delivery_files_uploaded=True
        )
        
        # Test completed order with files
        self.assertTrue(order.can_be_delivered())
        
        # Test completed order without files
        order.delivery_files_uploaded = False
        order.save()
        self.assertFalse(order.can_be_delivered())
    
    def test_custom_order_request_get_refund_percentage(self):
        """Test CustomOrderRequest get_refund_percentage method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='cancelled',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user,
            cancellation_type='customer'
        )
        
        # Test customer cancellation
        self.assertEqual(order.get_refund_percentage(), 50)
        
        # Test admin cancellation
        order.cancellation_type = 'admin'
        order.save()
        self.assertEqual(order.get_refund_percentage(), 100)
        
        # Test system error
        order.cancellation_type = 'system'
        order.save()
        self.assertEqual(order.get_refund_percentage(), 100)
    
    def test_custom_order_request_get_order_summary(self):
        """Test CustomOrderRequest get_order_summary method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        summary = order.get_order_summary()
        
        self.assertEqual(summary['title'], 'Custom Logo Design')
        self.assertEqual(summary['description'], 'I need a modern logo for my startup company')
        self.assertEqual(summary['budget'], Decimal('500.00'))
        self.assertEqual(summary['status'], 'pending')
        self.assertIsNotNone(summary['sla_deadline'])
        self.assertIsNotNone(summary['created_at'])
    
    # CustomOrderComment model tests removed - comments now use OrderComment via Order model
    
        self.assertEqual(summary['created_by'], self.designer.id)
        self.assertIsNotNone(summary['created_at'])
    
    def test_custom_order_file_creation(self):
        """Test CustomOrderFile creation"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        file = CustomOrderFile.objects.create(
            custom_order_request=order,
            file_name='logo_concept.jpg',
            file_url='https://example.com/logo_concept.jpg',
            file_type='image',
            file_size=1024000,
            uploaded_by=self.designer
        )
        
        self.assertEqual(file.custom_order_request, order)
        self.assertEqual(file.file_name, 'logo_concept.jpg')
        self.assertEqual(file.file_url, 'https://example.com/logo_concept.jpg')
        self.assertEqual(file.file_type, 'image')
        self.assertEqual(file.file_size, 1024000)
        self.assertEqual(file.uploaded_by, self.designer)
        self.assertIsNotNone(file.created_at)
        self.assertIsNotNone(file.updated_at)
    
    def test_custom_order_file_str(self):
        """Test CustomOrderFile string representation"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        file = CustomOrderFile.objects.create(
            custom_order_request=order,
            file_name='logo_concept.jpg',
            file_url='https://example.com/logo_concept.jpg',
            file_type='image',
            file_size=1024000,
            uploaded_by=self.designer
        )
        
        expected_str = f"Custom Order File {file.id} - {file.file_name}"
        self.assertEqual(str(file), expected_str)
    
    def test_custom_order_file_file_type_choices(self):
        """Test CustomOrderFile file type choices"""
        choices = CustomOrderFile.FILE_TYPE_CHOICES
        
        self.assertIn(('image', 'Image'), choices)
        self.assertIn(('document', 'Document'), choices)
        self.assertIn(('video', 'Video'), choices)
        self.assertIn(('audio', 'Audio'), choices)
        self.assertIn(('archive', 'Archive'), choices)
        self.assertIn(('other', 'Other'), choices)
    
    def test_custom_order_file_get_file_size_display(self):
        """Test CustomOrderFile get_file_size_display method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        file = CustomOrderFile.objects.create(
            custom_order_request=order,
            file_name='logo_concept.jpg',
            file_url='https://example.com/logo_concept.jpg',
            file_type='image',
            file_size=1024000,
            uploaded_by=self.designer
        )
        
        size_display = file.get_file_size_display()
        self.assertEqual(size_display, '1.0 MB')
    
    def test_custom_order_file_get_file_extension(self):
        """Test CustomOrderFile get_file_extension method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        file = CustomOrderFile.objects.create(
            custom_order_request=order,
            file_name='logo_concept.jpg',
            file_url='https://example.com/logo_concept.jpg',
            file_type='image',
            file_size=1024000,
            uploaded_by=self.designer
        )
        
        extension = file.get_file_extension()
        self.assertEqual(extension, '.jpg')
    
    def test_custom_order_file_get_file_summary(self):
        """Test CustomOrderFile get_file_summary method"""
        order = CustomOrderRequest.objects.create(
            title='Custom Logo Design',
            description='I need a modern logo for my startup company',
            budget=Decimal('500.00'),
            status='pending',
            sla_deadline=timezone.now() + timedelta(hours=1),
            created_by=self.user
        )
        
        file = CustomOrderFile.objects.create(
            custom_order_request=order,
            file_name='logo_concept.jpg',
            file_url='https://example.com/logo_concept.jpg',
            file_type='image',
            file_size=1024000,
            uploaded_by=self.designer
        )
        
        summary = file.get_file_summary()
        
        self.assertEqual(summary['file_name'], 'logo_concept.jpg')
        self.assertEqual(summary['file_url'], 'https://example.com/logo_concept.jpg')
        self.assertEqual(summary['file_type'], 'image')
        self.assertEqual(summary['file_size'], 1024000)
        self.assertEqual(summary['uploaded_by'], self.designer.id)
        self.assertIsNotNone(summary['created_at'])