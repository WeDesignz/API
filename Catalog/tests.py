"""
Comprehensive tests for Catalog app
Tests product management, categories, tags, and catalog operations
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

from .models import Product, Category, Tags, CollectionBundle, ProductImage, ProductFile
from common.relations import attach_relation


class CatalogAPITestCase(APITestCase):
    """Test cases for Catalog API endpoints"""
    
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
        
        # Create category
        self.category = Category.objects.create(
            name='Logo Design',
            slug='logo-design',
            description='Professional logo design templates',
            is_active=True,
            display_order=1
        )
        
        # Create tag
        self.tag = Tags.objects.create(
            name='Modern',
            slug='modern',
            description='Modern design style',
            color='#007bff',
            is_active=True
        )
        
        # Create product
        self.product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            category=self.category,
            status='active',
            visibility_status='show',
            is_featured=True,
            is_trending=False,
            download_count=0,
            view_count=0,
            rating=0.0,
            total_ratings=0,
            created_by=self.designer
        )
        attach_relation('Product:Tags', self.product, self.tag)
        
        # Create product image
        self.product_image = ProductImage.objects.create(
            image_url='https://example.com/image1.jpg',
            alt_text='Modern Logo Template Preview',
            is_primary=True,
            display_order=1
        )
        attach_relation('ProductImage:Product', self.product_image, self.product)
        
        # Create product file
        self.product_file = ProductFile.objects.create(
            file_url='https://example.com/logo_template.ai',
            file_name='logo_template.ai',
            file_size=1024000,
            file_type='ai',
            download_count=0
        )
        attach_relation('ProductFile:Product', self.product_file, self.product)
        
        # Create collection bundle
        self.collection_bundle = CollectionBundle.objects.create(
            title='Logo Design Bundle',
            description='A collection of professional logo designs',
            price=Decimal('99.99'),
            discount_percentage=20.0,
            is_active=True,
            is_featured=True,
            created_by=self.designer
        )
        attach_relation('CollectionBundle:Product', self.collection_bundle, self.product)
    
    def test_product_list_success(self):
        """Test successful product list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('product_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_product_list_with_filters(self):
        """Test product list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('product_list')
        params = {
            'category': self.category.id,
            'status': 'active',
            'visibility_status': 'show',
            'is_featured': 'true',
            'is_trending': 'false',
            'min_price': '10.00',
            'max_price': '100.00',
            'search': 'logo',
            'tags': self.tag.id
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_product_detail_success(self):
        """Test successful product detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('product_detail', kwargs={'product_id': self.product.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('title', response.data)
        self.assertIn('description', response.data)
        self.assertIn('price', response.data)
        self.assertIn('category', response.data)
        self.assertIn('status', response.data)
        self.assertIn('visibility_status', response.data)
        self.assertIn('is_featured', response.data)
        self.assertIn('is_trending', response.data)
        self.assertIn('download_count', response.data)
        self.assertIn('view_count', response.data)
        self.assertIn('rating', response.data)
        self.assertIn('created_at', response.data)
    
    def test_product_detail_not_found(self):
        """Test product detail with non-existent product"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('product_detail', kwargs={'product_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_product_create_success(self):
        """Test successful product creation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('product_create')
        data = {
            'title': 'Creative Logo Template',
            'description': 'A creative and unique logo template',
            'price': '39.99',
            'category': self.category.id,
            'status': 'active',
            'visibility_status': 'show',
            'is_featured': False,
            'is_trending': False,
            'tags': [self.tag.id]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('product', response.data)
    
    def test_product_create_unauthorized(self):
        """Test product creation without authentication"""
        url = reverse('product_create')
        data = {
            'title': 'Creative Logo Template',
            'description': 'A creative and unique logo template',
            'price': '39.99',
            'category': self.category.id,
            'status': 'active',
            'visibility_status': 'show'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_product_update_success(self):
        """Test successful product update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('product_update', kwargs={'product_id': self.product.id})
        data = {
            'title': 'Updated Modern Logo Template',
            'description': 'An updated modern and professional logo template',
            'price': '34.99',
            'status': 'active',
            'visibility_status': 'show',
            'is_featured': True,
            'is_trending': True
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('product', response.data)
    
    def test_product_update_unauthorized(self):
        """Test product update without authentication"""
        url = reverse('product_update', kwargs={'product_id': self.product.id})
        data = {
            'title': 'Updated Modern Logo Template',
            'description': 'An updated modern and professional logo template'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_product_delete_success(self):
        """Test successful product deletion"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('product_delete', kwargs={'product_id': self.product.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_product_delete_unauthorized(self):
        """Test product deletion without authentication"""
        url = reverse('product_delete', kwargs={'product_id': self.product.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_product_feature_success(self):
        """Test successful product featuring"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('product_feature', kwargs={'product_id': self.product.id})
        data = {
            'is_featured': True,
            'admin_notes': 'Product featured by admin'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify product was featured
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_featured)
    
    def test_product_feature_unauthorized(self):
        """Test product featuring without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('product_feature', kwargs={'product_id': self.product.id})
        data = {
            'is_featured': True,
            'admin_notes': 'Product featured by admin'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_product_trending_success(self):
        """Test successful product trending"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('product_trending', kwargs={'product_id': self.product.id})
        data = {
            'is_trending': True,
            'admin_notes': 'Product marked as trending by admin'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify product was marked as trending
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_trending)
    
    def test_product_trending_unauthorized(self):
        """Test product trending without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('product_trending', kwargs={'product_id': self.product.id})
        data = {
            'is_trending': True,
            'admin_notes': 'Product marked as trending by admin'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_product_approve_success(self):
        """Test successful product approval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('product_approve', kwargs={'product_id': self.product.id})
        data = {
            'status': 'approved',
            'admin_notes': 'Product approved by admin'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify product was approved
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'approved')
    
    def test_product_approve_unauthorized(self):
        """Test product approval without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('product_approve', kwargs={'product_id': self.product.id})
        data = {
            'status': 'approved',
            'admin_notes': 'Product approved by admin'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_product_reject_success(self):
        """Test successful product rejection"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('product_reject', kwargs={'product_id': self.product.id})
        data = {
            'status': 'rejected',
            'rejection_reason': 'Product does not meet quality standards',
            'admin_notes': 'Product rejected by admin'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify product was rejected
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, 'rejected')
        self.assertEqual(self.product.rejection_reason, 'Product does not meet quality standards')
    
    def test_product_reject_unauthorized(self):
        """Test product rejection without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('product_reject', kwargs={'product_id': self.product.id})
        data = {
            'status': 'rejected',
            'rejection_reason': 'Product does not meet quality standards',
            'admin_notes': 'Product rejected by admin'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_product_analytics_success(self):
        """Test successful product analytics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('product_analytics')
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'group_by': 'day'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_products', response.data)
        self.assertIn('active_products', response.data)
        self.assertIn('featured_products', response.data)
        self.assertIn('trending_products', response.data)
        self.assertIn('total_downloads', response.data)
        self.assertIn('total_views', response.data)
        self.assertIn('average_rating', response.data)
        self.assertIn('daily_breakdown', response.data)
    
    def test_product_analytics_unauthorized(self):
        """Test product analytics without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('product_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_category_list_success(self):
        """Test successful category list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('category_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_category_list_with_filters(self):
        """Test category list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('category_list')
        params = {
            'is_active': 'true',
            'search': 'logo'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_category_detail_success(self):
        """Test successful category detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('category_detail', kwargs={'category_id': self.category.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('name', response.data)
        self.assertIn('slug', response.data)
        self.assertIn('description', response.data)
        self.assertIn('is_active', response.data)
        self.assertIn('display_order', response.data)
        self.assertIn('created_at', response.data)
    
    def test_category_detail_not_found(self):
        """Test category detail with non-existent category"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('category_detail', kwargs={'category_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_category_create_success(self):
        """Test successful category creation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('category_create')
        data = {
            'name': 'Web Design',
            'slug': 'web-design',
            'description': 'Professional web design templates',
            'is_active': True,
            'display_order': 2
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('category', response.data)
    
    def test_category_create_unauthorized(self):
        """Test category creation without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('category_create')
        data = {
            'name': 'Web Design',
            'slug': 'web-design',
            'description': 'Professional web design templates',
            'is_active': True,
            'display_order': 2
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_category_update_success(self):
        """Test successful category update"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('category_update', kwargs={'category_id': self.category.id})
        data = {
            'name': 'Updated Logo Design',
            'slug': 'updated-logo-design',
            'description': 'Updated professional logo design templates',
            'is_active': True,
            'display_order': 1
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('category', response.data)
    
    def test_category_update_unauthorized(self):
        """Test category update without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('category_update', kwargs={'category_id': self.category.id})
        data = {
            'name': 'Updated Logo Design',
            'slug': 'updated-logo-design',
            'description': 'Updated professional logo design templates'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_category_delete_success(self):
        """Test successful category deletion"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('category_delete', kwargs={'category_id': self.category.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_category_delete_unauthorized(self):
        """Test category deletion without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('category_delete', kwargs={'category_id': self.category.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_tags_list_success(self):
        """Test successful tags list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('tags_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_tags_list_with_filters(self):
        """Test tags list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('tags_list')
        params = {
            'is_active': 'true',
            'search': 'modern'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_tags_detail_success(self):
        """Test successful tags detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('tags_detail', kwargs={'tag_id': self.tag.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('name', response.data)
        self.assertIn('slug', response.data)
        self.assertIn('description', response.data)
        self.assertIn('color', response.data)
        self.assertIn('is_active', response.data)
        self.assertIn('created_at', response.data)
    
    def test_tags_detail_not_found(self):
        """Test tags detail with non-existent tag"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('tags_detail', kwargs={'tag_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_tags_create_success(self):
        """Test successful tags creation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('tags_create')
        data = {
            'name': 'Vintage',
            'slug': 'vintage',
            'description': 'Vintage design style',
            'color': '#6c757d',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('tag', response.data)
    
    def test_tags_create_unauthorized(self):
        """Test tags creation without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('tags_create')
        data = {
            'name': 'Vintage',
            'slug': 'vintage',
            'description': 'Vintage design style',
            'color': '#6c757d',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_tags_update_success(self):
        """Test successful tags update"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('tags_update', kwargs={'tag_id': self.tag.id})
        data = {
            'name': 'Updated Modern',
            'slug': 'updated-modern',
            'description': 'Updated modern design style',
            'color': '#28a745',
            'is_active': True
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('tag', response.data)
    
    def test_tags_update_unauthorized(self):
        """Test tags update without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('tags_update', kwargs={'tag_id': self.tag.id})
        data = {
            'name': 'Updated Modern',
            'slug': 'updated-modern',
            'description': 'Updated modern design style'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_tags_delete_success(self):
        """Test successful tags deletion"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('tags_delete', kwargs={'tag_id': self.tag.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_tags_delete_unauthorized(self):
        """Test tags deletion without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('tags_delete', kwargs={'tag_id': self.tag.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_collection_bundle_list_success(self):
        """Test successful collection bundle list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('collection_bundle_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_collection_bundle_list_with_filters(self):
        """Test collection bundle list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('collection_bundle_list')
        params = {
            'is_active': 'true',
            'is_featured': 'true',
            'min_price': '50.00',
            'max_price': '200.00',
            'search': 'logo'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_collection_bundle_detail_success(self):
        """Test successful collection bundle detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('collection_bundle_detail', kwargs={'bundle_id': self.collection_bundle.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('title', response.data)
        self.assertIn('description', response.data)
        self.assertIn('price', response.data)
        self.assertIn('discount_percentage', response.data)
        self.assertIn('is_active', response.data)
        self.assertIn('is_featured', response.data)
        self.assertIn('created_at', response.data)
    
    def test_collection_bundle_detail_not_found(self):
        """Test collection bundle detail with non-existent bundle"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('collection_bundle_detail', kwargs={'bundle_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_collection_bundle_create_success(self):
        """Test successful collection bundle creation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('collection_bundle_create')
        data = {
            'title': 'Web Design Bundle',
            'description': 'A collection of professional web designs',
            'price': '149.99',
            'discount_percentage': 25.0,
            'is_active': True,
            'is_featured': False,
            'products': [self.product.id]
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('bundle', response.data)
    
    def test_collection_bundle_create_unauthorized(self):
        """Test collection bundle creation without authentication"""
        url = reverse('collection_bundle_create')
        data = {
            'title': 'Web Design Bundle',
            'description': 'A collection of professional web designs',
            'price': '149.99',
            'discount_percentage': 25.0,
            'is_active': True,
            'is_featured': False
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_collection_bundle_update_success(self):
        """Test successful collection bundle update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('collection_bundle_update', kwargs={'bundle_id': self.collection_bundle.id})
        data = {
            'title': 'Updated Logo Design Bundle',
            'description': 'An updated collection of professional logo designs',
            'price': '119.99',
            'discount_percentage': 30.0,
            'is_active': True,
            'is_featured': True
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('bundle', response.data)
    
    def test_collection_bundle_update_unauthorized(self):
        """Test collection bundle update without authentication"""
        url = reverse('collection_bundle_update', kwargs={'bundle_id': self.collection_bundle.id})
        data = {
            'title': 'Updated Logo Design Bundle',
            'description': 'An updated collection of professional logo designs'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_collection_bundle_delete_success(self):
        """Test successful collection bundle deletion"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('collection_bundle_delete', kwargs={'bundle_id': self.collection_bundle.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_collection_bundle_delete_unauthorized(self):
        """Test collection bundle deletion without authentication"""
        url = reverse('collection_bundle_delete', kwargs={'bundle_id': self.collection_bundle.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('product_create')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('product_create')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_long_description(self):
        """Test edge case with very long description"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('product_create')
        data = {
            'title': 'Test Product',
            'description': 'A' * 10000,  # Very long description
            'price': '29.99',
            'category': self.category.id,
            'status': 'active',
            'visibility_status': 'show'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_special_characters_in_title(self):
        """Test edge case with special characters in title"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('product_create')
        data = {
            'title': 'Amazing Logo Template! 🎨 #creative',
            'description': 'A creative logo template',
            'price': '29.99',
            'category': self.category.id,
            'status': 'active',
            'visibility_status': 'show'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_unicode_in_description(self):
        """Test edge case with unicode characters in description"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('product_create')
        data = {
            'title': 'Unicode Logo Template',
            'description': 'Una plantilla de logo creativa ✅',
            'price': '29.99',
            'category': self.category.id,
            'status': 'active',
            'visibility_status': 'show'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class CatalogModelTestCase(TestCase):
    """Test cases for Catalog models"""
    
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
    
    def test_product_creation(self):
        """Test Product creation"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            is_featured=True,
            is_trending=False,
            download_count=0,
            view_count=0,
            rating=0.0,
            total_ratings=0,
            created_by=self.designer
        )
        
        self.assertEqual(product.title, 'Modern Logo Template')
        self.assertEqual(product.description, 'A modern and professional logo template')
        self.assertEqual(product.price, Decimal('29.99'))
        self.assertEqual(product.status, 'active')
        self.assertEqual(product.visibility_status, 'show')
        self.assertTrue(product.is_featured)
        self.assertFalse(product.is_trending)
        self.assertEqual(product.download_count, 0)
        self.assertEqual(product.view_count, 0)
        self.assertEqual(product.rating, 0.0)
        self.assertEqual(product.total_ratings, 0)
        self.assertEqual(product.created_by, self.designer)
        self.assertIsNotNone(product.created_at)
        self.assertIsNotNone(product.updated_at)
    
    def test_product_str(self):
        """Test Product string representation"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            is_featured=True,
            is_trending=False,
            download_count=0,
            view_count=0,
            rating=0.0,
            total_ratings=0,
            created_by=self.designer
        )
        
        expected_str = f"Product {product.id} - {product.title}"
        self.assertEqual(str(product), expected_str)
    
    def test_product_status_choices(self):
        """Test Product status choices"""
        choices = Product.STATUS_CHOICES
        
        self.assertIn(('draft', 'Draft'), choices)
        self.assertIn(('pending', 'Pending'), choices)
        self.assertIn(('approved', 'Approved'), choices)
        self.assertIn(('rejected', 'Rejected'), choices)
        self.assertIn(('active', 'Active'), choices)
        self.assertIn(('inactive', 'Inactive'), choices)
    
    def test_product_visibility_status_choices(self):
        """Test Product visibility status choices"""
        choices = Product.VISIBILITY_STATUS_CHOICES
        
        self.assertIn(('show', 'Show'), choices)
        self.assertIn(('hide', 'Hide'), choices)
        self.assertIn(('featured', 'Featured'), choices)
        self.assertIn(('trending', 'Trending'), choices)
    
    def test_product_increment_download_count(self):
        """Test Product increment_download_count method"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            download_count=0,
            created_by=self.designer
        )
        
        product.increment_download_count()
        
        self.assertEqual(product.download_count, 1)
    
    def test_product_increment_view_count(self):
        """Test Product increment_view_count method"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            view_count=0,
            created_by=self.designer
        )
        
        product.increment_view_count()
        
        self.assertEqual(product.view_count, 1)
    
    def test_product_update_rating(self):
        """Test Product update_rating method"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            rating=0.0,
            total_ratings=0,
            created_by=self.designer
        )
        
        product.update_rating(4.5)
        
        self.assertEqual(product.rating, 4.5)
        self.assertEqual(product.total_ratings, 1)
    
    def test_product_get_price_display(self):
        """Test Product get_price_display method"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            created_by=self.designer
        )
        
        price_display = product.get_price_display()
        self.assertEqual(price_display, '₹29.99')
    
    def test_product_get_rating_display(self):
        """Test Product get_rating_display method"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            rating=4.5,
            total_ratings=10,
            created_by=self.designer
        )
        
        rating_display = product.get_rating_display()
        self.assertEqual(rating_display, '4.5 (10 ratings)')
    
    def test_product_get_product_summary(self):
        """Test Product get_product_summary method"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            is_featured=True,
            is_trending=False,
            download_count=100,
            view_count=500,
            rating=4.5,
            total_ratings=10,
            created_by=self.designer
        )
        
        summary = product.get_product_summary()
        
        self.assertEqual(summary['title'], 'Modern Logo Template')
        self.assertEqual(summary['description'], 'A modern and professional logo template')
        self.assertEqual(summary['price'], Decimal('29.99'))
        self.assertEqual(summary['status'], 'active')
        self.assertEqual(summary['visibility_status'], 'show')
        self.assertTrue(summary['is_featured'])
        self.assertFalse(summary['is_trending'])
        self.assertEqual(summary['download_count'], 100)
        self.assertEqual(summary['view_count'], 500)
        self.assertEqual(summary['rating'], 4.5)
        self.assertEqual(summary['total_ratings'], 10)
        self.assertIsNotNone(summary['created_at'])
    
    def test_category_creation(self):
        """Test Category creation"""
        category = Category.objects.create(
            name='Logo Design',
            slug='logo-design',
            description='Professional logo design templates',
            is_active=True,
            display_order=1
        )
        
        self.assertEqual(category.name, 'Logo Design')
        self.assertEqual(category.slug, 'logo-design')
        self.assertEqual(category.description, 'Professional logo design templates')
        self.assertTrue(category.is_active)
        self.assertEqual(category.display_order, 1)
        self.assertIsNotNone(category.created_at)
        self.assertIsNotNone(category.updated_at)
    
    def test_category_str(self):
        """Test Category string representation"""
        category = Category.objects.create(
            name='Logo Design',
            slug='logo-design',
            description='Professional logo design templates',
            is_active=True,
            display_order=1
        )
        
        expected_str = f"Category {category.id} - {category.name}"
        self.assertEqual(str(category), expected_str)
    
    def test_category_activate_category(self):
        """Test Category activate_category method"""
        category = Category.objects.create(
            name='Logo Design',
            slug='logo-design',
            description='Professional logo design templates',
            is_active=False,
            display_order=1
        )
        
        category.activate_category(
            activated_by_id=self.user.id,
            admin_notes='Category activated by admin'
        )
        
        self.assertTrue(category.is_active)
        self.assertEqual(category.activated_by_id, self.user.id)
        self.assertEqual(category.admin_notes, 'Category activated by admin')
        self.assertIsNotNone(category.activated_at)
    
    def test_category_deactivate_category(self):
        """Test Category deactivate_category method"""
        category = Category.objects.create(
            name='Logo Design',
            slug='logo-design',
            description='Professional logo design templates',
            is_active=True,
            display_order=1
        )
        
        category.deactivate_category(
            deactivated_by_id=self.user.id,
            admin_notes='Category deactivated by admin'
        )
        
        self.assertFalse(category.is_active)
        self.assertEqual(category.deactivated_by_id, self.user.id)
        self.assertEqual(category.admin_notes, 'Category deactivated by admin')
        self.assertIsNotNone(category.deactivated_at)
    
    def test_category_get_category_summary(self):
        """Test Category get_category_summary method"""
        category = Category.objects.create(
            name='Logo Design',
            slug='logo-design',
            description='Professional logo design templates',
            is_active=True,
            display_order=1
        )
        
        summary = category.get_category_summary()
        
        self.assertEqual(summary['name'], 'Logo Design')
        self.assertEqual(summary['slug'], 'logo-design')
        self.assertEqual(summary['description'], 'Professional logo design templates')
        self.assertTrue(summary['is_active'])
        self.assertEqual(summary['display_order'], 1)
        self.assertIsNotNone(summary['created_at'])
    
    def test_tags_creation(self):
        """Test Tags creation"""
        tag = Tags.objects.create(
            name='Modern',
            slug='modern',
            description='Modern design style',
            color='#007bff',
            is_active=True
        )
        
        self.assertEqual(tag.name, 'Modern')
        self.assertEqual(tag.slug, 'modern')
        self.assertEqual(tag.description, 'Modern design style')
        self.assertEqual(tag.color, '#007bff')
        self.assertTrue(tag.is_active)
        self.assertIsNotNone(tag.created_at)
        self.assertIsNotNone(tag.updated_at)
    
    def test_tags_str(self):
        """Test Tags string representation"""
        tag = Tags.objects.create(
            name='Modern',
            slug='modern',
            description='Modern design style',
            color='#007bff',
            is_active=True
        )
        
        expected_str = f"Tag {tag.id} - {tag.name}"
        self.assertEqual(str(tag), expected_str)
    
    def test_tags_activate_tag(self):
        """Test Tags activate_tag method"""
        tag = Tags.objects.create(
            name='Modern',
            slug='modern',
            description='Modern design style',
            color='#007bff',
            is_active=False
        )
        
        tag.activate_tag(
            activated_by_id=self.user.id,
            admin_notes='Tag activated by admin'
        )
        
        self.assertTrue(tag.is_active)
        self.assertEqual(tag.activated_by_id, self.user.id)
        self.assertEqual(tag.admin_notes, 'Tag activated by admin')
        self.assertIsNotNone(tag.activated_at)
    
    def test_tags_deactivate_tag(self):
        """Test Tags deactivate_tag method"""
        tag = Tags.objects.create(
            name='Modern',
            slug='modern',
            description='Modern design style',
            color='#007bff',
            is_active=True
        )
        
        tag.deactivate_tag(
            deactivated_by_id=self.user.id,
            admin_notes='Tag deactivated by admin'
        )
        
        self.assertFalse(tag.is_active)
        self.assertEqual(tag.deactivated_by_id, self.user.id)
        self.assertEqual(tag.admin_notes, 'Tag deactivated by admin')
        self.assertIsNotNone(tag.deactivated_at)
    
    def test_tags_get_tag_summary(self):
        """Test Tags get_tag_summary method"""
        tag = Tags.objects.create(
            name='Modern',
            slug='modern',
            description='Modern design style',
            color='#007bff',
            is_active=True
        )
        
        summary = tag.get_tag_summary()
        
        self.assertEqual(summary['name'], 'Modern')
        self.assertEqual(summary['slug'], 'modern')
        self.assertEqual(summary['description'], 'Modern design style')
        self.assertEqual(summary['color'], '#007bff')
        self.assertTrue(summary['is_active'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_collection_bundle_creation(self):
        """Test CollectionBundle creation"""
        bundle = CollectionBundle.objects.create(
            title='Logo Design Bundle',
            description='A collection of professional logo designs',
            price=Decimal('99.99'),
            discount_percentage=20.0,
            is_active=True,
            is_featured=True,
            created_by=self.designer
        )
        
        self.assertEqual(bundle.title, 'Logo Design Bundle')
        self.assertEqual(bundle.description, 'A collection of professional logo designs')
        self.assertEqual(bundle.price, Decimal('99.99'))
        self.assertEqual(bundle.discount_percentage, 20.0)
        self.assertTrue(bundle.is_active)
        self.assertTrue(bundle.is_featured)
        self.assertEqual(bundle.created_by, self.designer)
        self.assertIsNotNone(bundle.created_at)
        self.assertIsNotNone(bundle.updated_at)
    
    def test_collection_bundle_str(self):
        """Test CollectionBundle string representation"""
        bundle = CollectionBundle.objects.create(
            title='Logo Design Bundle',
            description='A collection of professional logo designs',
            price=Decimal('99.99'),
            discount_percentage=20.0,
            is_active=True,
            is_featured=True,
            created_by=self.designer
        )
        
        expected_str = f"Collection Bundle {bundle.id} - {bundle.title}"
        self.assertEqual(str(bundle), expected_str)
    
    def test_collection_bundle_get_discounted_price(self):
        """Test CollectionBundle get_discounted_price method"""
        bundle = CollectionBundle.objects.create(
            title='Logo Design Bundle',
            description='A collection of professional logo designs',
            price=Decimal('99.99'),
            discount_percentage=20.0,
            is_active=True,
            is_featured=True,
            created_by=self.designer
        )
        
        discounted_price = bundle.get_discounted_price()
        self.assertEqual(discounted_price, Decimal('79.99'))
    
    def test_collection_bundle_get_discount_amount(self):
        """Test CollectionBundle get_discount_amount method"""
        bundle = CollectionBundle.objects.create(
            title='Logo Design Bundle',
            description='A collection of professional logo designs',
            price=Decimal('99.99'),
            discount_percentage=20.0,
            is_active=True,
            is_featured=True,
            created_by=self.designer
        )
        
        discount_amount = bundle.get_discount_amount()
        self.assertEqual(discount_amount, Decimal('20.00'))
    
    def test_collection_bundle_get_bundle_summary(self):
        """Test CollectionBundle get_bundle_summary method"""
        bundle = CollectionBundle.objects.create(
            title='Logo Design Bundle',
            description='A collection of professional logo designs',
            price=Decimal('99.99'),
            discount_percentage=20.0,
            is_active=True,
            is_featured=True,
            created_by=self.designer
        )
        
        summary = bundle.get_bundle_summary()
        
        self.assertEqual(summary['title'], 'Logo Design Bundle')
        self.assertEqual(summary['description'], 'A collection of professional logo designs')
        self.assertEqual(summary['price'], Decimal('99.99'))
        self.assertEqual(summary['discount_percentage'], 20.0)
        self.assertTrue(summary['is_active'])
        self.assertTrue(summary['is_featured'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_product_image_creation(self):
        """Test ProductImage creation"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            created_by=self.designer
        )
        
        image = ProductImage.objects.create(
            product=product,
            image_url='https://example.com/image1.jpg',
            alt_text='Modern Logo Template Preview',
            is_primary=True,
            display_order=1
        )
        
        self.assertEqual(image.product, product)
        self.assertEqual(image.image_url, 'https://example.com/image1.jpg')
        self.assertEqual(image.alt_text, 'Modern Logo Template Preview')
        self.assertTrue(image.is_primary)
        self.assertEqual(image.display_order, 1)
        self.assertIsNotNone(image.created_at)
        self.assertIsNotNone(image.updated_at)
    
    def test_product_image_str(self):
        """Test ProductImage string representation"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            created_by=self.designer
        )
        
        image = ProductImage.objects.create(
            product=product,
            image_url='https://example.com/image1.jpg',
            alt_text='Modern Logo Template Preview',
            is_primary=True,
            display_order=1
        )
        
        expected_str = f"Product Image {image.id} - {image.alt_text}"
        self.assertEqual(str(image), expected_str)
    
    def test_product_file_creation(self):
        """Test ProductFile creation"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            created_by=self.designer
        )
        
        file = ProductFile.objects.create(
            product=product,
            file_url='https://example.com/logo_template.ai',
            file_name='logo_template.ai',
            file_size=1024000,
            file_type='ai',
            download_count=0
        )
        
        self.assertEqual(file.product, product)
        self.assertEqual(file.file_url, 'https://example.com/logo_template.ai')
        self.assertEqual(file.file_name, 'logo_template.ai')
        self.assertEqual(file.file_size, 1024000)
        self.assertEqual(file.file_type, 'ai')
        self.assertEqual(file.download_count, 0)
        self.assertIsNotNone(file.created_at)
        self.assertIsNotNone(file.updated_at)
    
    def test_product_file_str(self):
        """Test ProductFile string representation"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            created_by=self.designer
        )
        
        file = ProductFile.objects.create(
            product=product,
            file_url='https://example.com/logo_template.ai',
            file_name='logo_template.ai',
            file_size=1024000,
            file_type='ai',
            download_count=0
        )
        
        expected_str = f"Product File {file.id} - {file.file_name}"
        self.assertEqual(str(file), expected_str)
    
    def test_product_file_increment_download_count(self):
        """Test ProductFile increment_download_count method"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            created_by=self.designer
        )
        
        file = ProductFile.objects.create(
            product=product,
            file_url='https://example.com/logo_template.ai',
            file_name='logo_template.ai',
            file_size=1024000,
            file_type='ai',
            download_count=0
        )
        
        file.increment_download_count()
        
        self.assertEqual(file.download_count, 1)
    
    def test_product_file_get_file_size_display(self):
        """Test ProductFile get_file_size_display method"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            created_by=self.designer
        )
        
        file = ProductFile.objects.create(
            product=product,
            file_url='https://example.com/logo_template.ai',
            file_name='logo_template.ai',
            file_size=1024000,
            file_type='ai',
            download_count=0
        )
        
        size_display = file.get_file_size_display()
        self.assertEqual(size_display, '1.0 MB')
    
    def test_product_file_get_file_extension(self):
        """Test ProductFile get_file_extension method"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            created_by=self.designer
        )
        
        file = ProductFile.objects.create(
            product=product,
            file_url='https://example.com/logo_template.ai',
            file_name='logo_template.ai',
            file_size=1024000,
            file_type='ai',
            download_count=0
        )
        
        extension = file.get_file_extension()
        self.assertEqual(extension, '.ai')
    
    def test_product_file_get_file_summary(self):
        """Test ProductFile get_file_summary method"""
        product = Product.objects.create(
            title='Modern Logo Template',
            description='A modern and professional logo template',
            price=Decimal('29.99'),
            status='active',
            visibility_status='show',
            created_by=self.designer
        )
        
        file = ProductFile.objects.create(
            product=product,
            file_url='https://example.com/logo_template.ai',
            file_name='logo_template.ai',
            file_size=1024000,
            file_type='ai',
            download_count=0
        )
        
        summary = file.get_file_summary()
        
        self.assertEqual(summary['file_url'], 'https://example.com/logo_template.ai')
        self.assertEqual(summary['file_name'], 'logo_template.ai')
        self.assertEqual(summary['file_size'], 1024000)
        self.assertEqual(summary['file_type'], 'ai')
        self.assertEqual(summary['download_count'], 0)
        self.assertIsNotNone(summary['created_at'])