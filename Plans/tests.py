"""
Comprehensive tests for Plans app
Tests subscription plans, subscriptions, and plan management
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

from .models import Plan, Subscription, PlanFeature, PlanCategory


class PlansAPITestCase(APITestCase):
    """Test cases for Plans API endpoints"""
    
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
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin123',
            first_name='Admin',
            last_name='User',
            is_active=True,
            is_staff=True
        )
        
        # Create plan category
        self.plan_category = PlanCategory.objects.create(
            name='Basic Plans',
            description='Basic subscription plans',
            display_order=1,
            is_active=True
        )
        
        # Create plan features
        self.plan_feature1 = PlanFeature.objects.create(
            name='Unlimited Downloads',
            description='Download unlimited designs',
            is_active=True
        )
        
        self.plan_feature2 = PlanFeature.objects.create(
            name='Premium Support',
            description='24/7 premium support',
            is_active=True
        )
        
        # Create subscription plan
        self.plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        # Add features to plan
        self.plan.features.add(self.plan_feature1, self.plan_feature2)
        
        # Create subscription
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
    
    def test_plan_list_success(self):
        """Test successful plan list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_plan_list_with_filters(self):
        """Test plan list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_list')
        params = {
            'billing_cycle': 'monthly',
            'min_price': '10.00',
            'max_price': '100.00',
            'is_active': 'true',
            'category': self.plan_category.id,
            'search': 'basic'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_plan_detail_success(self):
        """Test successful plan detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_detail', kwargs={'plan_id': self.plan.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('name', response.data)
        self.assertIn('description', response.data)
        self.assertIn('price', response.data)
        self.assertIn('billing_cycle', response.data)
        self.assertIn('duration_days', response.data)
        self.assertIn('max_downloads', response.data)
        self.assertIn('is_active', response.data)
        self.assertIn('features', response.data)
        self.assertIn('category', response.data)
        self.assertIn('created_at', response.data)
    
    def test_plan_detail_not_found(self):
        """Test plan detail with non-existent plan"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_detail', kwargs={'plan_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_plan_create_success(self):
        """Test successful plan creation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_create')
        data = {
            'name': 'Premium Plan',
            'description': 'Premium subscription plan',
            'price': '99.99',
            'billing_cycle': 'monthly',
            'duration_days': 30,
            'max_downloads': 1000,
            'is_active': True,
            'category': self.plan_category.id,
            'features': [self.plan_feature1.id, self.plan_feature2.id]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('plan', response.data)
    
    def test_plan_create_unauthorized(self):
        """Test plan creation without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_create')
        data = {
            'name': 'Premium Plan',
            'description': 'Premium subscription plan',
            'price': '99.99',
            'billing_cycle': 'monthly',
            'duration_days': 30,
            'max_downloads': 1000,
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_plan_update_success(self):
        """Test successful plan update"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_update', kwargs={'plan_id': self.plan.id})
        data = {
            'name': 'Updated Basic Plan',
            'description': 'Updated basic subscription plan',
            'price': '39.99',
            'max_downloads': 200
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('plan', response.data)
    
    def test_plan_update_unauthorized(self):
        """Test plan update without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_update', kwargs={'plan_id': self.plan.id})
        data = {
            'name': 'Updated Basic Plan',
            'description': 'Updated basic subscription plan',
            'price': '39.99'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_plan_deactivate_success(self):
        """Test successful plan deactivation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_deactivate', kwargs={'plan_id': self.plan.id})
        data = {
            'reason': 'Plan no longer available',
            'admin_notes': 'Deactivating plan due to policy changes'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify plan was deactivated
        self.plan.refresh_from_db()
        self.assertFalse(self.plan.is_active)
    
    def test_plan_deactivate_unauthorized(self):
        """Test plan deactivation without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_deactivate', kwargs={'plan_id': self.plan.id})
        data = {
            'reason': 'Plan no longer available',
            'admin_notes': 'Deactivating plan due to policy changes'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_plan_analytics_success(self):
        """Test successful plan analytics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_analytics')
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'group_by': 'day'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_plans', response.data)
        self.assertIn('active_plans', response.data)
        self.assertIn('inactive_plans', response.data)
        self.assertIn('total_subscriptions', response.data)
        self.assertIn('active_subscriptions', response.data)
        self.assertIn('total_revenue', response.data)
        self.assertIn('average_revenue', response.data)
        self.assertIn('daily_breakdown', response.data)
    
    def test_plan_analytics_unauthorized(self):
        """Test plan analytics without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_plan_feature_list_success(self):
        """Test successful plan feature list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_feature_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_plan_feature_list_unauthorized(self):
        """Test plan feature list without authentication"""
        url = reverse('plan_feature_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_plan_feature_detail_success(self):
        """Test successful plan feature detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_feature_detail', kwargs={'feature_id': self.plan_feature1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('name', response.data)
        self.assertIn('description', response.data)
        self.assertIn('is_active', response.data)
        self.assertIn('created_at', response.data)
    
    def test_plan_feature_detail_not_found(self):
        """Test plan feature detail with non-existent feature"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_feature_detail', kwargs={'feature_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_plan_feature_create_success(self):
        """Test successful plan feature creation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_feature_create')
        data = {
            'name': 'Advanced Analytics',
            'description': 'Access to advanced analytics dashboard',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('feature', response.data)
    
    def test_plan_feature_create_unauthorized(self):
        """Test plan feature creation without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_feature_create')
        data = {
            'name': 'Advanced Analytics',
            'description': 'Access to advanced analytics dashboard',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_plan_feature_update_success(self):
        """Test successful plan feature update"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_feature_update', kwargs={'feature_id': self.plan_feature1.id})
        data = {
            'name': 'Updated Unlimited Downloads',
            'description': 'Updated description for unlimited downloads',
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('feature', response.data)
    
    def test_plan_feature_update_unauthorized(self):
        """Test plan feature update without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_feature_update', kwargs={'feature_id': self.plan_feature1.id})
        data = {
            'name': 'Updated Unlimited Downloads',
            'description': 'Updated description for unlimited downloads',
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_plan_feature_delete_success(self):
        """Test successful plan feature deletion"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_feature_delete', kwargs={'feature_id': self.plan_feature1.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_plan_feature_delete_unauthorized(self):
        """Test plan feature deletion without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_feature_delete', kwargs={'feature_id': self.plan_feature1.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_plan_category_list_success(self):
        """Test successful plan category list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_category_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_plan_category_list_unauthorized(self):
        """Test plan category list without authentication"""
        url = reverse('plan_category_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_plan_category_detail_success(self):
        """Test successful plan category detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_category_detail', kwargs={'category_id': self.plan_category.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('name', response.data)
        self.assertIn('description', response.data)
        self.assertIn('display_order', response.data)
        self.assertIn('is_active', response.data)
        self.assertIn('created_at', response.data)
    
    def test_plan_category_detail_not_found(self):
        """Test plan category detail with non-existent category"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_category_detail', kwargs={'category_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_plan_category_create_success(self):
        """Test successful plan category creation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_category_create')
        data = {
            'name': 'Premium Plans',
            'description': 'Premium subscription plans',
            'display_order': 2,
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('category', response.data)
    
    def test_plan_category_create_unauthorized(self):
        """Test plan category creation without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_category_create')
        data = {
            'name': 'Premium Plans',
            'description': 'Premium subscription plans',
            'display_order': 2,
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_plan_category_update_success(self):
        """Test successful plan category update"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_category_update', kwargs={'category_id': self.plan_category.id})
        data = {
            'name': 'Updated Basic Plans',
            'description': 'Updated basic subscription plans',
            'display_order': 3,
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('category', response.data)
    
    def test_plan_category_update_unauthorized(self):
        """Test plan category update without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_category_update', kwargs={'category_id': self.plan_category.id})
        data = {
            'name': 'Updated Basic Plans',
            'description': 'Updated basic subscription plans',
            'display_order': 3,
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_plan_category_delete_success(self):
        """Test successful plan category deletion"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_category_delete', kwargs={'category_id': self.plan_category.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_plan_category_delete_unauthorized(self):
        """Test plan category deletion without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_category_delete', kwargs={'category_id': self.plan_category.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_subscription_list_success(self):
        """Test successful subscription list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('subscription_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_subscription_list_with_filters(self):
        """Test subscription list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('subscription_list')
        params = {
            'status': 'active',
            'plan': self.plan.id,
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'is_active': 'true'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_subscription_detail_success(self):
        """Test successful subscription detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('subscription_detail', kwargs={'subscription_id': self.subscription.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('user', response.data)
        self.assertIn('plan', response.data)
        self.assertIn('status', response.data)
        self.assertIn('start_date', response.data)
        self.assertIn('end_date', response.data)
        self.assertIn('is_active', response.data)
        self.assertIn('created_at', response.data)
    
    def test_subscription_detail_not_found(self):
        """Test subscription detail with non-existent subscription"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('subscription_detail', kwargs={'subscription_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_subscription_create_success(self):
        """Test successful subscription creation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('subscription_create')
        data = {
            'plan': self.plan.id,
            'start_date': timezone.now().isoformat(),
            'end_date': (timezone.now() + timedelta(days=30)).isoformat(),
            'status': 'active',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('subscription', response.data)
    
    def test_subscription_create_unauthorized(self):
        """Test subscription creation without authentication"""
        url = reverse('subscription_create')
        data = {
            'plan': self.plan.id,
            'start_date': timezone.now().isoformat(),
            'end_date': (timezone.now() + timedelta(days=30)).isoformat(),
            'status': 'active',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_subscription_update_success(self):
        """Test successful subscription update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('subscription_update', kwargs={'subscription_id': self.subscription.id})
        data = {
            'status': 'cancelled',
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('subscription', response.data)
    
    def test_subscription_update_unauthorized(self):
        """Test subscription update without authentication"""
        url = reverse('subscription_update', kwargs={'subscription_id': self.subscription.id})
        data = {
            'status': 'cancelled',
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_subscription_cancel_success(self):
        """Test successful subscription cancellation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('subscription_cancel', kwargs={'subscription_id': self.subscription.id})
        data = {
            'cancellation_reason': 'No longer needed',
            'notes': 'Customer requested cancellation'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify subscription was cancelled
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, 'cancelled')
        self.assertFalse(self.subscription.is_active)
    
    def test_subscription_cancel_unauthorized(self):
        """Test subscription cancellation without authentication"""
        url = reverse('subscription_cancel', kwargs={'subscription_id': self.subscription.id})
        data = {
            'cancellation_reason': 'No longer needed',
            'notes': 'Customer requested cancellation'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_subscription_renew_success(self):
        """Test successful subscription renewal"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('subscription_renew', kwargs={'subscription_id': self.subscription.id})
        data = {
            'renewal_duration_days': 30,
            'admin_notes': 'Subscription renewed for 30 days'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('subscription', response.data)
    
    def test_subscription_renew_unauthorized(self):
        """Test subscription renewal without authentication"""
        url = reverse('subscription_renew', kwargs={'subscription_id': self.subscription.id})
        data = {
            'renewal_duration_days': 30,
            'admin_notes': 'Subscription renewed for 30 days'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_subscription_analytics_success(self):
        """Test successful subscription analytics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('subscription_analytics')
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'group_by': 'day'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_subscriptions', response.data)
        self.assertIn('active_subscriptions', response.data)
        self.assertIn('cancelled_subscriptions', response.data)
        self.assertIn('expired_subscriptions', response.data)
        self.assertIn('total_revenue', response.data)
        self.assertIn('average_revenue', response.data)
        self.assertIn('daily_breakdown', response.data)
    
    def test_subscription_analytics_unauthorized(self):
        """Test subscription analytics without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('subscription_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_create')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('plan_create')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_large_price(self):
        """Test edge case with very large price"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_create')
        data = {
            'name': 'Expensive Plan',
            'description': 'Very expensive plan',
            'price': '999999.99',  # Very large price
            'billing_cycle': 'monthly',
            'duration_days': 30,
            'max_downloads': 1000,
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_special_characters_in_name(self):
        """Test edge case with special characters in name"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_create')
        data = {
            'name': 'Premium Plan! 🚀 #awesome',
            'description': 'A premium plan with special characters',
            'price': '99.99',
            'billing_cycle': 'monthly',
            'duration_days': 30,
            'max_downloads': 1000,
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_unicode_in_description(self):
        """Test edge case with unicode characters in description"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('plan_create')
        data = {
            'name': 'Unicode Plan',
            'description': 'Plan de suscripción con caracteres unicode ✅',
            'price': '99.99',
            'billing_cycle': 'monthly',
            'duration_days': 30,
            'max_downloads': 1000,
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class PlansModelTestCase(TestCase):
    """Test cases for Plans models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        
        self.plan_category = PlanCategory.objects.create(
            name='Basic Plans',
            description='Basic subscription plans',
            display_order=1,
            is_active=True
        )
        
        self.plan_feature = PlanFeature.objects.create(
            name='Unlimited Downloads',
            description='Download unlimited designs',
            is_active=True
        )
    
    def test_plan_creation(self):
        """Test Plan creation"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        self.assertEqual(plan.name, 'Basic Plan')
        self.assertEqual(plan.description, 'Basic subscription plan')
        self.assertEqual(plan.price, Decimal('29.99'))
        self.assertEqual(plan.billing_cycle, 'monthly')
        self.assertEqual(plan.duration_days, 30)
        self.assertEqual(plan.max_downloads, 100)
        self.assertTrue(plan.is_active)
        self.assertEqual(plan.category, self.plan_category)
        self.assertIsNotNone(plan.created_at)
        self.assertIsNotNone(plan.updated_at)
    
    def test_plan_str(self):
        """Test Plan string representation"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        expected_str = f"Plan {plan.pk} - {plan.name} ({plan.billing_cycle})"
        self.assertEqual(str(plan), expected_str)
    
    def test_plan_billing_cycle_choices(self):
        """Test Plan billing cycle choices"""
        choices = Plan.BILLING_CYCLE_CHOICES
        
        self.assertIn(('monthly', 'Monthly'), choices)
        self.assertIn(('yearly', 'Yearly'), choices)
        self.assertIn(('lifetime', 'Lifetime'), choices)
    
    def test_plan_get_plan_summary(self):
        """Test Plan get_plan_summary method"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        summary = plan.get_plan_summary()
        
        self.assertEqual(summary['name'], 'Basic Plan')
        self.assertEqual(summary['description'], 'Basic subscription plan')
        self.assertEqual(summary['price'], Decimal('29.99'))
        self.assertEqual(summary['billing_cycle'], 'monthly')
        self.assertEqual(summary['duration_days'], 30)
        self.assertEqual(summary['max_downloads'], 100)
        self.assertTrue(summary['is_active'])
        self.assertEqual(summary['category'], self.plan_category.id)
        self.assertIsNotNone(summary['created_at'])
    
    def test_plan_category_creation(self):
        """Test PlanCategory creation"""
        category = PlanCategory.objects.create(
            name='Premium Plans',
            description='Premium subscription plans',
            display_order=2,
            is_active=True
        )
        
        self.assertEqual(category.name, 'Premium Plans')
        self.assertEqual(category.description, 'Premium subscription plans')
        self.assertEqual(category.display_order, 2)
        self.assertTrue(category.is_active)
        self.assertIsNotNone(category.created_at)
        self.assertIsNotNone(category.updated_at)
    
    def test_plan_category_str(self):
        """Test PlanCategory string representation"""
        category = PlanCategory.objects.create(
            name='Premium Plans',
            description='Premium subscription plans',
            display_order=2,
            is_active=True
        )
        
        expected_str = f"Plan Category {category.id} - {category.name}"
        self.assertEqual(str(category), expected_str)
    
    def test_plan_category_get_category_summary(self):
        """Test PlanCategory get_category_summary method"""
        category = PlanCategory.objects.create(
            name='Premium Plans',
            description='Premium subscription plans',
            display_order=2,
            is_active=True
        )
        
        summary = category.get_category_summary()
        
        self.assertEqual(summary['name'], 'Premium Plans')
        self.assertEqual(summary['description'], 'Premium subscription plans')
        self.assertEqual(summary['display_order'], 2)
        self.assertTrue(summary['is_active'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_plan_feature_creation(self):
        """Test PlanFeature creation"""
        feature = PlanFeature.objects.create(
            name='Premium Support',
            description='24/7 premium support',
            is_active=True
        )
        
        self.assertEqual(feature.name, 'Premium Support')
        self.assertEqual(feature.description, '24/7 premium support')
        self.assertTrue(feature.is_active)
        self.assertIsNotNone(feature.created_at)
        self.assertIsNotNone(feature.updated_at)
    
    def test_plan_feature_str(self):
        """Test PlanFeature string representation"""
        feature = PlanFeature.objects.create(
            name='Premium Support',
            description='24/7 premium support',
            is_active=True
        )
        
        expected_str = f"Plan Feature {feature.id} - {feature.name}"
        self.assertEqual(str(feature), expected_str)
    
    def test_plan_feature_get_feature_summary(self):
        """Test PlanFeature get_feature_summary method"""
        feature = PlanFeature.objects.create(
            name='Premium Support',
            description='24/7 premium support',
            is_active=True
        )
        
        summary = feature.get_feature_summary()
        
        self.assertEqual(summary['name'], 'Premium Support')
        self.assertEqual(summary['description'], '24/7 premium support')
        self.assertTrue(summary['is_active'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_subscription_creation(self):
        """Test Subscription creation"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.plan, plan)
        self.assertEqual(subscription.status, 'active')
        self.assertIsNotNone(subscription.start_date)
        self.assertIsNotNone(subscription.end_date)
        self.assertTrue(subscription.is_active)
        self.assertIsNotNone(subscription.created_at)
        self.assertIsNotNone(subscription.updated_at)
    
    def test_subscription_str(self):
        """Test Subscription string representation"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        expected_str = f"Subscription {subscription.id} - {self.user.username} - {plan.name} ({subscription.status})"
        self.assertEqual(str(subscription), expected_str)
    
    def test_subscription_status_choices(self):
        """Test Subscription status choices"""
        choices = Subscription.STATUS_CHOICES
        
        self.assertIn(('active', 'Active'), choices)
        self.assertIn(('cancelled', 'Cancelled'), choices)
        self.assertIn(('expired', 'Expired'), choices)
        self.assertIn(('suspended', 'Suspended'), choices)
        self.assertIn(('pending', 'Pending'), choices)
    
    def test_subscription_get_subscription_summary(self):
        """Test Subscription get_subscription_summary method"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        summary = subscription.get_subscription_summary()
        
        self.assertEqual(summary['user'], self.user.id)
        self.assertEqual(summary['plan'], plan.id)
        self.assertEqual(summary['status'], 'active')
        self.assertIsNotNone(summary['start_date'])
        self.assertIsNotNone(summary['end_date'])
        self.assertTrue(summary['is_active'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_subscription_is_expired(self):
        """Test Subscription is_expired method"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        # Test active subscription
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        self.assertFalse(subscription.is_expired())
        
        # Test expired subscription
        expired_subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            start_date=timezone.now() - timedelta(days=30),
            end_date=timezone.now() - timedelta(days=1),
            is_active=True
        )
        
        self.assertTrue(expired_subscription.is_expired())
    
    def test_subscription_get_remaining_days(self):
        """Test Subscription get_remaining_days method"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        remaining_days = subscription.get_remaining_days()
        self.assertGreater(remaining_days, 0)
        self.assertLessEqual(remaining_days, 30)
    
    def test_subscription_can_renew(self):
        """Test Subscription can_renew method"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        # Test active subscription
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        self.assertTrue(subscription.can_renew())
        
        # Test cancelled subscription
        cancelled_subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='cancelled',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=False
        )
        
        self.assertFalse(cancelled_subscription.can_renew())
    
    def test_subscription_renew(self):
        """Test Subscription renew method"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        original_end_date = subscription.end_date
        subscription.renew(30)  # Renew for 30 days
        
        self.assertEqual(subscription.status, 'active')
        self.assertTrue(subscription.is_active)
        self.assertGreater(subscription.end_date, original_end_date)
    
    def test_subscription_cancel(self):
        """Test Subscription cancel method"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        subscription.cancel('Customer requested cancellation')
        
        self.assertEqual(subscription.status, 'cancelled')
        self.assertFalse(subscription.is_active)
        self.assertEqual(subscription.cancellation_reason, 'Customer requested cancellation')
    
    def test_subscription_suspend(self):
        """Test Subscription suspend method"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        subscription.suspend('Payment failed')
        
        self.assertEqual(subscription.status, 'suspended')
        self.assertFalse(subscription.is_active)
        self.assertEqual(subscription.suspension_reason, 'Payment failed')
    
    def test_subscription_activate(self):
        """Test Subscription activate method"""
        plan = Plan.objects.create(
            name='Basic Plan',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            duration_days=30,
            max_downloads=100,
            is_active=True,
            category=self.plan_category
        )
        
        subscription = Subscription.objects.create(
            user=self.user,
            plan=plan,
            status='suspended',
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_active=False
        )
        
        subscription.activate()
        
        self.assertEqual(subscription.status, 'active')
        self.assertTrue(subscription.is_active)
        self.assertIsNone(subscription.suspension_reason)