"""
Comprehensive tests for Feedback app
Tests feedback reviews, issue reports, and feedback management
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

from .models import FeedbackReview, ReportIssue, FeedbackCategory, FeedbackTag


class FeedbackAPITestCase(APITestCase):
    """Test cases for Feedback API endpoints"""
    
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
        
        # Create feedback category
        self.feedback_category = FeedbackCategory.objects.create(
            name='Design Quality',
            description='Feedback related to design quality',
            is_active=True
        )
        
        # Create feedback tag
        self.feedback_tag = FeedbackTag.objects.create(
            name='Excellent',
            description='Excellent quality feedback',
            is_active=True
        )
        
        # Create feedback review
        self.feedback_review = FeedbackReview.objects.create(
            user=self.user,
            title='Great Design',
            content='This design is amazing!',
            rating=5,
            category=self.feedback_category,
            is_public=True
        )
        
        # Add tag to review
        self.feedback_review.tags.add(self.feedback_tag)
        
        # Create issue report
        self.issue_report = ReportIssue.objects.create(
            user=self.user,
            title='Design Issue',
            description='There is an issue with the design',
            issue_type='design_quality',
            priority='medium',
            status='open'
        )
    
    def test_feedback_review_list_success(self):
        """Test successful feedback review list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_feedback_review_list_with_filters(self):
        """Test feedback review list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_list')
        params = {
            'rating': '5',
            'category': self.feedback_category.id,
            'is_public': 'true',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'search': 'great'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_feedback_review_list_unauthorized(self):
        """Test feedback review list without authentication"""
        url = reverse('feedback_review_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_feedback_review_detail_success(self):
        """Test successful feedback review detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_detail', kwargs={'review_id': self.feedback_review.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('user', response.data)
        self.assertIn('title', response.data)
        self.assertIn('content', response.data)
        self.assertIn('rating', response.data)
        self.assertIn('category', response.data)
        self.assertIn('tags', response.data)
        self.assertIn('is_public', response.data)
        self.assertIn('created_at', response.data)
    
    def test_feedback_review_detail_not_found(self):
        """Test feedback review detail with non-existent review"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_detail', kwargs={'review_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_feedback_review_create_success(self):
        """Test successful feedback review creation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_create')
        data = {
            'title': 'Amazing Design',
            'content': 'This design exceeded my expectations!',
            'rating': 5,
            'category': self.feedback_category.id,
            'tags': [self.feedback_tag.id],
            'is_public': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('review', response.data)
    
    def test_feedback_review_create_unauthorized(self):
        """Test feedback review creation without authentication"""
        url = reverse('feedback_review_create')
        data = {
            'title': 'Amazing Design',
            'content': 'This design exceeded my expectations!',
            'rating': 5,
            'category': self.feedback_category.id,
            'tags': [self.feedback_tag.id],
            'is_public': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_feedback_review_update_success(self):
        """Test successful feedback review update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_update', kwargs={'review_id': self.feedback_review.id})
        data = {
            'title': 'Updated Great Design',
            'content': 'This design is even better than I thought!',
            'rating': 5,
            'is_public': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('review', response.data)
    
    def test_feedback_review_update_unauthorized(self):
        """Test feedback review update without authentication"""
        url = reverse('feedback_review_update', kwargs={'review_id': self.feedback_review.id})
        data = {
            'title': 'Updated Great Design',
            'content': 'This design is even better than I thought!',
            'rating': 5,
            'is_public': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_feedback_review_delete_success(self):
        """Test successful feedback review deletion"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_delete', kwargs={'review_id': self.feedback_review.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_feedback_review_delete_unauthorized(self):
        """Test feedback review deletion without authentication"""
        url = reverse('feedback_review_delete', kwargs={'review_id': self.feedback_review.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_feedback_review_like_success(self):
        """Test successful feedback review like"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_like', kwargs={'review_id': self.feedback_review.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('review', response.data)
    
    def test_feedback_review_like_unauthorized(self):
        """Test feedback review like without authentication"""
        url = reverse('feedback_review_like', kwargs={'review_id': self.feedback_review.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_feedback_review_unlike_success(self):
        """Test successful feedback review unlike"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_unlike', kwargs={'review_id': self.feedback_review.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('review', response.data)
    
    def test_feedback_review_unlike_unauthorized(self):
        """Test feedback review unlike without authentication"""
        url = reverse('feedback_review_unlike', kwargs={'review_id': self.feedback_review.id})
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_feedback_review_comment_success(self):
        """Test successful feedback review comment"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_comment', kwargs={'review_id': self.feedback_review.id})
        data = {
            'content': 'I agree with this review!'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('comment', response.data)
    
    def test_feedback_review_comment_unauthorized(self):
        """Test feedback review comment without authentication"""
        url = reverse('feedback_review_comment', kwargs={'review_id': self.feedback_review.id})
        data = {
            'content': 'I agree with this review!'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_issue_report_list_success(self):
        """Test successful issue report list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('issue_report_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_issue_report_list_with_filters(self):
        """Test issue report list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('issue_report_list')
        params = {
            'issue_type': 'design_quality',
            'priority': 'medium',
            'status': 'open',
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'search': 'design'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_issue_report_list_unauthorized(self):
        """Test issue report list without authentication"""
        url = reverse('issue_report_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_issue_report_detail_success(self):
        """Test successful issue report detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('issue_report_detail', kwargs={'report_id': self.issue_report.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('user', response.data)
        self.assertIn('title', response.data)
        self.assertIn('description', response.data)
        self.assertIn('issue_type', response.data)
        self.assertIn('priority', response.data)
        self.assertIn('status', response.data)
        self.assertIn('created_at', response.data)
    
    def test_issue_report_detail_not_found(self):
        """Test issue report detail with non-existent report"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('issue_report_detail', kwargs={'report_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_issue_report_create_success(self):
        """Test successful issue report creation"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('issue_report_create')
        data = {
            'title': 'New Issue',
            'description': 'There is a new issue that needs attention',
            'issue_type': 'technical',
            'priority': 'high',
            'attachments': []
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('report', response.data)
    
    def test_issue_report_create_unauthorized(self):
        """Test issue report creation without authentication"""
        url = reverse('issue_report_create')
        data = {
            'title': 'New Issue',
            'description': 'There is a new issue that needs attention',
            'issue_type': 'technical',
            'priority': 'high',
            'attachments': []
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_issue_report_update_success(self):
        """Test successful issue report update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('issue_report_update', kwargs={'report_id': self.issue_report.id})
        data = {
            'title': 'Updated Issue',
            'description': 'Updated description of the issue',
            'priority': 'high'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('report', response.data)
    
    def test_issue_report_update_unauthorized(self):
        """Test issue report update without authentication"""
        url = reverse('issue_report_update', kwargs={'report_id': self.issue_report.id})
        data = {
            'title': 'Updated Issue',
            'description': 'Updated description of the issue',
            'priority': 'high'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_issue_report_close_success(self):
        """Test successful issue report closure"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('issue_report_close', kwargs={'report_id': self.issue_report.id})
        data = {
            'resolution': 'Issue has been resolved',
            'notes': 'Fixed the problem'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify issue report was closed
        self.issue_report.refresh_from_db()
        self.assertEqual(self.issue_report.status, 'closed')
    
    def test_issue_report_close_unauthorized(self):
        """Test issue report closure without authentication"""
        url = reverse('issue_report_close', kwargs={'report_id': self.issue_report.id})
        data = {
            'resolution': 'Issue has been resolved',
            'notes': 'Fixed the problem'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_issue_report_assign_success(self):
        """Test successful issue report assignment"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('issue_report_assign', kwargs={'report_id': self.issue_report.id})
        data = {
            'assigned_to': self.designer.id,
            'admin_notes': 'Assigned to designer for resolution'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('report', response.data)
    
    def test_issue_report_assign_unauthorized(self):
        """Test issue report assignment without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('issue_report_assign', kwargs={'report_id': self.issue_report.id})
        data = {
            'assigned_to': self.designer.id,
            'admin_notes': 'Assigned to designer for resolution'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_feedback_category_list_success(self):
        """Test successful feedback category list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_category_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_feedback_category_list_unauthorized(self):
        """Test feedback category list without authentication"""
        url = reverse('feedback_category_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_feedback_category_detail_success(self):
        """Test successful feedback category detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_category_detail', kwargs={'category_id': self.feedback_category.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('name', response.data)
        self.assertIn('description', response.data)
        self.assertIn('is_active', response.data)
        self.assertIn('created_at', response.data)
    
    def test_feedback_category_detail_not_found(self):
        """Test feedback category detail with non-existent category"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_category_detail', kwargs={'category_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_feedback_category_create_success(self):
        """Test successful feedback category creation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('feedback_category_create')
        data = {
            'name': 'User Experience',
            'description': 'Feedback related to user experience',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('category', response.data)
    
    def test_feedback_category_create_unauthorized(self):
        """Test feedback category creation without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_category_create')
        data = {
            'name': 'User Experience',
            'description': 'Feedback related to user experience',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_feedback_category_update_success(self):
        """Test successful feedback category update"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('feedback_category_update', kwargs={'category_id': self.feedback_category.id})
        data = {
            'name': 'Updated Design Quality',
            'description': 'Updated feedback related to design quality',
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('category', response.data)
    
    def test_feedback_category_update_unauthorized(self):
        """Test feedback category update without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_category_update', kwargs={'category_id': self.feedback_category.id})
        data = {
            'name': 'Updated Design Quality',
            'description': 'Updated feedback related to design quality',
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_feedback_category_delete_success(self):
        """Test successful feedback category deletion"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('feedback_category_delete', kwargs={'category_id': self.feedback_category.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_feedback_category_delete_unauthorized(self):
        """Test feedback category deletion without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_category_delete', kwargs={'category_id': self.feedback_category.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_feedback_tag_list_success(self):
        """Test successful feedback tag list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_tag_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_feedback_tag_list_unauthorized(self):
        """Test feedback tag list without authentication"""
        url = reverse('feedback_tag_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_feedback_tag_detail_success(self):
        """Test successful feedback tag detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_tag_detail', kwargs={'tag_id': self.feedback_tag.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('name', response.data)
        self.assertIn('description', response.data)
        self.assertIn('is_active', response.data)
        self.assertIn('created_at', response.data)
    
    def test_feedback_tag_detail_not_found(self):
        """Test feedback tag detail with non-existent tag"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_tag_detail', kwargs={'tag_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_feedback_tag_create_success(self):
        """Test successful feedback tag creation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('feedback_tag_create')
        data = {
            'name': 'Good',
            'description': 'Good quality feedback',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('tag', response.data)
    
    def test_feedback_tag_create_unauthorized(self):
        """Test feedback tag creation without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_tag_create')
        data = {
            'name': 'Good',
            'description': 'Good quality feedback',
            'is_active': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_feedback_tag_update_success(self):
        """Test successful feedback tag update"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('feedback_tag_update', kwargs={'tag_id': self.feedback_tag.id})
        data = {
            'name': 'Updated Excellent',
            'description': 'Updated excellent quality feedback',
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('tag', response.data)
    
    def test_feedback_tag_update_unauthorized(self):
        """Test feedback tag update without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_tag_update', kwargs={'tag_id': self.feedback_tag.id})
        data = {
            'name': 'Updated Excellent',
            'description': 'Updated excellent quality feedback',
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_feedback_tag_delete_success(self):
        """Test successful feedback tag deletion"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('feedback_tag_delete', kwargs={'tag_id': self.feedback_tag.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_feedback_tag_delete_unauthorized(self):
        """Test feedback tag deletion without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_tag_delete', kwargs={'tag_id': self.feedback_tag.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_feedback_analytics_success(self):
        """Test successful feedback analytics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('feedback_analytics')
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'group_by': 'day'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_reviews', response.data)
        self.assertIn('average_rating', response.data)
        self.assertIn('total_issues', response.data)
        self.assertIn('open_issues', response.data)
        self.assertIn('closed_issues', response.data)
        self.assertIn('daily_breakdown', response.data)
    
    def test_feedback_analytics_unauthorized(self):
        """Test feedback analytics without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_create')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_create')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_high_rating(self):
        """Test edge case with very high rating"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_create')
        data = {
            'title': 'Perfect Design',
            'content': 'This design is absolutely perfect!',
            'rating': 5,  # Maximum rating
            'category': self.feedback_category.id,
            'tags': [self.feedback_tag.id],
            'is_public': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_special_characters_in_title(self):
        """Test edge case with special characters in title"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_create')
        data = {
            'title': 'Amazing Design! 🎨 #creative',
            'content': 'This design is absolutely amazing!',
            'rating': 5,
            'category': self.feedback_category.id,
            'tags': [self.feedback_tag.id],
            'is_public': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_unicode_in_content(self):
        """Test edge case with unicode characters in content"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('feedback_review_create')
        data = {
            'title': 'Unicode Review',
            'content': 'Reseña con caracteres unicode ✅',
            'rating': 5,
            'category': self.feedback_category.id,
            'tags': [self.feedback_tag.id],
            'is_public': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class FeedbackModelTestCase(TestCase):
    """Test cases for Feedback models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        
        self.feedback_category = FeedbackCategory.objects.create(
            name='Design Quality',
            description='Feedback related to design quality',
            is_active=True
        )
        
        self.feedback_tag = FeedbackTag.objects.create(
            name='Excellent',
            description='Excellent quality feedback',
            is_active=True
        )
    
    def test_feedback_review_creation(self):
        """Test FeedbackReview creation"""
        review = FeedbackReview.objects.create(
            user=self.user,
            title='Great Design',
            content='This design is amazing!',
            rating=5,
            category=self.feedback_category,
            is_public=True
        )
        
        self.assertEqual(review.user, self.user)
        self.assertEqual(review.title, 'Great Design')
        self.assertEqual(review.content, 'This design is amazing!')
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.category, self.feedback_category)
        self.assertTrue(review.is_public)
        self.assertIsNotNone(review.created_at)
        self.assertIsNotNone(review.updated_at)
    
    def test_feedback_review_str(self):
        """Test FeedbackReview string representation"""
        review = FeedbackReview.objects.create(
            user=self.user,
            title='Great Design',
            content='This design is amazing!',
            rating=5,
            category=self.feedback_category,
            is_public=True
        )
        
        expected_str = f"Feedback Review {review.id} - {review.title} (Rating: {review.rating})"
        self.assertEqual(str(review), expected_str)
    
    def test_feedback_review_rating_choices(self):
        """Test FeedbackReview rating choices"""
        choices = FeedbackReview.RATING_CHOICES
        
        self.assertIn((1, '1 Star'), choices)
        self.assertIn((2, '2 Stars'), choices)
        self.assertIn((3, '3 Stars'), choices)
        self.assertIn((4, '4 Stars'), choices)
        self.assertIn((5, '5 Stars'), choices)
    
    def test_feedback_review_get_review_summary(self):
        """Test FeedbackReview get_review_summary method"""
        review = FeedbackReview.objects.create(
            user=self.user,
            title='Great Design',
            content='This design is amazing!',
            rating=5,
            category=self.feedback_category,
            is_public=True
        )
        
        summary = review.get_review_summary()
        
        self.assertEqual(summary['user'], self.user.id)
        self.assertEqual(summary['title'], 'Great Design')
        self.assertEqual(summary['content'], 'This design is amazing!')
        self.assertEqual(summary['rating'], 5)
        self.assertEqual(summary['category'], self.feedback_category.id)
        self.assertTrue(summary['is_public'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_issue_report_creation(self):
        """Test ReportIssue creation"""
        report = ReportIssue.objects.create(
            user=self.user,
            title='Design Issue',
            description='There is an issue with the design',
            issue_type='design_quality',
            priority='medium',
            status='open'
        )
        
        self.assertEqual(report.user, self.user)
        self.assertEqual(report.title, 'Design Issue')
        self.assertEqual(report.description, 'There is an issue with the design')
        self.assertEqual(report.issue_type, 'design_quality')
        self.assertEqual(report.priority, 'medium')
        self.assertEqual(report.status, 'open')
        self.assertIsNotNone(report.created_at)
        self.assertIsNotNone(report.updated_at)
    
    def test_issue_report_str(self):
        """Test ReportIssue string representation"""
        report = ReportIssue.objects.create(
            user=self.user,
            title='Design Issue',
            description='There is an issue with the design',
            issue_type='design_quality',
            priority='medium',
            status='open'
        )
        
        expected_str = f"Issue Report {report.id} - {report.title} ({report.status})"
        self.assertEqual(str(report), expected_str)
    
    def test_issue_report_issue_type_choices(self):
        """Test ReportIssue issue type choices"""
        choices = ReportIssue.ISSUE_TYPE_CHOICES
        
        self.assertIn(('design_quality', 'Design Quality'), choices)
        self.assertIn(('technical', 'Technical'), choices)
        self.assertIn(('user_experience', 'User Experience'), choices)
        self.assertIn(('performance', 'Performance'), choices)
        self.assertIn(('other', 'Other'), choices)
    
    def test_issue_report_priority_choices(self):
        """Test ReportIssue priority choices"""
        choices = ReportIssue.PRIORITY_CHOICES
        
        self.assertIn(('low', 'Low'), choices)
        self.assertIn(('medium', 'Medium'), choices)
        self.assertIn(('high', 'High'), choices)
        self.assertIn(('critical', 'Critical'), choices)
    
    def test_issue_report_status_choices(self):
        """Test ReportIssue status choices"""
        choices = ReportIssue.STATUS_CHOICES
        
        self.assertIn(('open', 'Open'), choices)
        self.assertIn(('in_progress', 'In Progress'), choices)
        self.assertIn(('resolved', 'Resolved'), choices)
        self.assertIn(('closed', 'Closed'), choices)
        self.assertIn(('cancelled', 'Cancelled'), choices)
    
    def test_issue_report_get_report_summary(self):
        """Test ReportIssue get_report_summary method"""
        report = ReportIssue.objects.create(
            user=self.user,
            title='Design Issue',
            description='There is an issue with the design',
            issue_type='design_quality',
            priority='medium',
            status='open'
        )
        
        summary = report.get_report_summary()
        
        self.assertEqual(summary['user'], self.user.id)
        self.assertEqual(summary['title'], 'Design Issue')
        self.assertEqual(summary['description'], 'There is an issue with the design')
        self.assertEqual(summary['issue_type'], 'design_quality')
        self.assertEqual(summary['priority'], 'medium')
        self.assertEqual(summary['status'], 'open')
        self.assertIsNotNone(summary['created_at'])
    
    def test_feedback_category_creation(self):
        """Test FeedbackCategory creation"""
        category = FeedbackCategory.objects.create(
            name='User Experience',
            description='Feedback related to user experience',
            is_active=True
        )
        
        self.assertEqual(category.name, 'User Experience')
        self.assertEqual(category.description, 'Feedback related to user experience')
        self.assertTrue(category.is_active)
        self.assertIsNotNone(category.created_at)
        self.assertIsNotNone(category.updated_at)
    
    def test_feedback_category_str(self):
        """Test FeedbackCategory string representation"""
        category = FeedbackCategory.objects.create(
            name='User Experience',
            description='Feedback related to user experience',
            is_active=True
        )
        
        expected_str = f"Feedback Category {category.id} - {category.name}"
        self.assertEqual(str(category), expected_str)
    
    def test_feedback_category_get_category_summary(self):
        """Test FeedbackCategory get_category_summary method"""
        category = FeedbackCategory.objects.create(
            name='User Experience',
            description='Feedback related to user experience',
            is_active=True
        )
        
        summary = category.get_category_summary()
        
        self.assertEqual(summary['name'], 'User Experience')
        self.assertEqual(summary['description'], 'Feedback related to user experience')
        self.assertTrue(summary['is_active'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_feedback_tag_creation(self):
        """Test FeedbackTag creation"""
        tag = FeedbackTag.objects.create(
            name='Good',
            description='Good quality feedback',
            is_active=True
        )
        
        self.assertEqual(tag.name, 'Good')
        self.assertEqual(tag.description, 'Good quality feedback')
        self.assertTrue(tag.is_active)
        self.assertIsNotNone(tag.created_at)
        self.assertIsNotNone(tag.updated_at)
    
    def test_feedback_tag_str(self):
        """Test FeedbackTag string representation"""
        tag = FeedbackTag.objects.create(
            name='Good',
            description='Good quality feedback',
            is_active=True
        )
        
        expected_str = f"Feedback Tag {tag.id} - {tag.name}"
        self.assertEqual(str(tag), expected_str)
    
    def test_feedback_tag_get_tag_summary(self):
        """Test FeedbackTag get_tag_summary method"""
        tag = FeedbackTag.objects.create(
            name='Good',
            description='Good quality feedback',
            is_active=True
        )
        
        summary = tag.get_tag_summary()
        
        self.assertEqual(summary['name'], 'Good')
        self.assertEqual(summary['description'], 'Good quality feedback')
        self.assertTrue(summary['is_active'])
        self.assertIsNotNone(summary['created_at'])