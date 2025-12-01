from django.shortcuts import redirect
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.utils import timezone
from datetime import timedelta
import requests
import logging

from .models import PinterestIntegration

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def pinterest_oauth_initiate(request):
    """
    Initiate Pinterest OAuth flow.
    Redirects user to Pinterest authorization page.
    """
    app_id = getattr(settings, 'PINTEREST_APP_ID', None)
    redirect_uri = getattr(settings, 'PINTEREST_REDIRECT_URI', None)
    
    if not app_id:
        return JsonResponse({'error': 'Pinterest App ID not configured'}, status=500)
    if not redirect_uri:
        return JsonResponse({'error': 'Pinterest Redirect URI not configured'}, status=500)
    
    # Build authorization URL
    # URL-encode the redirect_uri for the URL
    from urllib.parse import quote_plus
    # Remove trailing slash for consistency
    redirect_uri_clean = redirect_uri.rstrip('/')
    redirect_uri_encoded = quote_plus(redirect_uri_clean)
    
    auth_url = (
        f"https://www.pinterest.com/oauth/"
        f"?client_id={app_id}"
        f"&redirect_uri={redirect_uri_encoded}"
        f"&response_type=code"
        f"&scope=pins:write,pins:read,boards:read,boards:write"
    )
    
    logger.info(f"Pinterest OAuth authorization URL: client_id={app_id}, redirect_uri={redirect_uri_clean}")
    
    logger.info(f"Redirecting to Pinterest OAuth: {auth_url}")
    return redirect(auth_url)


