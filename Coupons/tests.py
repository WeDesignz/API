"""
Comprehensive tests for Coupons views
Tests all coupons endpoints with various scenarios and edge cases
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

from Coupons.models import Coupon, CouponUsage


class CouponsAPITestCase(APITestCase):
    """Test cases for Coupons API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User',
            is_active=True
        )
        
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123',
            first_name='Admin',
            last_name='User'
        )
        
        # Create coupons
        self.active_coupon = Coupon.objects.create(
            code='SAVE20',
            description='20% off on all items',
            discount_type='percentage',
            discount_value=20.0,
            min_order_amount=100.0,
            max_discount_amount=50.0,
            usage_limit=100,
            valid_from=timezone.now(),
            valid_until=timezone.now() + timedelta(days=30),
            is_active=True,
            created_by=self.admin_user
        )
        
        self.expired_coupon = Coupon.objects.create(
            code='EXPIRED',
            description='Expired coupon',
            discount_type='fixed',
            discount_value=10.0,
            min_order_amount=50.0,
            usage_limit=50,
            valid_from=timezone.now() - timedelta(days=30),
            valid_until=timezone.now() - timedelta(days=1),
            is_active=False,
            created_by=self.admin_user
        )
        
        # Create coupon usage
        self.coupon_usage = CouponUsage.objects.create(
            user=self.user,
            coupon=self.active_coupon,
            order_id=12345,
            discount_amount=20.0,
            created_by=self.user
        )
    
    def test_coupons_list_success(self):
        """Test successful coupons list retrieval"""
        url = reverse('coupons_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('coupons', response.data)
        self.assertIn('total_coupons', response.data)
        self.assertTrue(any(c['code'] == self.active_coupon.code for c in response.data['coupons']))
    
    def test_coupons_list_with_filters(self):
        """Test coupons list with filters"""
        url = reverse('coupons_list')
        response = self.client.get(url, {
            'is_active': 'true',
            'discount_type': 'percentage'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('coupons', response.data)
        # Should only return active percentage coupons
        for coupon in response.data['coupons']:
            self.assertTrue(coupon['is_active'])
            self.assertEqual(coupon['discount_type'], 'percentage')
    
    def test_coupon_detail_success(self):
        """Test successful coupon detail retrieval"""
        url = reverse('coupon_detail', args=[self.active_coupon.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('coupon', response.data)
        self.assertEqual(response.data['coupon']['id'], self.active_coupon.id)
        self.assertIn('code', response.data['coupon'])
        self.assertIn('description', response.data['coupon'])
        self.assertIn('discount_type', response.data['coupon'])
    
    def test_coupon_detail_not_found(self):
        """Test coupon detail with non-existent coupon ID"""
        url = reverse('coupon_detail', args=[9999])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_validate_coupon_success(self):
        """Test successful coupon validation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        data = {
            'code': self.active_coupon.code,
            'order_amount': 150.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('valid', response.data)
        self.assertTrue(response.data['valid'])
        self.assertIn('discount_amount', response.data)
        self.assertIn('coupon', response.data)
    
    def test_validate_coupon_invalid_code(self):
        """Test coupon validation with invalid code"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        data = {
            'code': 'INVALID',
            'order_amount': 150.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_validate_coupon_expired(self):
        """Test coupon validation with expired coupon"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        data = {
            'code': self.expired_coupon.code,
            'order_amount': 150.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_validate_coupon_minimum_amount(self):
        """Test coupon validation with insufficient order amount"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        data = {
            'code': self.active_coupon.code,
            'order_amount': 50.0  # Less than minimum required
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_validate_coupon_usage_limit_exceeded(self):
        """Test coupon validation when usage limit is exceeded"""
        # Create multiple usages to exceed limit
        for i in range(self.active_coupon.usage_limit + 1):
            CouponUsage.objects.create(
                user=self.user,
                coupon=self.active_coupon,
                order_id=12345 + i,
                discount_amount=20.0,
                created_by=self.user
            )
        
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        data = {
            'code': self.active_coupon.code,
            'order_amount': 150.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_validate_coupon_unauthorized(self):
        """Test coupon validation without authentication"""
        url = reverse('validate_coupon')
        data = {
            'code': self.active_coupon.code,
            'order_amount': 150.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_apply_coupon_success(self):
        """Test successful coupon application"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('apply_coupon')
        data = {
            'code': self.active_coupon.code,
            'order_amount': 150.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('discount_amount', response.data)
        self.assertIn('final_amount', response.data)
    
    def test_apply_coupon_invalid(self):
        """Test coupon application with invalid coupon"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('apply_coupon')
        data = {
            'code': 'INVALID',
            'order_amount': 150.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_my_coupons_success(self):
        """Test successful my coupons retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('my_coupons')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('coupons', response.data)
        self.assertIn('total_coupons', response.data)
        self.assertTrue(any(c['id'] == self.active_coupon.id for c in response.data['coupons']))
    
    def test_my_coupons_unauthorized(self):
        """Test my coupons without authentication"""
        url = reverse('my_coupons')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_coupon_usage_history_success(self):
        """Test successful coupon usage history retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('coupon_usage_history')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('usage_history', response.data)
        self.assertIn('total_usage', response.data)
        self.assertTrue(any(u['id'] == self.coupon_usage.id for u in response.data['usage_history']))
    
    def test_coupon_usage_history_unauthorized(self):
        """Test coupon usage history without authentication"""
        url = reverse('coupon_usage_history')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_edge_case_negative_coupon_id(self):
        """Test edge case with negative coupon ID"""
        url = reverse('coupon_detail', args=[-1])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_edge_case_zero_coupon_id(self):
        """Test edge case with zero coupon ID"""
        url = reverse('coupon_detail', args=[0])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_edge_case_very_large_coupon_id(self):
        """Test edge case with very large coupon ID"""
        url = reverse('coupon_detail', args=[999999999])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        response = self.client.post(
            url,
            'invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_empty_request_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', response.data)
        self.assertIn('order_amount', response.data)
    
    def test_edge_case_very_long_coupon_code(self):
        """Test edge case with very long coupon code"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        data = {
            'code': 'A' * 1000,  # Very long code
            'order_amount': 150.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_negative_order_amount(self):
        """Test edge case with negative order amount"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        data = {
            'code': self.active_coupon.code,
            'order_amount': -100.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_zero_order_amount(self):
        """Test edge case with zero order amount"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        data = {
            'code': self.active_coupon.code,
            'order_amount': 0.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_sql_injection_in_code(self):
        """Test edge case with SQL injection attempt in coupon code"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        data = {
            'code': "'; DROP TABLE coupons_coupon; --",
            'order_amount': 150.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Should not cause any issues due to Django's ORM protection
    
    def test_edge_case_xss_in_code(self):
        """Test edge case with XSS attempt in coupon code"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('validate_coupon')
        data = {
            'code': '<script>alert("xss")</script>',
            'order_amount': 150.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Should be properly handled
