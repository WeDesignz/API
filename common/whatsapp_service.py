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
        Send OTP via WhatsApp using approved template.
        Only used for mobile verification OTPs.
        
        Args:
            phone_number: Recipient phone number (with country code)
            otp_code: 6-digit OTP code
            purpose: Purpose of OTP (should be "Mobile Verification")
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Use approved template instead of free-form message
            template_name = getattr(settings, 'WHATSAPP_OTP_TEMPLATE_NAME', 'otp_template')
            
            # Pass OTP code as the first parameter ({{1}} in template)
            parameters = [otp_code]
            
            # Template requires URL button - provide button parameter if needed
            # Check if button requires dynamic URL parameter (vs static URL in template)
            button_requires_param = getattr(settings, 'WHATSAPP_BUTTON_REQUIRES_PARAM', True)
            
            if button_requires_param:
                # Button needs dynamic URL parameter
                button_url = getattr(settings, 'WHATSAPP_BUTTON_URL', 'wedesignz.com')
                
                # Remove protocol if present and ensure it's under 15 characters
                short_url = button_url.replace('https://', '').replace('http://', '')
                if len(short_url) > 15:
                    short_url = 'wedesignz.com'  # 14 characters - under limit
                
                button_parameters = [short_url]
            else:
                # Button URL is static in template - no parameter needed
                button_parameters = None
            
            return WhatsAppService.send_template_message(
                phone_number=phone_number,
                template_name=template_name,
                parameters=parameters,
                button_parameters=button_parameters
            )
            
        except Exception as e:
            logger.error(f"Failed to send OTP via WhatsApp to {phone_number}: {str(e)}")
            return False
    
    @staticmethod
    def send_template_message(phone_number, template_name, parameters=None, button_parameters=None):
        """
        Send a WhatsApp template message (for approved templates).
        
        Args:
            phone_number: Recipient phone number
            template_name: Name of the approved template
            parameters: List of parameters for the template body
            button_parameters: List of parameters for template buttons (if any)
                For URL buttons, provide the URL as a string
                For quick reply buttons, provide the button text
                
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
            
            # Build components array
            components = []
            
            # Add body parameters if provided
            if parameters:
                components.append({
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(param)} for param in parameters
                    ]
                })
            
            # Add button parameters if provided
            # Template requires URL button type (not COPY button)
            if button_parameters:
                for index, button_param in enumerate(button_parameters):
                    button_param_str = str(button_param)
                    
                    # URL button format (required by template)
                    # Parameter type must be "text" with URL in "text" field
                    # URL should be domain only (no protocol) to fit 15-char limit
                    components.append({
                        "type": "button",
                        "sub_type": "url",
                        "index": index,
                        "parameters": [
                            {
                                "type": "text",
                                "text": button_param_str
                            }
                        ]
                    })
            
            # Only add components if we have any
            if components:
                payload["template"]["components"] = components
            
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