@api_view(['GET'])
@permission_classes([AllowAny])
@csrf_exempt
def pinterest_oauth_callback(request):
    """
    Handle Pinterest OAuth callback.
    Exchanges authorization code for access token and saves to database.
    """
    code = request.GET.get('code')
    error = request.GET.get('error')
    
    # Get admin webapp URL from settings
    admin_webapp_url = getattr(settings, 'ADMIN_WEBAPP_URL', 'https://admin.wedesignz.com')
    
    if error:
        logger.error(f"Pinterest OAuth error: {error}")
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pinterest Authorization Failed</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 20px;
                    }}
                    .container {{
                        background: white;
                        border-radius: 16px;
                        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                        max-width: 600px;
                        width: 100%;
                        padding: 40px;
                        text-align: center;
                    }}
                    .icon {{
                        width: 80px;
                        height: 80px;
                        margin: 0 auto 24px;
                        background: #fee;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 40px;
                    }}
                    h1 {{
                        color: #dc3545;
                        font-size: 28px;
                        margin-bottom: 16px;
                        font-weight: 600;
                    }}
                    .error-box {{
                        background: #fee;
                        border: 2px solid #fcc;
                        border-radius: 8px;
                        padding: 16px;
                        margin: 24px 0;
                        color: #721c24;
                    }}
                    .error-box strong {{
                        display: block;
                        margin-bottom: 8px;
                        font-size: 14px;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }}
                    .actions {{
                        margin-top: 32px;
                        display: flex;
                        flex-direction: column;
                        gap: 12px;
                    }}
                    .btn {{
                        display: inline-block;
                        padding: 14px 28px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 16px;
                        transition: all 0.3s ease;
                        border: none;
                        cursor: pointer;
                    }}
                    .btn-primary {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    }}
                    .btn-primary:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
                    }}
                    .btn-secondary {{
                        background: #f8f9fa;
                        color: #495057;
                        border: 2px solid #dee2e6;
                    }}
                    .btn-secondary:hover {{
                        background: #e9ecef;
                        border-color: #adb5bd;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="icon">❌</div>
                    <h1>Authorization Failed</h1>
                    <div class="error-box">
                        <strong>Error Details</strong>
                        {error}
                    </div>
                    <p style="color: #6c757d; margin-top: 16px;">
                        There was an issue authorizing your Pinterest account. Please try again.
                    </p>
                    <div class="actions">
                        <a href="/api/pinterest/authorize/" class="btn btn-primary">Try Again</a>
                        <a href="{admin_webapp_url}/settings?tab=pinterest" class="btn btn-secondary">Go to Settings</a>
                    </div>
                </div>
            </body>
            </html>
            """,
            status=400
        )
    
    if not code:
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pinterest Authorization Failed</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 20px;
                    }}
                    .container {{
                        background: white;
                        border-radius: 16px;
                        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                        max-width: 600px;
                        width: 100%;
                        padding: 40px;
                        text-align: center;
                    }}
                    .icon {{
                        width: 80px;
                        height: 80px;
                        margin: 0 auto 24px;
                        background: #fee;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 40px;
                    }}
                    h1 {{
                        color: #dc3545;
                        font-size: 28px;
                        margin-bottom: 16px;
                        font-weight: 600;
                    }}
                    .error-box {{
                        background: #fee;
                        border: 2px solid #fcc;
                        border-radius: 8px;
                        padding: 16px;
                        margin: 24px 0;
                        color: #721c24;
                    }}
                    .actions {{
                        margin-top: 32px;
                        display: flex;
                        flex-direction: column;
                        gap: 12px;
                    }}
                    .btn {{
                        display: inline-block;
                        padding: 14px 28px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 16px;
                        transition: all 0.3s ease;
                    }}
                    .btn-primary {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    }}
                    .btn-primary:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
                    }}
                    .btn-secondary {{
                        background: #f8f9fa;
                        color: #495057;
                        border: 2px solid #dee2e6;
                    }}
                    .btn-secondary:hover {{
                        background: #e9ecef;
                        border-color: #adb5bd;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="icon">⚠️</div>
                    <h1>No Authorization Code</h1>
                    <div class="error-box">
                        No authorization code was received from Pinterest.
                    </div>
                    <p style="color: #6c757d; margin-top: 16px;">
                        Please try authorizing again.
                    </p>
                    <div class="actions">
                        <a href="/api/pinterest/authorize/" class="btn btn-primary">Try Again</a>
                        <a href="{admin_webapp_url}/settings?tab=pinterest" class="btn btn-secondary">Go to Settings</a>
                    </div>
                </div>
            </body>
            </html>
            """,
            status=400
        )
    
    app_id = getattr(settings, 'PINTEREST_APP_ID', None)
    app_secret = getattr(settings, 'PINTEREST_APP_SECRET', None)
    redirect_uri = getattr(settings, 'PINTEREST_REDIRECT_URI', None)
    
    if not app_id or not app_secret:
        admin_webapp_url = getattr(settings, 'ADMIN_WEBAPP_URL', 'https://admin.wedesignz.com')
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Configuration Error</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 20px;
                    }}
                    .container {{
                        background: white;
                        border-radius: 16px;
                        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                        max-width: 600px;
                        width: 100%;
                        padding: 40px;
                        text-align: center;
                    }}
                    .icon {{
                        width: 80px;
                        height: 80px;
                        margin: 0 auto 24px;
                        background: #fff3cd;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 40px;
                    }}
                    h1 {{
                        color: #856404;
                        font-size: 28px;
                        margin-bottom: 16px;
                        font-weight: 600;
                    }}
                    .error-box {{
                        background: #fff3cd;
                        border: 2px solid #ffc107;
                        border-radius: 8px;
                        padding: 16px;
                        margin: 24px 0;
                        color: #856404;
                    }}
                    .actions {{
                        margin-top: 32px;
                    }}
                    .btn {{
                        display: inline-block;
                        padding: 14px 28px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 16px;
                        transition: all 0.3s ease;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    }}
                    .btn:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="icon">⚠️</div>
                    <h1>Configuration Error</h1>
                    <div class="error-box">
                        Pinterest credentials are not configured. Please contact your administrator.
                    </div>
                    <div class="actions">
                        <a href="{admin_webapp_url}" class="btn">Go to Admin Panel</a>
                    </div>
                </div>
            </body>
            </html>
            """,
            status=500
        )
    
    # Exchange code for access token
    # Use sandbox for trial access, production for approved apps
    use_sandbox = getattr(settings, 'PINTEREST_USE_SANDBOX', True)
    if use_sandbox:
        token_url = "https://api-sandbox.pinterest.com/v5/oauth/token"
    else:
        token_url = "https://api.pinterest.com/v5/oauth/token"
    
    # Ensure redirect_uri matches exactly what was used in authorization request
    # Remove any trailing slashes to ensure consistency
    redirect_uri_clean = redirect_uri.rstrip('/')
    
    # Pinterest API v5 uses Basic Auth with client_id:client_secret
    # and form-encoded data in the body
    import base64
    credentials = f"{app_id}:{app_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    # Use form-encoded data (not JSON)
    data = {
        'grant_type': 'authorization_code',
        'code': str(code),
        'redirect_uri': redirect_uri_clean,
    }
    
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
    }
    
    logger.info(f"Exchanging code for token. Redirect URI: {redirect_uri_clean}")
    logger.info(f"Client ID: {app_id}, Code: {code[:10]}...")
    
    try:
        # Pinterest API v5 uses Basic Auth + form-encoded data
        response = requests.post(token_url, data=data, headers=headers, timeout=30)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 3600)  # Default to 1 hour if not provided
        
        if not access_token:
            admin_webapp_url = getattr(settings, 'ADMIN_WEBAPP_URL', 'https://admin.wedesignz.com')
            return HttpResponse(
                f"""
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Token Exchange Failed</title>
                    <style>
                        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            min-height: 100vh;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            padding: 20px;
                        }}
                        .container {{
                            background: white;
                            border-radius: 16px;
                            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                            max-width: 600px;
                            width: 100%;
                            padding: 40px;
                            text-align: center;
                        }}
                        .icon {{
                            width: 80px;
                            height: 80px;
                            margin: 0 auto 24px;
                            background: #fee;
                            border-radius: 50%;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            font-size: 40px;
                        }}
                        h1 {{
                            color: #dc3545;
                            font-size: 28px;
                            margin-bottom: 16px;
                            font-weight: 600;
                        }}
                        .error-box {{
                            background: #fee;
                            border: 2px solid #fcc;
                            border-radius: 8px;
                            padding: 16px;
                            margin: 24px 0;
                            color: #721c24;
                        }}
                        .actions {{
                            margin-top: 32px;
                            display: flex;
                            flex-direction: column;
                            gap: 12px;
                        }}
                        .btn {{
                            display: inline-block;
                            padding: 14px 28px;
                            border-radius: 8px;
                            text-decoration: none;
                            font-weight: 600;
                            font-size: 16px;
                            transition: all 0.3s ease;
                        }}
                        .btn-primary {{
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                        }}
                        .btn-primary:hover {{
                            transform: translateY(-2px);
                            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
                        }}
                        .btn-secondary {{
                            background: #f8f9fa;
                            color: #495057;
                            border: 2px solid #dee2e6;
                        }}
                        .btn-secondary:hover {{
                            background: #e9ecef;
                            border-color: #adb5bd;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="icon">❌</div>
                        <h1>Token Exchange Failed</h1>
                        <div class="error-box">
                            No access token was received from Pinterest. The authorization may have been cancelled or failed.
                        </div>
                        <div class="actions">
                            <a href="/api/pinterest/authorize/" class="btn btn-primary">Try Again</a>
                            <a href="{admin_webapp_url}/settings?tab=pinterest" class="btn btn-secondary">Go to Settings</a>
                        </div>
                    </div>
                </body>
                </html>
                """,
                status=400
            )
        
        # Calculate token expiration
        token_expires_at = None
        if expires_in:
            token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        
        # Save to database
        integration = PinterestIntegration.get_instance()
        integration.access_token = access_token
        if refresh_token:
            integration.refresh_token = refresh_token
        if token_expires_at:
            integration.token_expires_at = token_expires_at
        integration.is_enabled = True
        if request.user and request.user.is_authenticated:
            integration.created_by = request.user
        integration.save()
        
        logger.info("Successfully obtained and saved Pinterest access token")
        
        # Auto-retry failed Pinterest posts if any exist
        try:
            from .tasks import retry_failed_pinterest_posts
            from .models import PinterestPost
            failed_count = PinterestPost.objects.filter(status='failed').count()
            if failed_count > 0:
                retry_failed_pinterest_posts.delay()
                logger.info(f"Queued retry for {failed_count} failed Pinterest posts")
        except Exception as e:
            logger.warning(f"Could not queue retry for failed posts: {str(e)}")
        
        # Try to get boards to help user select board
        boards_info = ""
        try:
            from .pinterest_service import PinterestService
            service = PinterestService()
            boards = service.get_boards()
            if boards:
                boards_info = "<h3>Your Pinterest Boards:</h3><ul>"
                for board in boards[:10]:  # Show first 10 boards
                    board_id = board.get('id', '')
                    board_name = board.get('name', 'Unknown')
                    boards_info += f"<li><strong>{board_name}</strong> - ID: <code>{board_id}</code></li>"
                boards_info += "</ul>"
        except Exception as e:
            logger.warning(f"Could not fetch boards: {str(e)}")
            boards_info = "<p><em>Could not fetch boards. You can get your board ID from Pinterest API later.</em></p>"
        
        # Get admin webapp URL
        admin_webapp_url = getattr(settings, 'ADMIN_WEBAPP_URL', 'https://admin.wedesignz.com')
        
        # Format boards info with better styling
        boards_html = ""
        if boards_info and "<h3>" in boards_info:
            # Extract boards from the HTML
            boards_html = boards_info.replace("<h3>Your Pinterest Boards:</h3>", "<h3 style='margin-top: 24px; color: #495057;'>Your Pinterest Boards:</h3>")
            boards_html = boards_html.replace("<ul>", "<ul style='list-style: none; padding: 0; margin: 16px 0;'>")
            boards_html = boards_html.replace("<li>", "<li style='background: #f8f9fa; padding: 12px; margin: 8px 0; border-radius: 6px; border-left: 3px solid #667eea;'>")
            boards_html = boards_html.replace("<code>", "<code style='background: #e9ecef; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-family: 'Courier New', monospace;'>")
        elif boards_info:
            boards_html = f"<div style='background: #fff3cd; border: 1px solid #ffc107; padding: 16px; border-radius: 8px; margin: 24px 0;'>{boards_info}</div>"
        
        # Display success message with modern UI
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pinterest Authorization Successful</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 20px;
                    }}
                    .container {{
                        background: white;
                        border-radius: 16px;
                        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                        max-width: 700px;
                        width: 100%;
                        padding: 40px;
                    }}
                    .success-header {{
                        text-align: center;
                        margin-bottom: 32px;
                    }}
                    .success-icon {{
                        width: 100px;
                        height: 100px;
                        margin: 0 auto 24px;
                        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 50px;
                        animation: scaleIn 0.5s ease;
                    }}
                    @keyframes scaleIn {{
                        from {{ transform: scale(0); }}
                        to {{ transform: scale(1); }}
                    }}
                    h1 {{
                        color: #28a745;
                        font-size: 32px;
                        margin-bottom: 8px;
                        font-weight: 700;
                    }}
                    .subtitle {{
                        color: #6c757d;
                        font-size: 16px;
                    }}
                    .info-card {{
                        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
                        border: 2px solid #4caf50;
                        border-radius: 12px;
                        padding: 20px;
                        margin: 24px 0;
                    }}
                    .info-card h2 {{
                        color: #2e7d32;
                        font-size: 20px;
                        margin-bottom: 12px;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }}
                    .info-item {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        padding: 12px 0;
                        border-bottom: 1px solid rgba(46, 125, 50, 0.2);
                    }}
                    .info-item:last-child {{
                        border-bottom: none;
                    }}
                    .info-label {{
                        color: #2e7d32;
                        font-weight: 600;
                        font-size: 14px;
                    }}
                    .info-value {{
                        color: #1b5e20;
                        font-size: 14px;
                    }}
                    .boards-section {{
                        background: #f8f9fa;
                        border-radius: 12px;
                        padding: 20px;
                        margin: 24px 0;
                    }}
                    .boards-section h3 {{
                        color: #495057;
                        font-size: 18px;
                        margin-bottom: 16px;
                    }}
                    .next-steps {{
                        background: #e3f2fd;
                        border: 2px solid #2196f3;
                        border-radius: 12px;
                        padding: 20px;
                        margin: 24px 0;
                    }}
                    .next-steps h2 {{
                        color: #1565c0;
                        font-size: 20px;
                        margin-bottom: 16px;
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }}
                    .next-steps ol {{
                        margin-left: 20px;
                        line-height: 2;
                        color: #1976d2;
                    }}
                    .next-steps li {{
                        margin-bottom: 8px;
                    }}
                    .next-steps code {{
                        background: #bbdefb;
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-size: 13px;
                        font-family: 'Courier New', monospace;
                        color: #0d47a1;
                    }}
                    .actions {{
                        display: flex;
                        flex-direction: column;
                        gap: 12px;
                        margin-top: 32px;
                    }}
                    .btn {{
                        display: inline-block;
                        padding: 16px 32px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 16px;
                        transition: all 0.3s ease;
                        text-align: center;
                        border: none;
                        cursor: pointer;
                    }}
                    .btn-primary {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                    }}
                    .btn-primary:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5);
                    }}
                    .btn-secondary {{
                        background: white;
                        color: #667eea;
                        border: 2px solid #667eea;
                    }}
                    .btn-secondary:hover {{
                        background: #f8f9ff;
                        transform: translateY(-2px);
                    }}
                    .btn-success {{
                        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
                        color: white;
                        box-shadow: 0 4px 15px rgba(40, 167, 69, 0.4);
                    }}
                    .btn-success:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 25px rgba(40, 167, 69, 0.5);
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success-header">
                        <div class="success-icon">✅</div>
                        <h1>Authorization Successful!</h1>
                        <p class="subtitle">Your Pinterest account has been connected</p>
                    </div>
                    
                    <div class="info-card">
                        <h2>📋 Connection Details</h2>
                        <div class="info-item">
                            <span class="info-label">Status</span>
                            <span class="info-value" style="color: #28a745; font-weight: 600;">✓ Connected</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Token Expires</span>
                            <span class="info-value">{token_expires_at.strftime('%B %d, %Y at %I:%M %p') if token_expires_at else 'Not specified'}</span>
                        </div>
                    </div>
                    
                    {boards_html}
                    
                    <div class="next-steps">
                        <h2>🚀 Next Steps</h2>
                        <ol>
                            <li>If you see boards above, copy the <strong>Board ID</strong> of the board where you want to post designs</li>
                            <li>Go to Settings in your Admin Panel and select your Pinterest board</li>
                            <li>Test by approving a design - it will automatically post to Pinterest!</li>
                        </ol>
                    </div>
                    
                    <div class="actions">
                        <a href="{admin_webapp_url}/settings?tab=pinterest" class="btn btn-primary">
                            🎛️ Go to Settings
                        </a>
                        <a href="{admin_webapp_url}/designs" class="btn btn-success">
                            🎨 View Designs
                        </a>
                        <a href="{admin_webapp_url}" class="btn btn-secondary">
                            🏠 Go to Dashboard
                        </a>
                    </div>
                </div>
            </body>
            </html>
            """
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to exchange code for token: {str(e)}")
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_msg = error_data.get('message', error_data.get('error_description', str(e)))
                logger.error(f"Pinterest API Error: {error_data}")
            except:
                error_msg = e.response.text[:500]
        
        admin_webapp_url = getattr(settings, 'ADMIN_WEBAPP_URL', 'https://admin.wedesignz.com')
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pinterest Authorization Failed</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 20px;
                    }}
                    .container {{
                        background: white;
                        border-radius: 16px;
                        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                        max-width: 600px;
                        width: 100%;
                        padding: 40px;
                        text-align: center;
                    }}
                    .icon {{
                        width: 80px;
                        height: 80px;
                        margin: 0 auto 24px;
                        background: #fee;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 40px;
                    }}
                    h1 {{
                        color: #dc3545;
                        font-size: 28px;
                        margin-bottom: 16px;
                        font-weight: 600;
                    }}
                    .error-box {{
                        background: #fee;
                        border: 2px solid #fcc;
                        border-radius: 8px;
                        padding: 16px;
                        margin: 24px 0;
                        color: #721c24;
                        text-align: left;
                        word-break: break-word;
                    }}
                    .error-box strong {{
                        display: block;
                        margin-bottom: 8px;
                        font-size: 14px;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }}
                    .actions {{
                        margin-top: 32px;
                        display: flex;
                        flex-direction: column;
                        gap: 12px;
                    }}
                    .btn {{
                        display: inline-block;
                        padding: 14px 28px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        font-size: 16px;
                        transition: all 0.3s ease;
                    }}
                    .btn-primary {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                    }}
                    .btn-primary:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
                    }}
                    .btn-secondary {{
                        background: #f8f9fa;
                        color: #495057;
                        border: 2px solid #dee2e6;
                    }}
                    .btn-secondary:hover {{
                        background: #e9ecef;
                        border-color: #adb5bd;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="icon">❌</div>
                    <h1>Token Exchange Failed</h1>
                    <div class="error-box">
                        <strong>Error Details</strong>
                        {error_msg[:500]}
                    </div>
                    <p style="color: #6c757d; margin-top: 16px;">
                        There was an issue exchanging the authorization code for an access token. Please try authorizing again.
                    </p>
                    <div class="actions">
                        <a href="/api/pinterest/authorize/" class="btn btn-primary">Try Again</a>
                        <a href="{admin_webapp_url}/settings?tab=pinterest" class="btn btn-secondary">Go to Settings</a>
                    </div>
                </div>
            </body>
            </html>
            """,
            status=400
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def pinterest_status(request):
    """
    Check Pinterest integration status.
    Returns JSON with current status.
    """
    integration = PinterestIntegration.get_instance()
    
    status_data = {
        'is_enabled': integration.is_enabled,
        'is_configured': bool(integration.access_token and integration.board_id),
        'is_token_valid': integration.is_token_valid(),
        'has_board': bool(integration.board_id),
        'board_name': integration.board_name,
        'last_successful_post': integration.last_successful_post.isoformat() if integration.last_successful_post else None,
        'last_error': integration.last_error,
        'last_error_at': integration.last_error_at.isoformat() if integration.last_error_at else None,
    }
    
    return JsonResponse(status_data)


@api_view(['GET'])
@permission_classes([AllowAny])
def pinterest_boards(request):
    """
    Get list of Pinterest boards.
    Requires valid access token.
    """
    integration = PinterestIntegration.get_instance()
    
    if not integration.access_token:
        return JsonResponse({
            'error': 'Pinterest access token not configured. Please authorize first.'
        }, status=400)
    
    if not integration.is_token_valid():
        return JsonResponse({
            'error': 'Pinterest access token expired. Please re-authorize.'
        }, status=400)
    
    try:
        from .pinterest_service import PinterestService
        boards = PinterestService.get_boards_with_token(integration.access_token)
        
        if boards is None:
            return JsonResponse({
                'error': 'Failed to fetch boards. Check server logs for details.'
            }, status=500)
        
        return JsonResponse({
            'success': True,
            'boards': boards
        })
        
    except Exception as e:
        logger.error(f"Error fetching Pinterest boards: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'Error fetching boards: {str(e)}'
        }, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def pinterest_set_board(request):
    """
    Set the Pinterest board ID for posting.
    """
    board_id = request.data.get('board_id')
    board_name = request.data.get('board_name', '')
    
    if not board_id:
        return JsonResponse({
            'error': 'board_id is required'
        }, status=400)
    
    integration = PinterestIntegration.get_instance()
    
    if not integration.access_token:
        return JsonResponse({
            'error': 'Pinterest access token not configured. Please authorize first.'
        }, status=400)
    
    try:
        # Verify board exists by fetching boards
        from .pinterest_service import PinterestService
        boards = PinterestService.get_boards_with_token(integration.access_token)
        
        if boards is None:
            return JsonResponse({
                'error': 'Could not verify board. Please check your access token.'
            }, status=500)
        
        # Find the board
        board_found = None
        for board in boards:
            if str(board.get('id')) == str(board_id):
                board_found = board
                break
        
        if not board_found:
            return JsonResponse({
                'error': f'Board ID "{board_id}" not found in your boards.'
            }, status=400)
        
        # Set the board
        integration.board_id = str(board_id)
        if board_name:
            integration.board_name = board_name
        elif board_found.get('name'):
            integration.board_name = board_found.get('name')
        integration.save()
        
        logger.info(f"Pinterest board set: {integration.board_name} (ID: {integration.board_id})")
        
        return JsonResponse({
            'success': True,
            'message': 'Board set successfully',
            'board_id': integration.board_id,
            'board_name': integration.board_name
        })
        
    except Exception as e:
        logger.error(f"Error setting Pinterest board: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'Error setting board: {str(e)}'
        }, status=500)

