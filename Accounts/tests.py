"""
Comprehensive tests for Accounts views
Tests all accounts endpoints with various scenarios and edge cases
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json
from unittest.mock import patch, MagicMock
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from Accounts.models import Role, Permission
from Profiles.models import Addresses, DesignerProfile, Studio
from Plans.models import Subscription, Plan
from CustomRequests.models import CustomOrderRequest
from MediaFiles.models import Media
from Catalog.models import SubProduct, Product, Category


class AccountsAPITestCase(APITestCase):
    """Test cases for Accounts API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123',
            first_name='Admin',
            last_name='User'
        )
        
        # Create regular users
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='password123',
            first_name='User',
            last_name='One',
            is_active=True
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='password123',
            first_name='User',
            last_name='Two',
            is_active=True
        )
        
        self.inactive_user = User.objects.create_user(
            username='inactive',
            email='inactive@example.com',
            password='password123',
            first_name='Inactive',
            last_name='User',
            is_active=False
        )
        
        # Create roles and permissions
        self.role = Role.objects.create(
            role='Customer',
            created_by=self.admin_user
        )
        
        self.permission = Permission.objects.create(
            name='view_product',
            created_by=self.admin_user
        )
        
        # Create related objects
        self.address = Addresses.objects.create(
            address_line_1='123 Test St',
            city='Test City',
            state='Test State',
            country='Test Country',
            postal_code='12345',
            created_by=self.user1
        )
        
        self.plan = Plan.objects.create(
            plan_name='basic',
            description={'features': ['feature1', 'feature2']},
            price=29.99,
            plan_duration='monthly',
            created_by=self.admin_user
        )
        
        self.subscription = Subscription.objects.create(
            user=self.user1,
            plan=self.plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            status='active',
            created_by=self.user1
        )
        
        self.custom_order = CustomOrderRequest.objects.create(
            user=self.user1,
            title='Test Custom Order',
            description='Test Description',
            created_by=self.user1
        )
        
        self.media = Media.objects.create(
            file='test_media.jpg',
            media_type='image',
            created_by=self.user1
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            created_by=self.admin_user
        )
        
        self.product = Product.objects.create(
            title='Test Product',
            description='Test Description',
            category=self.category,
            product_plan_type='free',
            status='active',
            created_by=self.user1
        )
        
        self.sub_product = SubProduct.objects.create(
            product_number='SP001',
            color='red',
            price=19.99,
            created_by=self.user1
        )
    
    def test_users_list_admin_success(self):
        """Test successful users list retrieval by admin"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('users_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        self.assertIn('total_users', response.data)
        self.assertIn('active_users', response.data)
        self.assertIn('inactive_users', response.data)
        self.assertGreaterEqual(len(response.data['users']), 3)  # admin, user1, user2, inactive
    
    def test_users_list_non_admin_forbidden(self):
        """Test users list access by non-admin user"""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('users_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_users_list_unauthorized(self):
        """Test users list access without authentication"""
        url = reverse('users_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_users_list_with_pagination(self):
        """Test users list with pagination"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('users_list')
        response = self.client.get(url, {'page': 1, 'page_size': 2})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        self.assertIn('pagination', response.data)
    
    def test_users_list_with_search(self):
        """Test users list with search query"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('users_list')
        response = self.client.get(url, {'search': 'user1'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        # Should only return user1
        self.assertEqual(len(response.data['users']), 1)
        self.assertEqual(response.data['users'][0]['username'], 'user1')
    
    def test_users_list_with_status_filter(self):
        """Test users list with status filter"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('users_list')
        response = self.client.get(url, {'status': 'active'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        # Should only return active users
        for user in response.data['users']:
            self.assertTrue(user['is_active'])
    
    def test_user_detail_success(self):
        """Test successful user detail retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('user_detail', args=[self.user1.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['id'], self.user1.id)
        self.assertEqual(response.data['user']['username'], 'user1')
        self.assertIn('emails', response.data['user'])
        self.assertIn('mobile_numbers', response.data['user'])
        self.assertIn('addresses', response.data['user'])
        self.assertIn('subscriptions', response.data['user'])
        self.assertIn('custom_orders', response.data['user'])
        self.assertIn('media', response.data['user'])
        self.assertIn('sub_products', response.data['user'])
    
    def test_user_detail_not_found(self):
        """Test user detail with non-existent user ID"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('user_detail', args=[9999])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_user_detail_non_admin_forbidden(self):
        """Test user detail access by non-admin user"""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('user_detail', args=[self.user2.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_activate_user_success(self):
        """Test successful user activation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('activate_user', args=[self.inactive_user.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify user is now active
        self.inactive_user.refresh_from_db()
        self.assertTrue(self.inactive_user.is_active)
    
    def test_activate_user_already_active(self):
        """Test activating already active user"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('activate_user', args=[self.user1.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_activate_user_not_found(self):
        """Test activating non-existent user"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('activate_user', args=[9999])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_activate_user_non_admin_forbidden(self):
        """Test user activation by non-admin user"""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('activate_user', args=[self.inactive_user.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_deactivate_user_success(self):
        """Test successful user deactivation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('deactivate_user', args=[self.user1.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify user is now inactive
        self.user1.refresh_from_db()
        self.assertFalse(self.user1.is_active)
    
    def test_deactivate_user_already_inactive(self):
        """Test deactivating already inactive user"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('deactivate_user', args=[self.inactive_user.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_deactivate_user_not_found(self):
        """Test deactivating non-existent user"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('deactivate_user', args=[9999])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_deactivate_user_non_admin_forbidden(self):
        """Test user deactivation by non-admin user"""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('deactivate_user', args=[self.user2.id])
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_delete_user_success(self):
        """Test successful user deletion"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create a user to delete
        user_to_delete = User.objects.create_user(
            username='todelete',
            email='todelete@example.com',
            password='password123'
        )
        
        url = reverse('delete_user', args=[user_to_delete.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify user was deleted
        self.assertFalse(User.objects.filter(id=user_to_delete.id).exists())
    
    def test_delete_user_not_found(self):
        """Test deleting non-existent user"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('delete_user', args=[9999])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_delete_user_non_admin_forbidden(self):
        """Test user deletion by non-admin user"""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('delete_user', args=[self.user2.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_delete_user_with_related_data(self):
        """Test deleting user with related data"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Create user with related data
        user_with_data = User.objects.create_user(
            username='withdata',
            email='withdata@example.com',
            password='password123'
        )
        
        # Create related objects
        Addresses.objects.create(
            address_line_1='123 Test St',
            city='Test City',
            state='Test State',
            country='Test Country',
            postal_code='12345',
            created_by=user_with_data
        )
        
        url = reverse('delete_user', args=[user_with_data.id])
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_user_stats_success(self):
        """Test successful user statistics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('user_stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_users', response.data)
        self.assertIn('active_users', response.data)
        self.assertIn('inactive_users', response.data)
        self.assertIn('new_users_today', response.data)
        self.assertIn('new_users_this_week', response.data)
        self.assertIn('new_users_this_month', response.data)
        self.assertGreaterEqual(response.data['total_users'], 4)  # admin, user1, user2, inactive
    
    def test_user_stats_non_admin_forbidden(self):
        """Test user stats access by non-admin user"""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('user_stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_search_users_success(self):
        """Test successful user search"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        response = self.client.get(url, {'search': 'user1'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        self.assertEqual(len(response.data['users']), 1)
        self.assertEqual(response.data['users'][0]['username'], 'user1')
    
    def test_search_users_by_email(self):
        """Test user search by email"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        response = self.client.get(url, {'search': 'user1@example.com'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        self.assertEqual(len(response.data['users']), 1)
        self.assertEqual(response.data['users'][0]['email'], 'user1@example.com')
    
    def test_search_users_by_name(self):
        """Test user search by name"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        response = self.client.get(url, {'search': 'User One'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        self.assertEqual(len(response.data['users']), 1)
        self.assertEqual(response.data['users'][0]['first_name'], 'User')
        self.assertEqual(response.data['users'][0]['last_name'], 'One')
    
    def test_search_users_no_results(self):
        """Test user search with no results"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        response = self.client.get(url, {'search': 'nonexistent'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        self.assertEqual(len(response.data['users']), 0)
    
    def test_search_users_empty_query(self):
        """Test user search with empty query"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        response = self.client.get(url, {'search': ''})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('search', response.data)
    
    def test_search_users_non_admin_forbidden(self):
        """Test user search by non-admin user"""
        self.client.force_authenticate(user=self.user1)
        
        url = reverse('search_users')
        response = self.client.get(url, {'search': 'user2'})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_edge_case_very_long_search_query(self):
        """Test edge case with very long search query"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        long_query = 'a' * 1000  # Very long search query
        response = self.client.get(url, {'search': long_query})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_special_characters_in_search(self):
        """Test edge case with special characters in search query"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        response = self.client.get(url, {'search': '!@#$%^&*()'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
    
    def test_edge_case_unicode_in_search(self):
        """Test edge case with unicode characters in search query"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        response = self.client.get(url, {'search': 'José García'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
    
    def test_edge_case_negative_user_id(self):
        """Test edge case with negative user ID"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('user_detail', args=[-1])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_edge_case_zero_user_id(self):
        """Test edge case with zero user ID"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('user_detail', args=[0])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_edge_case_very_large_user_id(self):
        """Test edge case with very large user ID"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('user_detail', args=[999999999])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON in request body"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('users_list')
        response = self.client.post(
            url,
            'invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def test_edge_case_empty_request_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
    
    def test_edge_case_sql_injection_in_search(self):
        """Test edge case with SQL injection attempt in search"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        response = self.client.get(url, {'search': "'; DROP TABLE auth_user; --"})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        # Should not cause any issues due to Django's ORM protection
    
    def test_edge_case_xss_in_search(self):
        """Test edge case with XSS attempt in search"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('search_users')
        response = self.client.get(url, {'search': '<script>alert("xss")</script>'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        # Should be properly escaped in response


class AccountsRelationTests(TestCase):
    """Test cases for accounts app relation management"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.address = Addresses.objects.create(
            address_line_1='123 Test St',
            city='Test City',
            state='Test State',
            country='Test Country',
            postal_code='12345',
            created_by=self.user
        )
        
        self.plan = Plan.objects.create(
            plan_name='basic',
            description={'features': ['feature1', 'feature2']},
            price=29.99,
            plan_duration='monthly',
            created_by=self.user
        )
        
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            status='active',
            created_by=self.user
        )
        
        self.custom_order = CustomOrderRequest.objects.create(
            user=self.user,
            title='Test Custom Order',
            description='Test Description',
            created_by=self.user
        )
        
        self.media = Media.objects.create(
            file='test_media.jpg',
            media_type='image',
            created_by=self.user
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            created_by=self.user
        )
        
        self.product = Product.objects.create(
            title='Test Product',
            description='Test Description',
            category=self.category,
            product_plan_type='free',
            status='active',
            created_by=self.user
        )
        
        self.sub_product = SubProduct.objects.create(
            product_number='SP001',
            color='red',
            price=19.99,
            created_by=self.user
        )
    
    def test_user_address_relationship(self):
        """Test User:Address relationship"""
        # Test attachment
        self.user.attach_address(self.address, created_by=self.user)
        assert self.user.get_addresses().filter(pk=self.address.pk).exists()
        
        # Test detachment
        self.user.detach_address(self.address)
        assert not self.user.get_addresses().filter(pk=self.address.pk).exists()
    
    def test_user_subscription_relationship(self):
        """Test User:Subscription relationship"""
        # Test attachment
        self.user.attach_subscription(self.subscription, created_by=self.user)
        assert self.user.get_subscriptions().filter(pk=self.subscription.pk).exists()
        
        # Test detachment
        self.user.detach_subscription(self.subscription)
        assert not self.user.get_subscriptions().filter(pk=self.subscription.pk).exists()
    
    def test_user_custom_order_relationship(self):
        """Test User:CustomOrderRequest relationship"""
        # Test attachment
        self.user.attach_custom_order_request(self.custom_order, created_by=self.user)
        assert self.user.get_custom_order_requests().filter(pk=self.custom_order.pk).exists()
        
        # Test detachment
        self.user.detach_custom_order_request(self.custom_order)
        assert not self.user.get_custom_order_requests().filter(pk=self.custom_order.pk).exists()
    
    def test_user_media_relationship(self):
        """Test User:Media relationship"""
        # Test attachment
        self.user.attach_media(self.media, created_by=self.user)
        assert self.user.get_media().filter(pk=self.media.pk).exists()
        
        # Test detachment
        self.user.detach_media(self.media)
        assert not self.user.get_media().filter(pk=self.media.pk).exists()
    
    def test_user_subproduct_relationship(self):
        """Test User:SubProduct relationship"""
        # Test attachment
        self.user.attach_sub_product(self.sub_product, created_by=self.user)
        assert self.user.get_sub_products().filter(pk=self.sub_product.pk).exists()
        
        # Test detachment
        self.user.detach_sub_product(self.sub_product)
        assert not self.user.get_sub_products().filter(pk=self.sub_product.pk).exists()