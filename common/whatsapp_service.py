import requests
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class WhatsAppService:
    """
    WhatsApp Business API service for sending messages.
    Handles OTP and other notifications via WhatsApp.
    """
    
    # WhatsApp Business API endpoint
    API_URL = "https://graph.facebook.com/v18.0"
    
    @staticmethod
    def get_phone_number_id():
        """Get WhatsApp Phone Number ID from settings"""
        return getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', None)
    
    @staticmethod
    def get_access_token():
        """Get WhatsApp Access Token from settings"""
        return getattr(settings, 'WHATSAPP_ACCESS_TOKEN', None)
    
    @staticmethod
    def format_phone_number(phone_number):
        """
        Format phone number for WhatsApp API.
        Removes + and spaces, ensures it starts with country code.
        Example: +91 9876543210 -> 919876543210
        """
        # Remove all non-digit characters
        cleaned = ''.join(filter(str.isdigit, phone_number))
        
        # If it doesn't start with country code, assume it's Indian (+91)
        # You can modify this logic based on your requirements
        if len(cleaned) == 10:
            cleaned = '91' + cleaned
        
        return cleaned
    
    @staticmethod
    def send_message(phone_number, message):
        """
        Send a text message via WhatsApp Business API.
        
        Args:
            phone_number: Recipient phone number (with country code, e.g., +919876543210)
            message: Message text to send
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            phone_number_id = WhatsAppService.get_phone_number_id()
            access_token = WhatsAppService.get_access_token()
            
            if not phone_number_id or not access_token:
                logger.error("WhatsApp credentials not configured")
                return False
            
            # Format phone number
            formatted_number = WhatsAppService.format_phone_number(phone_number)
            
            # API endpoint
            url = f"{WhatsAppService.API_URL}/{phone_number_id}/messages"
            
            # Headers
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Request payload
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": formatted_number,
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": message
                }
            }
            
            # Send request
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"WhatsApp message sent successfully to {phone_number}. Message ID: {result.get('messages', [{}])[0].get('id', 'N/A')}")
                return True
            else:
                logger.error(f"WhatsApp API error: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send WhatsApp message to {phone_number}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending WhatsApp message: {str(e)}")
            return False
    
    @staticmethod
    def send_otp_message(phone_number, otp_code, purpose="verification"):
        """
        Send OTP via WhatsApp with properly formatted message.
        Only used for mobile verification OTPs.
        
        Args:
            phone_number: Recipient phone number (with country code)
            otp_code: 6-digit OTP code
            purpose: Purpose of OTP (should be "Mobile Verification")
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Clean, simple message format
            message = f"""Your WeDesignz verification code is: {otp_code}

This code is valid for 10 minutes.

Do not share this code with anyone. WeDesignz will never ask for your OTP.

Thank you,
WeDesignz Team"""

            return WhatsAppService.send_message(phone_number, message)
            
        except Exception as e:
            logger.error(f"Failed to send OTP via WhatsApp to {phone_number}: {str(e)}")
            return False
    
    @staticmethod
    def send_template_message(phone_number, template_name, parameters=None):
        """
        Send a WhatsApp template message (for approved templates).
        
        Args:
            phone_number: Recipient phone number
            template_name: Name of the approved template
            parameters: List of parameters for the template
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            phone_number_id = WhatsAppService.get_phone_number_id()
            access_token = WhatsAppService.get_access_token()
            
            if not phone_number_id or not access_token:
                logger.error("WhatsApp credentials not configured")
                return False
            
            formatted_number = WhatsAppService.format_phone_number(phone_number)
            
            url = f"{WhatsAppService.API_URL}/{phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Build template payload
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": formatted_number,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {
                        "code": "en"
                    }
                }
            }
            
            # Add parameters if provided
            if parameters:
                payload["template"]["components"] = [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": str(param)} for param in parameters
                        ]
                    }
                ]
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"WhatsApp template message sent to {phone_number}")
                return True
            else:
                logger.error(f"WhatsApp template API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send WhatsApp template message: {str(e)}")
            return False

