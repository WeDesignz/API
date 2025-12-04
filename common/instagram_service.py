import requests
import logging
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from .models import InstagramIntegration

logger = logging.getLogger(__name__)


class InstagramService:
    """
    Service to interact with Instagram Graph API for posting.
    Uses InstagramIntegration model to get tokens.
    
    Note: Instagram Graph API requires:
    1. Facebook App with Instagram Basic Display or Instagram Graph API permissions
    2. Long-lived access token
    3. Instagram Business or Creator account
    """
    
    # Instagram Graph API uses Facebook Graph API endpoints
    # Base URL should be graph.facebook.com, not graph.instagram.com
    API_BASE_URL = "https://graph.facebook.com"
    API_VERSION = "v18.0"
    
    @property
    def base_url(self):
        """Get the base URL for Instagram Graph API."""
        return f"{self.API_BASE_URL}/{self.API_VERSION}"
    
    def __init__(self):
        """Initialize Instagram service with tokens from database."""
        self.integration = InstagramIntegration.get_instance()
        
        if not self.integration.access_token:
            # Fallback to env var for initial setup
            access_token = getattr(settings, 'INSTAGRAM_ACCESS_TOKEN', None)
            if access_token:
                self.integration.access_token = access_token
                self.integration.save(update_fields=['access_token'])
            else:
                raise ImproperlyConfigured("Instagram access token not configured. Please authorize Instagram first.")
        
        if not self.integration.is_enabled:
            raise ImproperlyConfigured("Instagram integration is disabled. Enable it in settings.")
        
        if not self.integration.is_token_valid():
            raise ImproperlyConfigured("Instagram access token has expired. Please re-authorize.")
    
    def get_user_info(self):
        """
        Get Instagram user information.
        
        Returns:
            dict: User data if successful, None otherwise
        """
        # Use the user_id endpoint instead of /me
        # Note: 'username' field is deprecated in Instagram Graph API v2.0+
        if not self.integration.user_id:
            logger.error("Cannot get user info: user_id not set")
            return None
        
        url = f"{self.base_url}/{self.integration.user_id}"
        
        params = {
            'fields': 'id',  # Only request 'id' - username is deprecated
            'access_token': self.integration.access_token
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            user_data = response.json()
            
            # Update integration with user info
            if 'id' in user_data:
                self.integration.user_id = user_data['id']
            # Username is deprecated, so we can't get it from API
            # Leave username as is (it might be set from OAuth callback or remain None)
            self.integration.save(update_fields=['user_id'])
            
            logger.info(f"Instagram user info retrieved: ID {user_data.get('id')}")
            return user_data
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    logger.error(f"Instagram API Error: {error_data}")
                except:
                    logger.error(f"Response: {e.response.text}")
                    error_msg = e.response.text[:500]
            
            self.integration.update_error(error_msg)
            logger.error(f"Failed to get Instagram user info: {error_msg}")
            return None
    
    def create_media_container(self, image_url, caption, is_story=False):
        """
        Create a media container for Instagram post.
        This is step 1 of the Instagram posting process.
        
        Args:
            image_url: Absolute URL to the image (must be publicly accessible)
            caption: Caption for the post (max 2200 chars)
            is_story: Whether this is a story (True) or regular post (False)
        
        Returns:
            dict: Container ID if successful, None otherwise
        """
        if not self.integration.user_id:
            # Try to get user info first
            user_info = self.get_user_info()
            if not user_info:
                logger.error("Cannot create media container: user_id not available")
                return None
        
        url = f"{self.base_url}/{self.integration.user_id}/media"
        
        params = {
            'image_url': image_url,
            'caption': (caption[:2200] if caption else ""),  # Instagram limits caption to 2200 chars
            'access_token': self.integration.access_token
        }
        
        # For stories, use different endpoint
        if is_story:
            url = f"{self.base_url}/{self.integration.user_id}/media"
            params['media_type'] = 'STORIES'
        
        try:
            response = requests.post(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            container_id = data.get('id')
            
            logger.info(f"Instagram media container created: {container_id}")
            return {
                'id': container_id,
                'status_code': data.get('status_code'),
                'data': data
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    logger.error(f"Instagram API Error: {error_data}")
                except:
                    logger.error(f"Response: {e.response.text}")
                    error_msg = e.response.text[:500]
            
            self.integration.update_error(error_msg)
            logger.error(f"Failed to create Instagram media container: {error_msg}")
            return None
    
    def publish_media(self, creation_id, is_story=False):
        """
        Publish the media container to Instagram.
        This is step 2 of the Instagram posting process.
        
        Args:
            creation_id: Container ID from create_media_container
            is_story: Whether this is a story (True) or regular post (False)
        
        Returns:
            dict: Post data if successful, None otherwise
        """
        if not self.integration.user_id:
            logger.error("Cannot publish media: user_id not available")
            return None
        
        url = f"{self.base_url}/{self.integration.user_id}/media_publish"
        
        params = {
            'creation_id': creation_id,
            'access_token': self.integration.access_token
        }
        
        try:
            response = requests.post(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            post_id = data.get('id')
            
            # Build post URL
            post_url = f"https://www.instagram.com/p/{post_id}/" if post_id else None
            
            logger.info(f"Instagram post published: {post_id}")
            
            # Update integration success tracking
            self.integration.update_success()
            
            return {
                'id': post_id,
                'url': post_url,
                'data': data
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    logger.error(f"Instagram API Error: {error_data}")
                except:
                    logger.error(f"Response: {e.response.text}")
                    error_msg = e.response.text[:500]
            
            self.integration.update_error(error_msg)
            logger.error(f"Failed to publish Instagram post: {error_msg}")
            return None
    
    def create_and_publish_post(self, image_url, caption, is_story=False):
        """
        Create and publish an Instagram post in one go.
        This combines create_media_container and publish_media.
        
        Args:
            image_url: Absolute URL to the image (must be publicly accessible)
            caption: Caption for the post (max 2200 chars)
            is_story: Whether this is a story (True) or regular post (False)
        
        Returns:
            dict: Post data if successful, None otherwise
        """
        # Step 1: Create media container
        container_result = self.create_media_container(image_url, caption, is_story)
        if not container_result or not container_result.get('id'):
            return None
        
        creation_id = container_result['id']
        
        # Step 2: Publish the media
        # Note: For stories, publishing might be different or automatic
        if is_story:
            # Stories might be published automatically or require different handling
            # Check Instagram API docs for current story publishing flow
            return self.publish_media(creation_id, is_story)
        else:
            return self.publish_media(creation_id, is_story)
    
    def check_container_status(self, container_id):
        """
        Check the status of a media container.
        Useful for checking if container is ready to publish.
        
        Args:
            container_id: Container ID to check
        
        Returns:
            dict: Status data if successful, None otherwise
        """
        url = f"{self.base_url}/{container_id}"
        
        params = {
            'fields': 'status_code',
            'access_token': self.integration.access_token
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return {
                'status_code': data.get('status_code'),
                'data': data
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    logger.error(f"Instagram API Error: {error_data}")
                except:
                    logger.error(f"Response: {e.response.text}")
            
            logger.error(f"Failed to check Instagram container status: {error_msg}")
            return None
    
    def refresh_access_token(self):
        """
        Refresh the long-lived access token.
        Instagram long-lived tokens expire after 60 days.
        
        Returns:
            bool: True if token was refreshed, False otherwise
        """
        if not self.integration.access_token:
            logger.warning("No access token available for Instagram refresh")
            return False
        
        url = f"{self.base_url}/refresh_access_token"
        
        params = {
            'grant_type': 'ig_refresh_token',
            'access_token': self.integration.access_token
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            self.integration.access_token = token_data.get('access_token')
            
            # Instagram tokens are valid for 60 days
            if 'expires_in' in token_data:
                from django.utils import timezone
                from datetime import timedelta
                self.integration.token_expires_at = timezone.now() + timedelta(seconds=token_data.get('expires_in', 5184000))
            
            self.integration.save()
            logger.info("Instagram access token refreshed successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('error', {}).get('message', str(e))
                    logger.error(f"Instagram API Error: {error_data}")
                except:
                    logger.error(f"Response: {e.response.text}")
            
            logger.error(f"Failed to refresh Instagram token: {error_msg}")
            return False

