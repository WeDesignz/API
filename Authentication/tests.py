"""
Comprehensive tests for Authentication app
Tests user authentication, email/mobile verification, and OTP functionality
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

from .models import Email, MobileNumber, OTP


class AuthenticationAPITestCase(APITestCase):
    """Test cases for Authentication API endpoints"""
    
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
        
        # Create email
        self.email = Email.objects.create(
            email='test@example.com',
            is_verified=True,
            is_primary=True,
            created_by=self.user
        )
        
        # Create mobile number
        self.mobile = MobileNumber.objects.create(
            mobile_number='+1234567890',
            is_verified=True,
            is_primary=True,
            created_by=self.user
        )
        
        # Create OTP
        self.otp = OTP.objects.create(
            otp='123456',
            otp_type='E',
            otp_for='email_verification',
            is_verified=False,
            expires_at=timezone.now() + timedelta(minutes=10),
            created_by=self.user
        )
    
    def test_user_register_success(self):
        """Test successful user registration"""
        url = reverse('user_register')
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpassword123',
            'confirm_password': 'newpassword123',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
    
    def test_user_register_password_mismatch(self):
        """Test user registration with password mismatch"""
        url = reverse('user_register')
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpassword123',
            'confirm_password': 'differentpassword',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_user_register_duplicate_email(self):
        """Test user registration with duplicate email"""
        url = reverse('user_register')
        data = {
            'username': 'newuser',
            'email': 'test@example.com',  # Existing email
            'password': 'newpassword123',
            'confirm_password': 'newpassword123',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_user_login_success(self):
        """Test successful user login"""
        url = reverse('user_login')
        data = {
            'email': 'test@example.com',
            'password': 'password123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
    
    def test_user_login_invalid_credentials(self):
        """Test user login with invalid credentials"""
        url = reverse('user_login')
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_user_login_inactive_account(self):
        """Test user login with inactive account"""
        # Deactivate user
        self.user.is_active = False
        self.user.save()
        
        url = reverse('user_login')
        data = {
            'email': 'test@example.com',
            'password': 'password123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_user_logout_success(self):
        """Test successful user logout"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('user_logout')
        data = {
            'refresh_token': 'test_refresh_token'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_user_logout_unauthorized(self):
        """Test user logout without authentication"""
        url = reverse('user_logout')
        data = {
            'refresh_token': 'test_refresh_token'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_profile_success(self):
        """Test successful user profile retrieval"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('user_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
    
    def test_user_profile_unauthorized(self):
        """Test user profile without authentication"""
        url = reverse('user_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_profile_update_success(self):
        """Test successful user profile update"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('user_profile_update')
        data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)
    
    def test_user_profile_update_unauthorized(self):
        """Test user profile update without authentication"""
        url = reverse('user_profile_update')
        data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_change_password_success(self):
        """Test successful password change"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('user_change_password')
        data = {
            'old_password': 'password123',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_user_change_password_wrong_old_password(self):
        """Test password change with wrong old password"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('user_change_password')
        data = {
            'old_password': 'wrongpassword',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_user_change_password_mismatch(self):
        """Test password change with password mismatch"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('user_change_password')
        data = {
            'old_password': 'password123',
            'new_password': 'newpassword123',
            'confirm_password': 'differentpassword'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_user_change_password_unauthorized(self):
        """Test password change without authentication"""
        url = reverse('user_change_password')
        data = {
            'old_password': 'password123',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_verification_success(self):
        """Test successful user verification"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('user_verification')
        data = {
            'verification_code': '123456'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_user_verification_unauthorized(self):
        """Test user verification without authentication"""
        url = reverse('user_verification')
        data = {
            'verification_code': '123456'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_resend_verification_success(self):
        """Test successful resend verification"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('user_resend_verification')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_user_resend_verification_unauthorized(self):
        """Test resend verification without authentication"""
        url = reverse('user_resend_verification')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_user_forgot_password_success(self):
        """Test successful forgot password"""
        url = reverse('user_forgot_password')
        data = {
            'email': 'test@example.com'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_user_forgot_password_invalid_email(self):
        """Test forgot password with invalid email"""
        url = reverse('user_forgot_password')
        data = {
            'email': 'nonexistent@example.com'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_user_reset_password_success(self):
        """Test successful password reset"""
        url = reverse('user_reset_password')
        data = {
            'token': 'valid_reset_token',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_user_reset_password_invalid_token(self):
        """Test password reset with invalid token"""
        url = reverse('user_reset_password')
        data = {
            'token': 'invalid_token',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_user_reset_password_mismatch(self):
        """Test password reset with password mismatch"""
        url = reverse('user_reset_password')
        data = {
            'token': 'valid_reset_token',
            'new_password': 'newpassword123',
            'confirm_password': 'differentpassword'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_user_delete_account_success(self):
        """Test successful account deletion"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('user_delete_account')
        data = {
            'password': 'password123',
            'reason': 'No longer needed'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_user_delete_account_wrong_password(self):
        """Test account deletion with wrong password"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('user_delete_account')
        data = {
            'password': 'wrongpassword',
            'reason': 'No longer needed'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_user_delete_account_unauthorized(self):
        """Test account deletion without authentication"""
        url = reverse('user_delete_account')
        data = {
            'password': 'password123',
            'reason': 'No longer needed'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        url = reverse('user_register')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        url = reverse('user_register')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_long_username(self):
        """Test edge case with very long username"""
        url = reverse('user_register')
        data = {
            'username': 'a' * 1000,  # Very long username
            'email': 'test@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_special_characters_in_username(self):
        """Test edge case with special characters in username"""
        url = reverse('user_register')
        data = {
            'username': 'test_user!@#',
            'email': 'test@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_unicode_in_name(self):
        """Test edge case with unicode characters in name"""
        url = reverse('user_register')
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'password123',
            'confirm_password': 'password123',
            'first_name': 'Test ✅',
            'last_name': 'User 🚀'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class AuthenticationModelTestCase(TestCase):
    """Test cases for Authentication models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
    
    def test_email_creation(self):
        """Test Email creation"""
        email = Email.objects.create(
            email='test@example.com',
            is_verified=True,
            is_primary=True,
            created_by=self.user
        )
        
        self.assertEqual(email.email, 'test@example.com')
        self.assertTrue(email.is_verified)
        self.assertTrue(email.is_primary)
        self.assertEqual(email.created_by, self.user)
        self.assertIsNotNone(email.created_at)
        self.assertIsNotNone(email.updated_at)
    
    def test_email_str(self):
        """Test Email string representation"""
        email = Email.objects.create(
            email='test@example.com',
            is_verified=True,
            is_primary=True,
            created_by=self.user
        )
        
        expected_str = f"Email {email.pk} - {email.email}"
        self.assertEqual(str(email), expected_str)
    
    def test_email_get_email_summary(self):
        """Test Email get_email_summary method"""
        email = Email.objects.create(
            email='test@example.com',
            is_verified=True,
            is_primary=True,
            created_by=self.user
        )
        
        summary = email.get_email_summary()
        
        self.assertEqual(summary['email'], 'test@example.com')
        self.assertTrue(summary['is_verified'])
        self.assertTrue(summary['is_primary'])
        self.assertEqual(summary['created_by'], self.user.id)
        self.assertIsNotNone(summary['created_at'])
    
    def test_mobile_number_creation(self):
        """Test MobileNumber creation"""
        mobile = MobileNumber.objects.create(
            mobile_number='+1234567890',
            is_verified=True,
            is_primary=True,
            created_by=self.user
        )
        
        self.assertEqual(mobile.mobile_number, '+1234567890')
        self.assertTrue(mobile.is_verified)
        self.assertTrue(mobile.is_primary)
        self.assertEqual(mobile.created_by, self.user)
        self.assertIsNotNone(mobile.created_at)
        self.assertIsNotNone(mobile.updated_at)
    
    def test_mobile_number_str(self):
        """Test MobileNumber string representation"""
        mobile = MobileNumber.objects.create(
            mobile_number='+1234567890',
            is_verified=True,
            is_primary=True,
            created_by=self.user
        )
        
        expected_str = f"Mobile {mobile.pk} - {mobile.mobile_number}"
        self.assertEqual(str(mobile), expected_str)
    
    def test_mobile_number_get_mobile_summary(self):
        """Test MobileNumber get_mobile_summary method"""
        mobile = MobileNumber.objects.create(
            mobile_number='+1234567890',
            is_verified=True,
            is_primary=True,
            created_by=self.user
        )
        
        summary = mobile.get_mobile_summary()
        
        self.assertEqual(summary['mobile_number'], '+1234567890')
        self.assertTrue(summary['is_verified'])
        self.assertTrue(summary['is_primary'])
        self.assertEqual(summary['created_by'], self.user.id)
        self.assertIsNotNone(summary['created_at'])
    
    def test_otp_creation(self):
        """Test OTP creation"""
        otp = OTP.objects.create(
            otp='123456',
            otp_type='E',
            otp_for='email_verification',
            is_verified=False,
            expires_at=timezone.now() + timedelta(minutes=10),
            created_by=self.user
        )
        
        self.assertEqual(otp.otp, '123456')
        self.assertEqual(otp.otp_type, 'E')
        self.assertEqual(otp.otp_for, 'email_verification')
        self.assertFalse(otp.is_verified)
        self.assertIsNotNone(otp.expires_at)
        self.assertEqual(otp.created_by, self.user)
        self.assertIsNotNone(otp.created_at)
        self.assertIsNotNone(otp.updated_at)
    
    def test_otp_str(self):
        """Test OTP string representation"""
        otp = OTP.objects.create(
            otp='123456',
            otp_type='E',
            otp_for='email_verification',
            is_verified=False,
            expires_at=timezone.now() + timedelta(minutes=10),
            created_by=self.user
        )
        
        expected_str = f"OTP {otp.pk} - {otp.otp_type}"
        self.assertEqual(str(otp), expected_str)
    
    def test_otp_otp_type_choices(self):
        """Test OTP otp type choices"""
        choices = OTP.OTP_TYPE_CHOICES
        
        self.assertIn(('E', 'Email'), choices)
        self.assertIn(('M', 'Mobile'), choices)
    
    def test_otp_otp_for_choices(self):
        """Test OTP otp for choices"""
        choices = OTP.OTP_FOR_CHOICES
        
        self.assertIn(('email_verification', 'Email Verification'), choices)
        self.assertIn(('password_reset', 'Password Reset'), choices)
        self.assertIn(('mobile_verification', 'Mobile Verification'), choices)
    
    def test_otp_is_expired(self):
        """Test OTP is_expired method"""
        # Test non-expired OTP
        otp = OTP.objects.create(
            otp='123456',
            otp_type='E',
            otp_for='email_verification',
            is_verified=False,
            expires_at=timezone.now() + timedelta(minutes=10),
            created_by=self.user
        )
        
        self.assertFalse(otp.is_expired())
        
        # Test expired OTP
        expired_otp = OTP.objects.create(
            otp='123456',
            otp_type='E',
            otp_for='email_verification',
            is_verified=False,
            expires_at=timezone.now() - timedelta(minutes=10),
            created_by=self.user
        )
        
        self.assertTrue(expired_otp.is_expired())
    
    def test_otp_get_otp_summary(self):
        """Test OTP get_otp_summary method"""
        otp = OTP.objects.create(
            otp='123456',
            otp_type='E',
            otp_for='email_verification',
            is_verified=False,
            expires_at=timezone.now() + timedelta(minutes=10),
            created_by=self.user
        )
        
        summary = otp.get_otp_summary()
        
        self.assertEqual(summary['otp'], '123456')
        self.assertEqual(summary['otp_type'], 'E')
        self.assertEqual(summary['otp_for'], 'email_verification')
        self.assertFalse(summary['is_verified'])
        self.assertIsNotNone(summary['expires_at'])
        self.assertEqual(summary['created_by'], self.user.id)
        self.assertIsNotNone(summary['created_at'])