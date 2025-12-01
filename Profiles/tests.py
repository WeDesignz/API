"""
Comprehensive tests for Profiles app
Tests designer profiles, portfolios, and profile management
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

from .models import DesignerProfile, DesignerPortfolio, DesignerSkill, DesignerExperience
from common.relations import attach_relation


class ProfilesAPITestCase(APITestCase):
    """Test cases for Profiles API endpoints"""
    
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
        
        # Create designer profile
        self.designer_profile = DesignerProfile.objects.create(
            bio='Experienced graphic designer with 5+ years of experience',
            specialization='Graphic Design',
            experience_years=5,
            hourly_rate=Decimal('50.00'),
            availability='available',
            portfolio_url='https://portfolio.example.com',
            linkedin_url='https://linkedin.com/in/designer',
            behance_url='https://behance.net/designer',
            is_verified=True,
            is_active=True
        )
        attach_relation('DesignerProfile:User', self.designer_profile, self.designer)
        
        # Create designer portfolio
        self.designer_portfolio = DesignerPortfolio.objects.create(
            title='Logo Design Collection',
            description='A collection of modern logo designs',
            category='Logo Design',
            tags=['logo', 'branding', 'modern'],
            is_featured=True,
            is_public=True
        )
        attach_relation('DesignerPortfolio:DesignerProfile', self.designer_portfolio, self.designer_profile)
        
        # Create designer skill
        self.designer_skill = DesignerSkill.objects.create(
            skill_name='Adobe Photoshop',
            skill_level='expert',
            years_of_experience=5,
            is_primary=True
        )
        attach_relation('DesignerSkill:DesignerProfile', self.designer_skill, self.designer_profile)
        
        # Create designer experience
        self.designer_experience = DesignerExperience.objects.create(
            company_name='Design Studio Inc',
            position='Senior Graphic Designer',
            start_date='2020-01-01',
            end_date='2023-12-31',
            description='Led design projects for major clients',
            is_current=False
        )
        attach_relation('DesignerExperience:DesignerProfile', self.designer_experience, self.designer_profile)
    
    def test_designer_profile_list_success(self):
        """Test successful designer profile list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_profile_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_designer_profile_list_with_filters(self):
        """Test designer profile list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_profile_list')
        params = {
            'specialization': 'Graphic Design',
            'experience_years': '5',
            'availability': 'available',
            'is_verified': 'true',
            'min_hourly_rate': '30.00',
            'max_hourly_rate': '100.00',
            'search': 'designer'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_designer_profile_detail_success(self):
        """Test successful designer profile detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_profile_detail', kwargs={'profile_id': self.designer_profile.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('bio', response.data)
        self.assertIn('specialization', response.data)
        self.assertIn('experience_years', response.data)
        self.assertIn('hourly_rate', response.data)
        self.assertIn('availability', response.data)
        self.assertIn('is_verified', response.data)
        self.assertIn('created_at', response.data)
    
    def test_designer_profile_detail_not_found(self):
        """Test designer profile detail with non-existent profile"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_profile_detail', kwargs={'profile_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_designer_profile_create_success(self):
        """Test successful designer profile creation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_profile_create')
        data = {
            'bio': 'Creative designer with passion for innovation',
            'specialization': 'UI/UX Design',
            'experience_years': 3,
            'hourly_rate': '40.00',
            'availability': 'available',
            'portfolio_url': 'https://portfolio.example.com',
            'linkedin_url': 'https://linkedin.com/in/designer',
            'behance_url': 'https://behance.net/designer'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('profile', response.data)
    
    def test_designer_profile_create_unauthorized(self):
        """Test designer profile creation without authentication"""
        url = reverse('designer_profile_create')
        data = {
            'bio': 'Creative designer with passion for innovation',
            'specialization': 'UI/UX Design',
            'experience_years': 3,
            'hourly_rate': '40.00',
            'availability': 'available'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_profile_update_success(self):
        """Test successful designer profile update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_profile_update', kwargs={'profile_id': self.designer_profile.id})
        data = {
            'bio': 'Updated bio with more experience',
            'specialization': 'Brand Design',
            'experience_years': 6,
            'hourly_rate': '60.00',
            'availability': 'busy'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('profile', response.data)
    
    def test_designer_profile_update_unauthorized(self):
        """Test designer profile update without authentication"""
        url = reverse('designer_profile_update', kwargs={'profile_id': self.designer_profile.id})
        data = {
            'bio': 'Updated bio with more experience',
            'specialization': 'Brand Design'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_profile_verify_success(self):
        """Test successful designer profile verification"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('designer_profile_verify', kwargs={'profile_id': self.designer_profile.id})
        data = {
            'is_verified': True,
            'admin_notes': 'Profile verified by admin'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify profile was verified
        self.designer_profile.refresh_from_db()
        self.assertTrue(self.designer_profile.is_verified)
    
    def test_designer_profile_verify_unauthorized(self):
        """Test designer profile verification without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_profile_verify', kwargs={'profile_id': self.designer_profile.id})
        data = {
            'is_verified': True,
            'admin_notes': 'Profile verified by admin'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_designer_portfolio_list_success(self):
        """Test successful designer portfolio list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_portfolio_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_designer_portfolio_list_with_filters(self):
        """Test designer portfolio list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_portfolio_list')
        params = {
            'category': 'Logo Design',
            'is_featured': 'true',
            'is_public': 'true',
            'search': 'logo'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_designer_portfolio_detail_success(self):
        """Test successful designer portfolio detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_portfolio_detail', kwargs={'portfolio_id': self.designer_portfolio.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('title', response.data)
        self.assertIn('description', response.data)
        self.assertIn('category', response.data)
        self.assertIn('tags', response.data)
        self.assertIn('is_featured', response.data)
        self.assertIn('is_public', response.data)
        self.assertIn('created_at', response.data)
    
    def test_designer_portfolio_detail_not_found(self):
        """Test designer portfolio detail with non-existent portfolio"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_portfolio_detail', kwargs={'portfolio_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_designer_portfolio_create_success(self):
        """Test successful designer portfolio creation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_portfolio_create')
        data = {
            'title': 'Web Design Collection',
            'description': 'A collection of modern web designs',
            'category': 'Web Design',
            'tags': ['web', 'design', 'modern'],
            'is_featured': False,
            'is_public': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('portfolio', response.data)
    
    def test_designer_portfolio_create_unauthorized(self):
        """Test designer portfolio creation without authentication"""
        url = reverse('designer_portfolio_create')
        data = {
            'title': 'Web Design Collection',
            'description': 'A collection of modern web designs',
            'category': 'Web Design',
            'tags': ['web', 'design', 'modern']
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_portfolio_update_success(self):
        """Test successful designer portfolio update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_portfolio_update', kwargs={'portfolio_id': self.designer_portfolio.id})
        data = {
            'title': 'Updated Logo Design Collection',
            'description': 'An updated collection of modern logo designs',
            'category': 'Brand Design',
            'tags': ['logo', 'branding', 'modern', 'updated'],
            'is_featured': True,
            'is_public': True
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('portfolio', response.data)
    
    def test_designer_portfolio_update_unauthorized(self):
        """Test designer portfolio update without authentication"""
        url = reverse('designer_portfolio_update', kwargs={'portfolio_id': self.designer_portfolio.id})
        data = {
            'title': 'Updated Logo Design Collection',
            'description': 'An updated collection of modern logo designs'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_portfolio_delete_success(self):
        """Test successful designer portfolio deletion"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_portfolio_delete', kwargs={'portfolio_id': self.designer_portfolio.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_designer_portfolio_delete_unauthorized(self):
        """Test designer portfolio deletion without authentication"""
        url = reverse('designer_portfolio_delete', kwargs={'portfolio_id': self.designer_portfolio.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_skill_list_success(self):
        """Test successful designer skill list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_skill_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_designer_skill_list_with_filters(self):
        """Test designer skill list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_skill_list')
        params = {
            'skill_level': 'expert',
            'is_primary': 'true',
            'min_years_experience': '3',
            'max_years_experience': '10'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_designer_skill_detail_success(self):
        """Test successful designer skill detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_skill_detail', kwargs={'skill_id': self.designer_skill.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('skill_name', response.data)
        self.assertIn('skill_level', response.data)
        self.assertIn('years_of_experience', response.data)
        self.assertIn('is_primary', response.data)
        self.assertIn('created_at', response.data)
    
    def test_designer_skill_detail_not_found(self):
        """Test designer skill detail with non-existent skill"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_skill_detail', kwargs={'skill_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_designer_skill_create_success(self):
        """Test successful designer skill creation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_skill_create')
        data = {
            'skill_name': 'Adobe Illustrator',
            'skill_level': 'intermediate',
            'years_of_experience': 3,
            'is_primary': False
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('skill', response.data)
    
    def test_designer_skill_create_unauthorized(self):
        """Test designer skill creation without authentication"""
        url = reverse('designer_skill_create')
        data = {
            'skill_name': 'Adobe Illustrator',
            'skill_level': 'intermediate',
            'years_of_experience': 3,
            'is_primary': False
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_skill_update_success(self):
        """Test successful designer skill update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_skill_update', kwargs={'skill_id': self.designer_skill.id})
        data = {
            'skill_name': 'Adobe Photoshop Pro',
            'skill_level': 'expert',
            'years_of_experience': 6,
            'is_primary': True
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('skill', response.data)
    
    def test_designer_skill_update_unauthorized(self):
        """Test designer skill update without authentication"""
        url = reverse('designer_skill_update', kwargs={'skill_id': self.designer_skill.id})
        data = {
            'skill_name': 'Adobe Photoshop Pro',
            'skill_level': 'expert'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_skill_delete_success(self):
        """Test successful designer skill deletion"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_skill_delete', kwargs={'skill_id': self.designer_skill.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_designer_skill_delete_unauthorized(self):
        """Test designer skill deletion without authentication"""
        url = reverse('designer_skill_delete', kwargs={'skill_id': self.designer_skill.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_experience_list_success(self):
        """Test successful designer experience list retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_experience_list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_designer_experience_list_with_filters(self):
        """Test designer experience list with filters"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_experience_list')
        params = {
            'company_name': 'Design Studio Inc',
            'position': 'Senior Graphic Designer',
            'is_current': 'false',
            'start_date': '2020-01-01',
            'end_date': '2023-12-31'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
    
    def test_designer_experience_detail_success(self):
        """Test successful designer experience detail retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_experience_detail', kwargs={'experience_id': self.designer_experience.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('company_name', response.data)
        self.assertIn('position', response.data)
        self.assertIn('start_date', response.data)
        self.assertIn('end_date', response.data)
        self.assertIn('description', response.data)
        self.assertIn('is_current', response.data)
        self.assertIn('created_at', response.data)
    
    def test_designer_experience_detail_not_found(self):
        """Test designer experience detail with non-existent experience"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_experience_detail', kwargs={'experience_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_designer_experience_create_success(self):
        """Test successful designer experience creation"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_experience_create')
        data = {
            'company_name': 'Creative Agency Ltd',
            'position': 'UI/UX Designer',
            'start_date': '2022-01-01',
            'end_date': '2024-12-31',
            'description': 'Designed user interfaces for mobile and web applications',
            'is_current': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('experience', response.data)
    
    def test_designer_experience_create_unauthorized(self):
        """Test designer experience creation without authentication"""
        url = reverse('designer_experience_create')
        data = {
            'company_name': 'Creative Agency Ltd',
            'position': 'UI/UX Designer',
            'start_date': '2022-01-01',
            'end_date': '2024-12-31',
            'description': 'Designed user interfaces for mobile and web applications',
            'is_current': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_experience_update_success(self):
        """Test successful designer experience update"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_experience_update', kwargs={'experience_id': self.designer_experience.id})
        data = {
            'company_name': 'Updated Design Studio Inc',
            'position': 'Lead Graphic Designer',
            'start_date': '2020-01-01',
            'end_date': '2023-12-31',
            'description': 'Led design projects for major clients and managed design team',
            'is_current': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('experience', response.data)
    
    def test_designer_experience_update_unauthorized(self):
        """Test designer experience update without authentication"""
        url = reverse('designer_experience_update', kwargs={'experience_id': self.designer_experience.id})
        data = {
            'company_name': 'Updated Design Studio Inc',
            'position': 'Lead Graphic Designer'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_experience_delete_success(self):
        """Test successful designer experience deletion"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_experience_delete', kwargs={'experience_id': self.designer_experience.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_designer_experience_delete_unauthorized(self):
        """Test designer experience deletion without authentication"""
        url = reverse('designer_experience_delete', kwargs={'experience_id': self.designer_experience.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_designer_analytics_success(self):
        """Test successful designer analytics retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('designer_analytics')
        params = {
            'start_date': '2024-01-01',
            'end_date': '2024-12-31',
            'group_by': 'day'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_designers', response.data)
        self.assertIn('verified_designers', response.data)
        self.assertIn('active_designers', response.data)
        self.assertIn('average_hourly_rate', response.data)
        self.assertIn('specialization_breakdown', response.data)
        self.assertIn('daily_breakdown', response.data)
    
    def test_designer_analytics_unauthorized(self):
        """Test designer analytics without admin authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_analytics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_designer_search_success(self):
        """Test successful designer search"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('designer_search')
        params = {
            'query': 'graphic designer',
            'specialization': 'Graphic Design',
            'min_experience': '3',
            'max_experience': '10',
            'availability': 'available'
        }
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_profile_create')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_profile_create')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_long_bio(self):
        """Test edge case with very long bio"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_profile_create')
        data = {
            'bio': 'A' * 10000,  # Very long bio
            'specialization': 'Graphic Design',
            'experience_years': 5,
            'hourly_rate': '50.00',
            'availability': 'available'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_special_characters_in_tags(self):
        """Test edge case with special characters in tags"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_portfolio_create')
        data = {
            'title': 'Special Design Collection',
            'description': 'A collection with special characters',
            'category': 'Special Design',
            'tags': ['design', 'special', '🎨', 'creative'],
            'is_featured': False,
            'is_public': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_unicode_in_description(self):
        """Test edge case with unicode characters in description"""
        self.client.force_authenticate(user=self.designer)
        
        url = reverse('designer_portfolio_create')
        data = {
            'title': 'Unicode Design Collection',
            'description': 'Una colección de diseños con caracteres unicode ✅',
            'category': 'Unicode Design',
            'tags': ['design', 'unicode', 'special'],
            'is_featured': False,
            'is_public': True
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class ProfilesModelTestCase(TestCase):
    """Test cases for Profiles models"""
    
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
    
    def test_designer_profile_creation(self):
        """Test DesignerProfile creation"""
        profile = DesignerProfile.objects.create(
            bio='Experienced graphic designer with 5+ years of experience',
            specialization='Graphic Design',
            experience_years=5,
            hourly_rate=Decimal('50.00'),
            availability='available',
            portfolio_url='https://portfolio.example.com',
            linkedin_url='https://linkedin.com/in/designer',
            behance_url='https://behance.net/designer',
            is_verified=True,
            is_active=True
        )
        
        self.assertEqual(profile.bio, 'Experienced graphic designer with 5+ years of experience')
        self.assertEqual(profile.specialization, 'Graphic Design')
        self.assertEqual(profile.experience_years, 5)
        self.assertEqual(profile.hourly_rate, Decimal('50.00'))
        self.assertEqual(profile.availability, 'available')
        self.assertEqual(profile.portfolio_url, 'https://portfolio.example.com')
        self.assertEqual(profile.linkedin_url, 'https://linkedin.com/in/designer')
        self.assertEqual(profile.behance_url, 'https://behance.net/designer')
        self.assertTrue(profile.is_verified)
        self.assertTrue(profile.is_active)
        self.assertIsNotNone(profile.created_at)
        self.assertIsNotNone(profile.updated_at)
    
    def test_designer_profile_str(self):
        """Test DesignerProfile string representation"""
        profile = DesignerProfile.objects.create(
            bio='Experienced graphic designer with 5+ years of experience',
            specialization='Graphic Design',
            experience_years=5,
            hourly_rate=Decimal('50.00'),
            availability='available',
            is_verified=True,
            is_active=True
        )
        
        expected_str = f"Designer Profile {profile.id}"
        self.assertEqual(str(profile), expected_str)
    
    def test_designer_profile_availability_choices(self):
        """Test DesignerProfile availability choices"""
        choices = DesignerProfile.AVAILABILITY_CHOICES
        
        self.assertIn(('available', 'Available'), choices)
        self.assertIn(('busy', 'Busy'), choices)
        self.assertIn(('unavailable', 'Unavailable'), choices)
        self.assertIn(('on_break', 'On Break'), choices)
    
    def test_designer_profile_verify_profile(self):
        """Test DesignerProfile verify_profile method"""
        profile = DesignerProfile.objects.create(
            bio='Experienced graphic designer with 5+ years of experience',
            specialization='Graphic Design',
            experience_years=5,
            hourly_rate=Decimal('50.00'),
            availability='available',
            is_verified=False,
            is_active=True
        )
        
        profile.verify_profile(
            verified_by_id=self.user.id,
            admin_notes='Profile verified by admin'
        )
        
        self.assertTrue(profile.is_verified)
        self.assertEqual(profile.verified_by_id, self.user.id)
        self.assertEqual(profile.admin_notes, 'Profile verified by admin')
        self.assertIsNotNone(profile.verified_at)
    
    def test_designer_profile_unverify_profile(self):
        """Test DesignerProfile unverify_profile method"""
        profile = DesignerProfile.objects.create(
            bio='Experienced graphic designer with 5+ years of experience',
            specialization='Graphic Design',
            experience_years=5,
            hourly_rate=Decimal('50.00'),
            availability='available',
            is_verified=True,
            is_active=True,
            verified_by_id=self.user.id
        )
        
        profile.unverify_profile(
            unverified_by_id=self.user.id,
            admin_notes='Profile unverified by admin'
        )
        
        self.assertFalse(profile.is_verified)
        self.assertEqual(profile.unverified_by_id, self.user.id)
        self.assertEqual(profile.admin_notes, 'Profile unverified by admin')
        self.assertIsNotNone(profile.unverified_at)
    
    def test_designer_profile_activate_profile(self):
        """Test DesignerProfile activate_profile method"""
        profile = DesignerProfile.objects.create(
            bio='Experienced graphic designer with 5+ years of experience',
            specialization='Graphic Design',
            experience_years=5,
            hourly_rate=Decimal('50.00'),
            availability='available',
            is_verified=True,
            is_active=False
        )
        
        profile.activate_profile(
            activated_by_id=self.user.id,
            admin_notes='Profile activated by admin'
        )
        
        self.assertTrue(profile.is_active)
        self.assertEqual(profile.activated_by_id, self.user.id)
        self.assertEqual(profile.admin_notes, 'Profile activated by admin')
        self.assertIsNotNone(profile.activated_at)
    
    def test_designer_profile_deactivate_profile(self):
        """Test DesignerProfile deactivate_profile method"""
        profile = DesignerProfile.objects.create(
            bio='Experienced graphic designer with 5+ years of experience',
            specialization='Graphic Design',
            experience_years=5,
            hourly_rate=Decimal('50.00'),
            availability='available',
            is_verified=True,
            is_active=True
        )
        
        profile.deactivate_profile(
            deactivated_by_id=self.user.id,
            admin_notes='Profile deactivated by admin'
        )
        
        self.assertFalse(profile.is_active)
        self.assertEqual(profile.deactivated_by_id, self.user.id)
        self.assertEqual(profile.admin_notes, 'Profile deactivated by admin')
        self.assertIsNotNone(profile.deactivated_at)
    
    def test_designer_profile_get_profile_summary(self):
        """Test DesignerProfile get_profile_summary method"""
        profile = DesignerProfile.objects.create(
            bio='Experienced graphic designer with 5+ years of experience',
            specialization='Graphic Design',
            experience_years=5,
            hourly_rate=Decimal('50.00'),
            availability='available',
            portfolio_url='https://portfolio.example.com',
            linkedin_url='https://linkedin.com/in/designer',
            behance_url='https://behance.net/designer',
            is_verified=True,
            is_active=True
        )
        
        summary = profile.get_profile_summary()
        
        self.assertEqual(summary['bio'], 'Experienced graphic designer with 5+ years of experience')
        self.assertEqual(summary['specialization'], 'Graphic Design')
        self.assertEqual(summary['experience_years'], 5)
        self.assertEqual(summary['hourly_rate'], Decimal('50.00'))
        self.assertEqual(summary['availability'], 'available')
        self.assertEqual(summary['portfolio_url'], 'https://portfolio.example.com')
        self.assertEqual(summary['linkedin_url'], 'https://linkedin.com/in/designer')
        self.assertEqual(summary['behance_url'], 'https://behance.net/designer')
        self.assertTrue(summary['is_verified'])
        self.assertTrue(summary['is_active'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_designer_portfolio_creation(self):
        """Test DesignerPortfolio creation"""
        portfolio = DesignerPortfolio.objects.create(
            title='Logo Design Collection',
            description='A collection of modern logo designs',
            category='Logo Design',
            tags=['logo', 'branding', 'modern'],
            is_featured=True,
            is_public=True
        )
        
        self.assertEqual(portfolio.title, 'Logo Design Collection')
        self.assertEqual(portfolio.description, 'A collection of modern logo designs')
        self.assertEqual(portfolio.category, 'Logo Design')
        self.assertEqual(portfolio.tags, ['logo', 'branding', 'modern'])
        self.assertTrue(portfolio.is_featured)
        self.assertTrue(portfolio.is_public)
        self.assertIsNotNone(portfolio.created_at)
        self.assertIsNotNone(portfolio.updated_at)
    
    def test_designer_portfolio_str(self):
        """Test DesignerPortfolio string representation"""
        portfolio = DesignerPortfolio.objects.create(
            title='Logo Design Collection',
            description='A collection of modern logo designs',
            category='Logo Design',
            tags=['logo', 'branding', 'modern'],
            is_featured=True,
            is_public=True
        )
        
        expected_str = f"Designer Portfolio {portfolio.id} - {portfolio.title}"
        self.assertEqual(str(portfolio), expected_str)
    
    def test_designer_portfolio_make_featured(self):
        """Test DesignerPortfolio make_featured method"""
        portfolio = DesignerPortfolio.objects.create(
            title='Logo Design Collection',
            description='A collection of modern logo designs',
            category='Logo Design',
            tags=['logo', 'branding', 'modern'],
            is_featured=False,
            is_public=True
        )
        
        portfolio.make_featured(
            featured_by_id=self.user.id,
            admin_notes='Portfolio featured by admin'
        )
        
        self.assertTrue(portfolio.is_featured)
        self.assertEqual(portfolio.featured_by_id, self.user.id)
        self.assertEqual(portfolio.admin_notes, 'Portfolio featured by admin')
        self.assertIsNotNone(portfolio.featured_at)
    
    def test_designer_portfolio_make_public(self):
        """Test DesignerPortfolio make_public method"""
        portfolio = DesignerPortfolio.objects.create(
            title='Logo Design Collection',
            description='A collection of modern logo designs',
            category='Logo Design',
            tags=['logo', 'branding', 'modern'],
            is_featured=True,
            is_public=False
        )
        
        portfolio.make_public(
            made_public_by_id=self.user.id,
            admin_notes='Portfolio made public by admin'
        )
        
        self.assertTrue(portfolio.is_public)
        self.assertEqual(portfolio.made_public_by_id, self.user.id)
        self.assertEqual(portfolio.admin_notes, 'Portfolio made public by admin')
        self.assertIsNotNone(portfolio.made_public_at)
    
    def test_designer_portfolio_make_private(self):
        """Test DesignerPortfolio make_private method"""
        portfolio = DesignerPortfolio.objects.create(
            title='Logo Design Collection',
            description='A collection of modern logo designs',
            category='Logo Design',
            tags=['logo', 'branding', 'modern'],
            is_featured=True,
            is_public=True
        )
        
        portfolio.make_private(
            made_private_by_id=self.user.id,
            admin_notes='Portfolio made private by admin'
        )
        
        self.assertFalse(portfolio.is_public)
        self.assertEqual(portfolio.made_private_by_id, self.user.id)
        self.assertEqual(portfolio.admin_notes, 'Portfolio made private by admin')
        self.assertIsNotNone(portfolio.made_private_at)
    
    def test_designer_portfolio_get_portfolio_summary(self):
        """Test DesignerPortfolio get_portfolio_summary method"""
        portfolio = DesignerPortfolio.objects.create(
            title='Logo Design Collection',
            description='A collection of modern logo designs',
            category='Logo Design',
            tags=['logo', 'branding', 'modern'],
            is_featured=True,
            is_public=True
        )
        
        summary = portfolio.get_portfolio_summary()
        
        self.assertEqual(summary['title'], 'Logo Design Collection')
        self.assertEqual(summary['description'], 'A collection of modern logo designs')
        self.assertEqual(summary['category'], 'Logo Design')
        self.assertEqual(summary['tags'], ['logo', 'branding', 'modern'])
        self.assertTrue(summary['is_featured'])
        self.assertTrue(summary['is_public'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_designer_skill_creation(self):
        """Test DesignerSkill creation"""
        skill = DesignerSkill.objects.create(
            skill_name='Adobe Photoshop',
            skill_level='expert',
            years_of_experience=5,
            is_primary=True
        )
        
        self.assertEqual(skill.skill_name, 'Adobe Photoshop')
        self.assertEqual(skill.skill_level, 'expert')
        self.assertEqual(skill.years_of_experience, 5)
        self.assertTrue(skill.is_primary)
        self.assertIsNotNone(skill.created_at)
        self.assertIsNotNone(skill.updated_at)
    
    def test_designer_skill_str(self):
        """Test DesignerSkill string representation"""
        skill = DesignerSkill.objects.create(
            skill_name='Adobe Photoshop',
            skill_level='expert',
            years_of_experience=5,
            is_primary=True
        )
        
        expected_str = f"Designer Skill {skill.id} - {skill.skill_name}"
        self.assertEqual(str(skill), expected_str)
    
    def test_designer_skill_skill_level_choices(self):
        """Test DesignerSkill skill level choices"""
        choices = DesignerSkill.SKILL_LEVEL_CHOICES
        
        self.assertIn(('beginner', 'Beginner'), choices)
        self.assertIn(('intermediate', 'Intermediate'), choices)
        self.assertIn(('advanced', 'Advanced'), choices)
        self.assertIn(('expert', 'Expert'), choices)
        self.assertIn(('master', 'Master'), choices)
    
    def test_designer_skill_make_primary(self):
        """Test DesignerSkill make_primary method"""
        skill = DesignerSkill.objects.create(
            skill_name='Adobe Photoshop',
            skill_level='expert',
            years_of_experience=5,
            is_primary=False
        )
        
        skill.make_primary(
            made_primary_by_id=self.user.id,
            admin_notes='Skill made primary by admin'
        )
        
        self.assertTrue(skill.is_primary)
        self.assertEqual(skill.made_primary_by_id, self.user.id)
        self.assertEqual(skill.admin_notes, 'Skill made primary by admin')
        self.assertIsNotNone(skill.made_primary_at)
    
    def test_designer_skill_get_skill_summary(self):
        """Test DesignerSkill get_skill_summary method"""
        skill = DesignerSkill.objects.create(
            skill_name='Adobe Photoshop',
            skill_level='expert',
            years_of_experience=5,
            is_primary=True
        )
        
        summary = skill.get_skill_summary()
        
        self.assertEqual(summary['skill_name'], 'Adobe Photoshop')
        self.assertEqual(summary['skill_level'], 'expert')
        self.assertEqual(summary['years_of_experience'], 5)
        self.assertTrue(summary['is_primary'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_designer_experience_creation(self):
        """Test DesignerExperience creation"""
        experience = DesignerExperience.objects.create(
            company_name='Design Studio Inc',
            position='Senior Graphic Designer',
            start_date='2020-01-01',
            end_date='2023-12-31',
            description='Led design projects for major clients',
            is_current=False
        )
        
        self.assertEqual(experience.company_name, 'Design Studio Inc')
        self.assertEqual(experience.position, 'Senior Graphic Designer')
        self.assertEqual(experience.start_date, '2020-01-01')
        self.assertEqual(experience.end_date, '2023-12-31')
        self.assertEqual(experience.description, 'Led design projects for major clients')
        self.assertFalse(experience.is_current)
        self.assertIsNotNone(experience.created_at)
        self.assertIsNotNone(experience.updated_at)
    
    def test_designer_experience_str(self):
        """Test DesignerExperience string representation"""
        experience = DesignerExperience.objects.create(
            company_name='Design Studio Inc',
            position='Senior Graphic Designer',
            start_date='2020-01-01',
            end_date='2023-12-31',
            description='Led design projects for major clients',
            is_current=False
        )
        
        expected_str = f"Designer Experience {experience.id} - {experience.position} at {experience.company_name}"
        self.assertEqual(str(experience), expected_str)
    
    def test_designer_experience_make_current(self):
        """Test DesignerExperience make_current method"""
        experience = DesignerExperience.objects.create(
            company_name='Design Studio Inc',
            position='Senior Graphic Designer',
            start_date='2020-01-01',
            end_date='2023-12-31',
            description='Led design projects for major clients',
            is_current=False
        )
        
        experience.make_current(
            made_current_by_id=self.user.id,
            admin_notes='Experience made current by admin'
        )
        
        self.assertTrue(experience.is_current)
        self.assertEqual(experience.made_current_by_id, self.user.id)
        self.assertEqual(experience.admin_notes, 'Experience made current by admin')
        self.assertIsNotNone(experience.made_current_at)
    
    def test_designer_experience_get_experience_summary(self):
        """Test DesignerExperience get_experience_summary method"""
        experience = DesignerExperience.objects.create(
            company_name='Design Studio Inc',
            position='Senior Graphic Designer',
            start_date='2020-01-01',
            end_date='2023-12-31',
            description='Led design projects for major clients',
            is_current=False
        )
        
        summary = experience.get_experience_summary()
        
        self.assertEqual(summary['company_name'], 'Design Studio Inc')
        self.assertEqual(summary['position'], 'Senior Graphic Designer')
        self.assertEqual(summary['start_date'], '2020-01-01')
        self.assertEqual(summary['end_date'], '2023-12-31')
        self.assertEqual(summary['description'], 'Led design projects for major clients')
        self.assertFalse(summary['is_current'])
        self.assertIsNotNone(summary['created_at'])
    
    def test_designer_profile_get_availability_display(self):
        """Test DesignerProfile get_availability_display method"""
        profile = DesignerProfile.objects.create(
            bio='Experienced graphic designer with 5+ years of experience',
            specialization='Graphic Design',
            experience_years=5,
            hourly_rate=Decimal('50.00'),
            availability='available',
            is_verified=True,
            is_active=True
        )
        
        availability_display = profile.get_availability_display()
        self.assertEqual(availability_display, 'Available')
    
    def test_designer_profile_get_hourly_rate_display(self):
        """Test DesignerProfile get_hourly_rate_display method"""
        profile = DesignerProfile.objects.create(
            bio='Experienced graphic designer with 5+ years of experience',
            specialization='Graphic Design',
            experience_years=5,
            hourly_rate=Decimal('50.00'),
            availability='available',
            is_verified=True,
            is_active=True
        )
        
        hourly_rate_display = profile.get_hourly_rate_display()
        self.assertEqual(hourly_rate_display, '₹50.00/hour')
    
    def test_designer_portfolio_get_tags_display(self):
        """Test DesignerPortfolio get_tags_display method"""
        portfolio = DesignerPortfolio.objects.create(
            title='Logo Design Collection',
            description='A collection of modern logo designs',
            category='Logo Design',
            tags=['logo', 'branding', 'modern'],
            is_featured=True,
            is_public=True
        )
        
        tags_display = portfolio.get_tags_display()
        self.assertEqual(tags_display, 'logo, branding, modern')
    
    def test_designer_skill_get_skill_level_display(self):
        """Test DesignerSkill get_skill_level_display method"""
        skill = DesignerSkill.objects.create(
            skill_name='Adobe Photoshop',
            skill_level='expert',
            years_of_experience=5,
            is_primary=True
        )
        
        skill_level_display = skill.get_skill_level_display()
        self.assertEqual(skill_level_display, 'Expert')
    
    def test_designer_experience_get_duration(self):
        """Test DesignerExperience get_duration method"""
        experience = DesignerExperience.objects.create(
            company_name='Design Studio Inc',
            position='Senior Graphic Designer',
            start_date='2020-01-01',
            end_date='2023-12-31',
            description='Led design projects for major clients',
            is_current=False
        )
        
        duration = experience.get_duration()
        self.assertEqual(duration, '4 years')
    
    def test_designer_experience_get_duration_current(self):
        """Test DesignerExperience get_duration method for current experience"""
        experience = DesignerExperience.objects.create(
            company_name='Design Studio Inc',
            position='Senior Graphic Designer',
            start_date='2020-01-01',
            end_date=None,
            description='Led design projects for major clients',
            is_current=True
        )
        
        duration = experience.get_duration()
        self.assertIn('years', duration)
        self.assertIn('current', duration.lower())