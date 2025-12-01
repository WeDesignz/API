import requests
import logging
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from .models import PinterestIntegration

logger = logging.getLogger(__name__)


class PinterestService:
    """
    Service to interact with Pinterest API for posting pins.
    Uses PinterestIntegration model to get tokens.
    """
    
    @classmethod
    def get_api_base_url(cls):
        """Get the appropriate API base URL (sandbox or production)."""
        use_sandbox = getattr(settings, 'PINTEREST_USE_SANDBOX', True)
        if use_sandbox:
            return "https://api-sandbox.pinterest.com/v5"
        return "https://api.pinterest.com/v5"
    
    @property
    def API_BASE_URL(self):
        """Dynamic API base URL based on settings."""
        return self.__class__.get_api_base_url()
    
    def __init__(self):
        """Initialize Pinterest service with tokens from database."""
        self.integration = PinterestIntegration.get_instance()
        
        if not self.integration.access_token:
            # Fallback to env var for initial setup
            access_token = getattr(settings, 'PINTEREST_ACCESS_TOKEN', None)
            if access_token:
                self.integration.access_token = access_token
                self.integration.save(update_fields=['access_token'])
            else:
                raise ImproperlyConfigured("Pinterest access token not configured. Please authorize Pinterest first.")
        
        if not self.integration.board_id:
            # Fallback to env var for initial setup
            board_id = getattr(settings, 'PINTEREST_BOARD_ID', None)
            if board_id:
                self.integration.board_id = board_id
                self.integration.save(update_fields=['board_id'])
            else:
                raise ImproperlyConfigured("Pinterest board ID not configured. Please set board ID first.")
        
        if not self.integration.is_enabled:
            raise ImproperlyConfigured("Pinterest integration is disabled. Enable it in settings.")
        
        if not self.integration.is_token_valid():
            raise ImproperlyConfigured("Pinterest access token has expired. Please re-authorize.")
    
    def create_pin(self, image_url, title, description, link=None):
        """
        Create a pin on Pinterest.
        
        Args:
            image_url: Absolute URL to the image (must be publicly accessible)
            title: Pin title (max 100 chars)
            description: Pin description (max 800 chars)
            link: Optional link URL (e.g., to your design page)
        
        Returns:
            dict: Pin data if successful, None otherwise
        """
        url = f"{self.API_BASE_URL}/pins"
        
        headers = {
            "Authorization": f"Bearer {self.integration.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "board_id": self.integration.board_id,
            "media_source": {
                "source_type": "image_url",
                "url": image_url
            },
            "title": (title[:100] if title else "Design"),  # Pinterest limits title to 100 chars
            "description": (description[:800] if description else "")  # Limit to 800 chars
        }
        
        # Only add link if it's provided and valid (HTTPS, not localhost)
        if link:
            # Validate link - must be HTTPS and not localhost
            if (link.startswith('https://') and 
                'localhost' not in link.lower() and 
                '127.0.0.1' not in link):
                payload["link"] = link
                logger.debug(f"Adding link to Pinterest pin: {link}")
            else:
                logger.warning(f"Invalid link format for Pinterest (skipping): {link}")
                # Don't add invalid link - Pinterest allows pins without links
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            pin_data = response.json()
            pin_id = pin_data.get('id')
            pin_url = pin_data.get('url', '')
            
            logger.info(f"Pin created successfully: {pin_id}")
            
            # Update integration success tracking
            self.integration.update_success()
            
            return {
                'id': pin_id,
                'url': pin_url,
                'data': pin_data
            }
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('message', error_data.get('error_description', str(e)))
                    logger.error(f"Pinterest API Error: {error_data}")
                except:
                    logger.error(f"Response: {e.response.text}")
                    error_msg = e.response.text[:500]  # Limit error message length
            
            # Update integration error tracking
            self.integration.update_error(error_msg)
            
            logger.error(f"Failed to create Pinterest pin: {error_msg}")
            return None
    
    def get_boards(self):
        """
        Get list of boards for the authenticated user.
        Useful for finding board_id.
        
        Returns:
            list: List of board dictionaries with id, name, etc.
        """
        url = f"{self.API_BASE_URL}/boards"
        
        headers = {
            "Authorization": f"Bearer {self.integration.access_token}",
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            boards = data.get('items', [])
            
            return boards
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('message', error_data.get('error_description', str(e)))
                    logger.error(f"Pinterest API Error: {error_data}")
                except:
                    logger.error(f"Response: {e.response.text}")
            
            self.integration.update_error(error_msg)
            logger.error(f"Failed to get Pinterest boards: {error_msg}")
            return None
    
    @classmethod
    def get_boards_with_token(cls, access_token):
        """
        Get list of boards using an access token.
        This doesn't require board_id to be set, so it can be used during initial setup.
        
        Args:
            access_token: Pinterest OAuth access token
        
        Returns:
            list: List of board dictionaries with id, name, etc., or None if error
        """
        url = f"{cls.get_api_base_url()}/boards"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            boards = data.get('items', [])
            
            return boards
            
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get('message', error_data.get('error_description', str(e)))
                    logger.error(f"Pinterest API Error: {error_data}")
                except:
                    logger.error(f"Response: {e.response.text}")
            
            logger.error(f"Failed to get Pinterest boards: {error_msg}")
            return None
    
    def refresh_access_token(self):
        """
        Refresh the access token using refresh token.
        Note: Pinterest API v5 may not support refresh tokens in all cases.
        Check Pinterest documentation for current refresh token flow.
        
        Returns:
            bool: True if token was refreshed, False otherwise
        """
        if not self.integration.refresh_token:
            logger.warning("No refresh token available for Pinterest")
            return False
        
        # Pinterest token refresh endpoint (verify with current API docs)
        use_sandbox = getattr(settings, 'PINTEREST_USE_SANDBOX', True)
        if use_sandbox:
            url = "https://api-sandbox.pinterest.com/v5/oauth/token"
        else:
            url = "https://api.pinterest.com/v5/oauth/token"
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.integration.refresh_token,
            'client_id': getattr(settings, 'PINTEREST_APP_ID', ''),
            'client_secret': getattr(settings, 'PINTEREST_APP_SECRET', ''),
        }
        
        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            self.integration.access_token = token_data.get('access_token')
            if 'refresh_token' in token_data:
                self.integration.refresh_token = token_data.get('refresh_token')
            if 'expires_in' in token_data:
                from django.utils import timezone
                from datetime import timedelta
                self.integration.token_expires_at = timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))
            
            self.integration.save()
            logger.info("Pinterest access token refreshed successfully")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh Pinterest token: {str(e)}")
            return False

