"""
Comprehensive tests for CoreAdmin app
Tests all admin functionality including authentication, 2FA, activity logging, and management features
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json
from unittest.mock import patch, MagicMock
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
import pyotp
import base64

from .models import AdminUserProfile, AdminActivityLog, AdminSession
from .serializers import (
    AdminLoginSerializer, Admin2FASetupSerializer, Admin2FAVerifySerializer,
    Admin2FAEnableSerializer, Admin2FADisableSerializer, AdminLogoutSerializer,
    AdminProfileSerializer, AdminActivityLogSerializer, AdminSessionSerializer,
    AdminUserCreateSerializer, AdminUserUpdateSerializer, AdminPasswordChangeSerializer
)


class CoreAdminAPITestCase(APITestCase):
    """Test cases for CoreAdmin API endpoints"""
    
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
        
        # Create admin groups
        self.superadmin_group = Group.objects.create(name='SuperAdmin')
        self.moderator_group = Group.objects.create(name='Moderator')
        
        # Create admin profiles
        self.superadmin_profile = AdminUserProfile.objects.create(
            user=self.admin_user,
            admin_group='superadmin',
            is_active=True
        )
        
        # Add user to groups
        self.admin_user.groups.add(self.superadmin_group)
    
    def test_admin_login_success(self):
        """Test successful admin login"""
        url = reverse('admin_login')
        data = {
            'email': self.admin_user.email,
            'password': 'admin123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('user', response.data)
        self.assertIn('temporary_token', response.data)
        self.assertIn('requires_2fa', response.data)
    
    def test_admin_login_invalid_credentials(self):
        """Test admin login with invalid credentials"""
        url = reverse('admin_login')
        data = {
            'email': self.admin_user.email,
            'password': 'wrongpassword'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
    
    def test_admin_login_non_admin_user(self):
        """Test admin login with non-admin user"""
        url = reverse('admin_login')
        data = {
            'email': self.user.email,
            'password': 'password123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
    
    def test_admin_login_inactive_user(self):
        """Test admin login with inactive user"""
        self.admin_user.is_active = False
        self.admin_user.save()
        
        url = reverse('admin_login')
        data = {
            'email': self.admin_user.email,
            'password': 'admin123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
    
    def test_2fa_setup_success(self):
        """Test successful 2FA setup"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_2fa_setup')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user_id', response.data)
        self.assertIn('email', response.data)
        self.assertIn('secret_key', response.data)
        self.assertIn('qr_code', response.data)
        self.assertIn('backup_codes', response.data)
    
    def test_2fa_setup_unauthorized(self):
        """Test 2FA setup without authentication"""
        url = reverse('admin_2fa_setup')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_2fa_verify_success(self):
        """Test successful 2FA verification"""
        # Enable 2FA for admin user
        self.superadmin_profile.is_2fa_enabled = True
        self.superadmin_profile.set_two_factor_secret('JBSWY3DPEHPK3PXP')
        self.superadmin_profile.save()
        
        # Generate valid TOTP code
        totp = pyotp.TOTP('JBSWY3DPEHPK3PXP')
        valid_code = totp.now()
        
        url = reverse('admin_2fa_verify')
        data = {
            'user_id': self.admin_user.id,
            'totp_code': valid_code
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertIn('user', response.data)
    
    def test_2fa_verify_invalid_code(self):
        """Test 2FA verification with invalid code"""
        # Enable 2FA for admin user
        self.superadmin_profile.is_2fa_enabled = True
        self.superadmin_profile.set_two_factor_secret('JBSWY3DPEHPK3PXP')
        self.superadmin_profile.save()
        
        url = reverse('admin_2fa_verify')
        data = {
            'user_id': self.admin_user.id,
            'totp_code': '123456'  # Invalid code
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
    
    def test_2fa_enable_success(self):
        """Test successful 2FA enable"""
        self.client.force_authenticate(user=self.admin_user)
        
        # Setup 2FA first
        self.superadmin_profile.set_two_factor_secret('JBSWY3DPEHPK3PXP')
        self.superadmin_profile.save()
        
        # Generate valid TOTP code
        totp = pyotp.TOTP('JBSWY3DPEHPK3PXP')
        valid_code = totp.now()
        
        url = reverse('admin_2fa_enable')
        data = {'totp_code': valid_code}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('backup_codes', response.data)
        
        # Verify 2FA is enabled
        self.superadmin_profile.refresh_from_db()
        self.assertTrue(self.superadmin_profile.is_2fa_enabled)
    
    def test_2fa_disable_success(self):
        """Test successful 2FA disable"""
        # Enable 2FA first
        self.superadmin_profile.is_2fa_enabled = True
        self.superadmin_profile.set_two_factor_secret('JBSWY3DPEHPK3PXP')
        self.superadmin_profile.save()
        
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_2fa_disable')
        data = {'password': 'admin123'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify 2FA is disabled
        self.superadmin_profile.refresh_from_db()
        self.assertFalse(self.superadmin_profile.is_2fa_enabled)
    
    def test_2fa_disable_wrong_password(self):
        """Test 2FA disable with wrong password"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_2fa_disable')
        data = {'password': 'wrongpassword'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
    
    def test_admin_logout_success(self):
        """Test successful admin logout"""
        # First login to get tokens
        refresh = RefreshToken.for_user(self.admin_user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Authenticate with access token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        url = reverse('admin_logout')
        data = {'refresh_token': refresh_token}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
    
    def test_admin_logout_invalid_token(self):
        """Test admin logout with invalid token"""
        url = reverse('admin_logout')
        data = {'refresh_token': 'invalid_token'}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_admin_profile_success(self):
        """Test successful admin profile retrieval"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertIn('user', response.data)
        self.assertIn('admin_group', response.data)
        self.assertIn('is_2fa_enabled', response.data)
    
    def test_admin_profile_unauthorized(self):
        """Test admin profile without authentication"""
        url = reverse('admin_profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_change_password_success(self):
        """Test successful password change"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_change_password')
        data = {
            'old_password': 'admin123',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify password was changed
        user = User.objects.get(id=self.admin_user.id)
        self.assertTrue(user.check_password('newpassword123'))
    
    def test_change_password_wrong_old_password(self):
        """Test password change with wrong old password"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_change_password')
        data = {
            'old_password': 'wrongpassword',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('old_password', response.data)
    
    def test_change_password_mismatch(self):
        """Test password change with mismatched passwords"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_change_password')
        data = {
            'old_password': 'admin123',
            'new_password': 'newpassword123',
            'confirm_password': 'differentpassword'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)
    
    def test_activity_logs_success(self):
        """Test successful activity logs retrieval"""
        # Create some activity logs
        AdminActivityLog.log_activity(
            user=self.admin_user,
            activity_type='login',
            description='Admin logged in',
            ip_address='127.0.0.1'
        )
        
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_activity_logs')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_activity_logs_unauthorized(self):
        """Test activity logs without authentication"""
        url = reverse('admin_activity_logs')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_sessions_success(self):
        """Test successful sessions retrieval"""
        # Create a session
        AdminSession.objects.create(
            user=self.admin_user,
            session_key='test_session_key',
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
        
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_sessions')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertGreater(len(response.data['results']), 0)
    
    def test_sessions_unauthorized(self):
        """Test sessions without authentication"""
        url = reverse('admin_sessions')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_create_admin_user_success(self):
        """Test successful admin user creation"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_user_create')
        data = {
            'email': 'newadmin@example.com',
            'first_name': 'New',
            'last_name': 'Admin',
            'password': 'newadmin123',
            'admin_group': 'moderator'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        
        # Verify user was created
        user = User.objects.get(email='newadmin@example.com')
        self.assertTrue(user.is_staff)
        self.assertTrue(hasattr(user, 'admin_profile'))
    
    def test_create_admin_user_duplicate_email(self):
        """Test admin user creation with duplicate email"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_user_create')
        data = {
            'email': self.admin_user.email,  # Existing email
            'first_name': 'New',
            'last_name': 'Admin',
            'password': 'newadmin123',
            'admin_group': 'moderator'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)
    
    def test_create_admin_user_unauthorized(self):
        """Test admin user creation without authentication"""
        url = reverse('admin_user_create')
        data = {
            'email': 'newadmin@example.com',
            'first_name': 'New',
            'last_name': 'Admin',
            'password': 'newadmin123',
            'admin_group': 'moderator'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_update_admin_user_success(self):
        """Test successful admin user update"""
        # Create another admin user to update
        other_admin = User.objects.create_user(
            username='otheradmin',
            email='otheradmin@example.com',
            password='password123',
            first_name='Other',
            last_name='Admin',
            is_staff=True
        )
        
        other_profile = AdminUserProfile.objects.create(
            user=other_admin,
            admin_group='moderator',
            is_active=True
        )
        
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_user_update', kwargs={'user_id': other_admin.id})
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'admin_group': 'superadmin',
            'is_active': False
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        
        # Verify user was updated
        other_admin.refresh_from_db()
        other_profile.refresh_from_db()
        self.assertEqual(other_admin.first_name, 'Updated')
        self.assertEqual(other_admin.last_name, 'Name')
        self.assertEqual(other_profile.admin_group, 'superadmin')
        self.assertFalse(other_profile.is_active)
    
    def test_update_admin_user_not_found(self):
        """Test admin user update with non-existent user"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_user_update', kwargs={'user_id': 99999})
        data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }
        
        response = self.client.put(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_edge_case_empty_data(self):
        """Test edge case with empty request data"""
        url = reverse('admin_login')
        response = self.client.post(url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_malformed_json(self):
        """Test edge case with malformed JSON"""
        url = reverse('admin_login')
        response = self.client.post(
            url, 
            'invalid json', 
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_very_long_email(self):
        """Test edge case with very long email"""
        url = reverse('admin_user_create')
        data = {
            'email': 'a' * 300 + '@example.com',  # Very long email
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'password123',
            'admin_group': 'moderator'
        }
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_edge_case_special_characters_in_password(self):
        """Test edge case with special characters in password"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_user_create')
        data = {
            'email': 'special@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password': '!@#$%^&*()_+-=[]{}|;:,.<>?',
            'admin_group': 'moderator'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_edge_case_unicode_in_names(self):
        """Test edge case with unicode characters in names"""
        self.client.force_authenticate(user=self.admin_user)
        
        url = reverse('admin_user_create')
        data = {
            'email': 'unicode@example.com',
            'first_name': 'José',
            'last_name': 'García',
            'password': 'password123',
            'admin_group': 'moderator'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class CoreAdminModelTestCase(TestCase):
    """Test cases for CoreAdmin models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123',
            first_name='Test',
            last_name='User'
        )
        
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin123',
            first_name='Admin',
            last_name='User',
            is_staff=True
        )
    
    def test_admin_user_profile_creation(self):
        """Test AdminUserProfile creation"""
        profile = AdminUserProfile.objects.create(
            user=self.admin_user,
            admin_group='superadmin',
            is_active=True
        )
        
        self.assertEqual(profile.user, self.admin_user)
        self.assertEqual(profile.admin_group, 'superadmin')
        self.assertTrue(profile.is_active)
        self.assertFalse(profile.is_2fa_enabled)
        self.assertIsNotNone(profile.created_at)
    
    def test_admin_user_profile_str(self):
        """Test AdminUserProfile string representation"""
        profile = AdminUserProfile.objects.create(
            user=self.admin_user,
            admin_group='superadmin',
            is_active=True
        )
        
        expected_str = f"Admin Profile for {self.admin_user.get_full_name()}"
        self.assertEqual(str(profile), expected_str)
    
    def test_admin_activity_log_creation(self):
        """Test AdminActivityLog creation"""
        log = AdminActivityLog.log_activity(
            user=self.admin_user,
            activity_type='login',
            description='Admin logged in',
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
        
        self.assertEqual(log.user, self.admin_user)
        self.assertEqual(log.activity_type, 'login')
        self.assertEqual(log.description, 'Admin logged in')
        self.assertEqual(log.ip_address, '127.0.0.1')
        self.assertEqual(log.user_agent, 'Test Agent')
        self.assertIsNotNone(log.timestamp)
    
    def test_admin_activity_log_str(self):
        """Test AdminActivityLog string representation"""
        log = AdminActivityLog.log_activity(
            user=self.admin_user,
            activity_type='login',
            description='Admin logged in'
        )
        
        expected_str = f"Activity Log {log.id} - {self.admin_user.get_full_name()}"
        self.assertEqual(str(log), expected_str)
    
    def test_admin_session_creation(self):
        """Test AdminSession creation"""
        session = AdminSession.objects.create(
            user=self.admin_user,
            session_key='test_session_key',
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
        
        self.assertEqual(session.user, self.admin_user)
        self.assertEqual(session.session_key, 'test_session_key')
        self.assertEqual(session.ip_address, '127.0.0.1')
        self.assertEqual(session.user_agent, 'Test Agent')
        self.assertTrue(session.is_active)
        self.assertIsNotNone(session.created_at)
    
    def test_admin_session_str(self):
        """Test AdminSession string representation"""
        session = AdminSession.objects.create(
            user=self.admin_user,
            session_key='test_session_key',
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
        
        expected_str = f"Session {session.id} - {self.admin_user.get_full_name()}"
        self.assertEqual(str(session), expected_str)
    
    def test_admin_session_is_expired(self):
        """Test AdminSession is_expired method"""
        # Create session with recent activity
        session = AdminSession.objects.create(
            user=self.admin_user,
            session_key='test_session_key',
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
        
        self.assertFalse(session.is_expired())
        
        # Create session with old activity
        old_session = AdminSession.objects.create(
            user=self.admin_user,
            session_key='old_session_key',
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
        old_session.last_activity = timezone.now() - timedelta(hours=25)
        old_session.save()
        
        self.assertTrue(old_session.is_expired())
    
    def test_2fa_secret_encryption(self):
        """Test 2FA secret encryption and decryption"""
        profile = AdminUserProfile.objects.create(
            user=self.admin_user,
            admin_group='superadmin',
            is_active=True
        )
        
        secret = 'JBSWY3DPEHPK3PXP'
        profile.set_two_factor_secret(secret)
        profile.save()
        
        # Verify secret is encrypted in database
        profile.refresh_from_db()
        self.assertNotEqual(profile.two_factor_secret, secret)
        
        # Verify decryption works
        decrypted_secret = profile.get_two_factor_secret()
        self.assertEqual(decrypted_secret, secret)
    
    def test_2fa_totp_verification(self):
        """Test 2FA TOTP verification"""
        profile = AdminUserProfile.objects.create(
            user=self.admin_user,
            admin_group='superadmin',
            is_active=True
        )
        
        secret = 'JBSWY3DPEHPK3PXP'
        profile.set_two_factor_secret(secret)
        profile.save()
        
        # Generate valid TOTP code
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        
        # Test valid code
        self.assertTrue(profile.verify_totp(valid_code))
        
        # Test invalid code
        self.assertFalse(profile.verify_totp('123456'))
    
    def test_2fa_qr_code_generation(self):
        """Test 2FA QR code generation"""
        profile = AdminUserProfile.objects.create(
            user=self.admin_user,
            admin_group='superadmin',
            is_active=True
        )
        
        secret = 'JBSWY3DPEHPK3PXP'
        profile.set_two_factor_secret(secret)
        profile.save()
        
        qr_code_data = profile.generate_qr_code()
        
        self.assertIsInstance(qr_code_data, bytes)
        self.assertGreater(len(qr_code_data), 0)
    
    def test_backup_codes_generation(self):
        """Test backup codes generation"""
        profile = AdminUserProfile.objects.create(
            user=self.admin_user,
            admin_group='superadmin',
            is_active=True
        )
        
        backup_codes = profile.generate_backup_codes()
        
        self.assertIsInstance(backup_codes, list)
        self.assertEqual(len(backup_codes), 10)
        
        # Verify all codes are unique
        self.assertEqual(len(set(backup_codes)), 10)
        
        # Verify codes are 8 characters long
        for code in backup_codes:
            self.assertEqual(len(code), 8)
    
    def test_backup_codes_verification(self):
        """Test backup codes verification"""
        profile = AdminUserProfile.objects.create(
            user=self.admin_user,
            admin_group='superadmin',
            is_active=True
        )
        
        backup_codes = profile.generate_backup_codes()
        profile.save()
        
        # Test valid backup code
        self.assertTrue(profile.verify_backup_code(backup_codes[0]))
        
        # Test invalid backup code
        self.assertFalse(profile.verify_backup_code('INVALID'))
        
        # Test used backup code
        self.assertFalse(profile.verify_backup_code(backup_codes[0]))
    
    def test_admin_group_choices(self):
        """Test admin group choices"""
        choices = AdminUserProfile.ADMIN_GROUP_CHOICES
        
        self.assertIn(('superadmin', 'Super Admin'), choices)
        self.assertIn(('moderator', 'Moderator'), choices)
    
    def test_activity_type_choices(self):
        """Test activity type choices"""
        choices = AdminActivityLog.ACTIVITY_TYPE_CHOICES
        
        self.assertIn(('login', 'Login'), choices)
        self.assertIn(('logout', 'Logout'), choices)
        self.assertIn(('password_change', 'Password Change'), choices)
        self.assertIn(('profile_update', 'Profile Update'), choices)
        self.assertIn(('user_management', 'User Management'), choices)
        self.assertIn(('system_config', 'System Configuration'), choices)
        self.assertIn(('other', 'Other'), choices)
