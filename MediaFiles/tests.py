"""
Comprehensive tests for MediaFiles app
Tests media file management, relations, and file operations
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

from .models import Media, Relation


class MediaFilesAPITestCase(APITestCase):
    """Test cases for MediaFiles API endpoints"""
    
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
        
        # Create media file
        self.media_file = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        # Create relation
        self.relation = Relation.objects.create(
            source_type='User',
            source_id=self.user.id,
            target_type='Media',
            target_id=self.media_file.id,
            relation_type='User:Media',
            metadata={'purpose': 'profile_picture'}
        )
    
    def test_media_list_success(self):
        """Test successful media list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_media_list_with_filters(self):
        """Test media list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_list')
        params = {
            'file_type': 'image',
            'mime_type': 'image/jpeg',
            'min_size': '1000000',
            'max_size': '2000000',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'search': 'test'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_media_list_unauthorized(self):
        """Test media list without authentication"""
        url = reverse('media_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_media_detail_success(self):
        """Test successful media detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_detail', kwargs={'media_id': self.media_file.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('file_name', response.data)
        self.assertIn('file_url', response.data)
        self.assertIn('file_type', response.data)
        self.assertIn('file_size', response.data)
        self.assertIn('mime_type', response.data)
        self.assertIn('uploaded_by', response.data)
        self.assertIn('created_at', response.data)
    
    def test_media_detail_not_found(self):
        """Test media detail with non-existent media"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_detail', kwargs={'media_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_media_upload_success(self):
        """Test successful media upload"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_upload')
        data = {
            'file_name': 'new_image.jpg',
            'file_url': 'https://example.com/new_image.jpg',
            'file_type': 'image',
            'file_size': 2048000,
            'mime_type': 'image/jpeg',
            'metadata': {'description': 'New image file'}
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('media', response.data)
    
    def test_media_upload_unauthorized(self):
        """Test media upload without authentication"""
        url = reverse('media_upload')
        data = {
            'file_name': 'new_image.jpg',
            'file_url': 'https://example.com/new_image.jpg',
            'file_type': 'image',
            'file_size': 2048000,
            'mime_type': 'image/jpeg'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_media_update_success(self):
        """Test successful media update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_update', kwargs={'media_id': self.media_file.id})
        data = {
            'file_name': 'updated_image.jpg',
            'metadata': {'description': 'Updated image file'}
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('media', response.data)
    
    def test_media_update_unauthorized(self):
        """Test media update without authentication"""
        url = reverse('media_update', kwargs={'media_id': self.media_file.id})
        data = {
            'file_name': 'updated_image.jpg',
            'metadata': {'description': 'Updated image file'}
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_media_delete_success(self):
        """Test successful media deletion"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_delete', kwargs={'media_id': self.media_file.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_media_delete_unauthorized(self):
        """Test media deletion without authentication"""
        url = reverse('media_delete', kwargs={'media_id': self.media_file.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_media_download_success(self):
        """Test successful media download"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_download', kwargs={'media_id': self.media_file.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('download_url', response.data)
        self.assertIn('expires_at', response.data)
    
    def test_media_download_unauthorized(self):
        """Test media download without authentication"""
        url = reverse('media_download', kwargs={'media_id': self.media_file.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_media_relations_success(self):
        """Test successful media relations retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_relations', kwargs={'media_id': self.media_file.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('relations', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['relations']), 0)
    
    def test_media_relations_unauthorized(self):
        """Test media relations without authentication"""
        url = reverse('media_relations', kwargs={'media_id': self.media_file.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_media_attach_relation_success(self):
        """Test successful media relation attachment"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_attach_relation', kwargs={'media_id': self.media_file.id})
        data = {
            'target_type': 'User',
            'target_id': self.designer.id,
            'relation_type': 'User:Media',
            'metadata': {'purpose': 'design_attachment'}
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('relation', response.data)
    
    def test_media_attach_relation_unauthorized(self):
        """Test media relation attachment without authentication"""
        url = reverse('media_attach_relation', kwargs={'media_id': self.media_file.id})
        data = {
            'target_type': 'User',
            'target_id': self.designer.id,
            'relation_type': 'User:Media',
            'metadata': {'purpose': 'design_attachment'}
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_media_detach_relation_success(self):
        """Test successful media relation detachment"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_detach_relation', kwargs={'relation_id': self.relation.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_media_detach_relation_unauthorized(self):
        """Test media relation detachment without authentication"""
        url = reverse('media_detach_relation', kwargs={'relation_id': self.relation.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_relation_list_success(self):
        """Test successful relation list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('relation_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_relation_list_with_filters(self):
        """Test relation list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('relation_list')
        params = {
            'source_type': 'User',
            'target_type': 'Media',
            'relation_type': 'User:Media',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_relation_list_unauthorized(self):
        """Test relation list without authentication"""
        url = reverse('relation_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_relation_detail_success(self):
        """Test successful relation detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('relation_detail', kwargs={'relation_id': self.relation.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('source_type', response.data)
        self.assertIn('source_id', response.data)
        self.assertIn('target_type', response.data)
        self.assertIn('target_id', response.data)
        self.assertIn('relation_type', response.data)
        self.assertIn('metadata', response.data)
        self.assertIn('created_at', response.data)
    
    def test_relation_detail_not_found(self):
        """Test relation detail with non-existent relation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('relation_detail', kwargs={'relation_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_relation_create_success(self):
        """Test successful relation creation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('relation_create')
        data = {
            'source_type': 'User',
            'source_id': self.designer.id,
            'target_type': 'Media',
            'target_id': self.media_file.id,
            'relation_type': 'User:Media',
            'metadata': {'purpose': 'design_attachment'}
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('relation', response.data)
    
    def test_relation_create_unauthorized(self):
        """Test relation creation without authentication"""
        url = reverse('relation_create')
        data = {
            'source_type': 'User',
            'source_id': self.designer.id,
            'target_type': 'Media',
            'target_id': self.media_file.id,
            'relation_type': 'User:Media',
            'metadata': {'purpose': 'design_attachment'}
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_relation_update_success(self):
        """Test successful relation update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('relation_update', kwargs={'relation_id': self.relation.id})
        data = {
            'metadata': {'purpose': 'updated_attachment', 'priority': 'high'}
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('relation', response.data)
    
    def test_relation_update_unauthorized(self):
        """Test relation update without authentication"""
        url = reverse('relation_update', kwargs={'relation_id': self.relation.id})
        data = {
            'metadata': {'purpose': 'updated_attachment', 'priority': 'high'}
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_relation_delete_success(self):
        """Test successful relation deletion"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('relation_delete', kwargs={'relation_id': self.relation.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_relation_delete_unauthorized(self):
        """Test relation deletion without authentication"""
        url = reverse('relation_delete', kwargs={'relation_id': self.relation.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_media_analytics_success(self):
        """Test successful media analytics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('media_analytics')
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'group_by': 'day'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_files', response.data)
        self.assertIn('total_size', response.data)
        self.assertIn('file_type_breakdown', response.data)
        self.assertIn('daily_breakdown', response.data)
    
    def test_media_analytics_unauthorized(self):
        """Test media analytics without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_upload')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_upload')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_large_file(self):
        """Test edge case with very large file"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_upload')
        data = {
            'file_name': 'large_file.jpg',
            'file_url': 'https://example.com/large_file.jpg',
            'file_type': 'image',
            'file_size': 999999999,  # Very large file
            'mime_type': 'image/jpeg'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_special_characters_in_filename(self):
        """Test edge case with special characters in filename"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_upload')
        data = {
            'file_name': 'special_file!@#.jpg',
            'file_url': 'https://example.com/special_file.jpg',
            'file_type': 'image',
            'file_size': 1024000,
            'mime_type': 'image/jpeg'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_unicode_in_filename(self):
        """Test edge case with unicode characters in filename"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('media_upload')
        data = {
            'file_name': 'archivo_con_unicode_✅.jpg',
            'file_url': 'https://example.com/archivo_con_unicode.jpg',
            'file_type': 'image',
            'file_size': 1024000,
            'mime_type': 'image/jpeg'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class MediaFilesModelTestCase(TestCase):
    """Test cases for MediaFiles models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
    
    def test_media_creation(self):
        """Test Media creation"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        self.assertEqual(media.file_name, 'test_image.jpg')
        self.assertEqual(media.file_url, 'https://example.com/test_image.jpg')
        self.assertEqual(media.file_type, 'image')
        self.assertEqual(media.file_size, 1024000)
        self.assertEqual(media.mime_type, 'image/jpeg')
        self.assertEqual(media.uploaded_by, self.user)
        self.assertIsNotNone(media.created_at)
        self.assertIsNotNone(media.updated_at)
    
    def test_media_str(self):
        """Test Media string representation"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        expected_str = f"Media {media.id} - {media.file_name} ({media.file_type})"
        self.assertEqual(str(media), expected_str)
    
    def test_media_file_type_choices(self):
        """Test Media file type choices"""
        choices = Media.FILE_TYPE_CHOICES
        
        self.assertIn(('image', 'Image'), choices)
        self.assertIn(('video', 'Video'), choices)
        self.assertIn(('audio', 'Audio'), choices)
        self.assertIn(('document', 'Document'), choices)
        self.assertIn(('archive', 'Archive'), choices)
        self.assertIn(('other', 'Other'), choices)
    
    def test_media_get_file_size_display(self):
        """Test Media get_file_size_display method"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        size_display = media.get_file_size_display()
        self.assertEqual(size_display, '1.0 MB')
    
    def test_media_get_file_extension(self):
        """Test Media get_file_extension method"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        extension = media.get_file_extension()
        self.assertEqual(extension, '.jpg')
    
    def test_media_get_media_summary(self):
        """Test Media get_media_summary method"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        summary = media.get_media_summary()
        
        self.assertEqual(summary['file_name'], 'test_image.jpg')
        self.assertEqual(summary['file_url'], 'https://example.com/test_image.jpg')
        self.assertEqual(summary['file_type'], 'image')
        self.assertEqual(summary['file_size'], 1024000)
        self.assertEqual(summary['mime_type'], 'image/jpeg')
        self.assertEqual(summary['uploaded_by'], self.user.id)
        self.assertIsNotNone(summary['created_at'])
    
    def test_relation_creation(self):
        """Test Relation creation"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        relation = Relation.objects.create(
            source_type='User',
            source_id=self.user.id,
            target_type='Media',
            target_id=media.id,
            relation_type='User:Media',
            metadata={'purpose': 'profile_picture'}
        )
        
        self.assertEqual(relation.source_type, 'User')
        self.assertEqual(relation.source_id, self.user.id)
        self.assertEqual(relation.target_type, 'Media')
        self.assertEqual(relation.target_id, media.id)
        self.assertEqual(relation.relation_type, 'User:Media')
        self.assertEqual(relation.metadata, {'purpose': 'profile_picture'})
        self.assertIsNotNone(relation.created_at)
        self.assertIsNotNone(relation.updated_at)
    
    def test_relation_str(self):
        """Test Relation string representation"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        relation = Relation.objects.create(
            source_type='User',
            source_id=self.user.id,
            target_type='Media',
            target_id=media.id,
            relation_type='User:Media',
            metadata={'purpose': 'profile_picture'}
        )
        
        expected_str = f"Relation {relation.id} - {relation.relation_type}"
        self.assertEqual(str(relation), expected_str)
    
    def test_relation_relation_type_choices(self):
        """Test Relation relation type choices"""
        choices = Relation.RELATION_TYPE_CHOICES
        
        # Check some key relation types
        self.assertIn(('User:Media', 'User and Media'), choices)
        self.assertIn(('User:Product', 'User and Product'), choices)
        self.assertIn(('User:Order', 'User and Order'), choices)
        self.assertIn(('Product:Media', 'Product and Media'), choices)
    
    def test_relation_get_relation_summary(self):
        """Test Relation get_relation_summary method"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        relation = Relation.objects.create(
            source_type='User',
            source_id=self.user.id,
            target_type='Media',
            target_id=media.id,
            relation_type='User:Media',
            metadata={'purpose': 'profile_picture'}
        )
        
        summary = relation.get_relation_summary()
        
        self.assertEqual(summary['source_type'], 'User')
        self.assertEqual(summary['source_id'], self.user.id)
        self.assertEqual(summary['target_type'], 'Media')
        self.assertEqual(summary['target_id'], media.id)
        self.assertEqual(summary['relation_type'], 'User:Media')
        self.assertEqual(summary['metadata'], {'purpose': 'profile_picture'})
        self.assertIsNotNone(summary['created_at'])
    
    def test_relation_get_source_object(self):
        """Test Relation get_source_object method"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        relation = Relation.objects.create(
            source_type='User',
            source_id=self.user.id,
            target_type='Media',
            target_id=media.id,
            relation_type='User:Media',
            metadata={'purpose': 'profile_picture'}
        )
        
        source_object = relation.get_source_object()
        self.assertEqual(source_object, self.user)
    
    def test_relation_get_target_object(self):
        """Test Relation get_target_object method"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        relation = Relation.objects.create(
            source_type='User',
            source_id=self.user.id,
            target_type='Media',
            target_id=media.id,
            relation_type='User:Media',
            metadata={'purpose': 'profile_picture'}
        )
        
        target_object = relation.get_target_object()
        self.assertEqual(target_object, media)
    
    def test_relation_update_metadata(self):
        """Test Relation update_metadata method"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        relation = Relation.objects.create(
            source_type='User',
            source_id=self.user.id,
            target_type='Media',
            target_id=media.id,
            relation_type='User:Media',
            metadata={'purpose': 'profile_picture'}
        )
        
        relation.update_metadata({'purpose': 'updated_purpose', 'priority': 'high'})
        
        self.assertEqual(relation.metadata, {'purpose': 'updated_purpose', 'priority': 'high'})
    
    def test_relation_is_valid(self):
        """Test Relation is_valid method"""
        media = Media.objects.create(
            file_name='test_image.jpg',
            file_url='https://example.com/test_image.jpg',
            file_type='image',
            file_size=1024000,
            mime_type='image/jpeg',
            uploaded_by=self.user
        )
        
        # Test valid relation
        relation = Relation.objects.create(
            source_type='User',
            source_id=self.user.id,
            target_type='Media',
            target_id=media.id,
            relation_type='User:Media',
            metadata={'purpose': 'profile_picture'}
        )
        
        self.assertTrue(relation.is_valid())
        
        # Test invalid relation (non-existent target)
        invalid_relation = Relation.objects.create(
            source_type='User',
            source_id=self.user.id,
            target_type='Media',
            target_id=99999,  # Non-existent media
            relation_type='User:Media',
            metadata={'purpose': 'profile_picture'}
        )
        
        self.assertFalse(invalid_relation.is_valid())