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
import time

from .models import PinterestIntegration, InstagramIntegration, InstagramPost

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
                        <a href="{admin_webapp_url}/settings" class="btn btn-secondary">Go to Settings</a>
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
                        <a href="{admin_webapp_url}/settings" class="btn btn-secondary">Go to Settings</a>
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
                            <a href="{admin_webapp_url}/settings" class="btn btn-secondary">Go to Settings</a>
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
        
        # Try to get boards and auto-select or create one
        boards_info = ""
        auto_selected_board = None
        try:
            from .pinterest_service import PinterestService
            
            # Fetch existing boards
            boards = PinterestService.get_boards_with_token(integration.access_token)
            
            if boards and len(boards) > 0:
                # Boards exist: auto-select the first one
                first_board = boards[0]
                board_id = str(first_board.get('id', ''))
                board_name = first_board.get('name', 'Unknown')
                
                # Auto-select the first board
                integration.board_id = board_id
                integration.board_name = board_name
                integration.save()
                
                auto_selected_board = first_board
                logger.info(f"Auto-selected Pinterest board: {board_name} (ID: {board_id})")
                
                boards_info = f"<h3>Your Pinterest Boards:</h3><ul>"
                for board in boards[:10]:  # Show first 10 boards
                    b_id = board.get('id', '')
                    b_name = board.get('name', 'Unknown')
                    selected = "✅ (Auto-selected)" if str(b_id) == str(board_id) else ""
                    boards_info += f"<li><strong>{b_name}</strong>{selected}<br><code>{b_id}</code></li>"
                boards_info += "</ul>"
            else:
                # No boards exist: create a default one in sandbox mode
                use_sandbox = getattr(settings, 'PINTEREST_USE_SANDBOX', True)
                if use_sandbox:
                    # Create a default board in sandbox
                    new_board = PinterestService.create_board_with_token(
                        integration.access_token,
                        name="Design Gallery",
                        description="WeDesignz designs"
                    )
                    
                    if new_board:
                        board_id = str(new_board.get('id', ''))
                        board_name = new_board.get('name', 'Design Gallery')
                        
                        # Auto-select the newly created board
                        integration.board_id = board_id
                        integration.board_name = board_name
                        integration.save()
                        
                        auto_selected_board = new_board
                        logger.info(f"Created and auto-selected Pinterest board: {board_name} (ID: {board_id})")
                        
                        boards_info = f"<h3>Created New Board:</h3><ul>"
                        boards_info += f"<li><strong>{board_name}</strong> ✅ (Auto-selected)<br><code>{board_id}</code></li>"
                        boards_info += "</ul><p><em>Note: In sandbox mode, boards may not appear in the list but can still be used.</em></p>"
                    else:
                        boards_info = "<p><em>Could not create board automatically. Please create a board manually in Pinterest and set it in Settings.</em></p>"
                else:
                    boards_info = "<p><em>No boards found. Please create a board in Pinterest and select it in Settings.</em></p>"
                    
        except Exception as e:
            logger.warning(f"Could not fetch/create boards: {str(e)}", exc_info=True)
            boards_info = "<p><em>Could not fetch boards. You can get your board ID from Pinterest API later.</em></p>"
        
        # Get admin webapp URL
        admin_webapp_url = getattr(settings, 'ADMIN_WEBAPP_URL', 'https://admin.wedesignz.com')
        
        # Format boards info with minimal styling
        boards_html = ""
        if boards_info and "<h3>" in boards_info:
            # Extract boards from the HTML and format for minimal design
            boards_html = boards_info
            boards_html = boards_html.replace("<h3>Your Pinterest Boards:</h3>", "<div class='boards-section'><h3>Your Boards</h3><ul class='board-list'>")
            boards_html = boards_html.replace("<h3>Created New Board:</h3>", "<div class='boards-section'><h3>Created Board</h3><ul class='board-list'>")
            # Remove the first <ul> tag (we already added it above)
            boards_html = boards_html.replace("<ul>", "", 1)
            boards_html = boards_html.replace("</ul>", "</ul></div>", 1)
            boards_html = boards_html.replace("<li>", "<li class='board-item'>")
            boards_html = boards_html.replace("✅ (Auto-selected)", "<span style='color: #0a7c0a; font-size: 11px; margin-left: 8px;'>• Selected</span>")
            # Handle any remaining </ul> tags
            boards_html = boards_html.replace("</ul>", "")
            # Handle any <p> tags that might be in the message
            if "<p>" in boards_html:
                boards_html = boards_html.replace("<p><em>", "<p style='color: #666; font-size: 13px; margin-top: 12px;'>")
                boards_html = boards_html.replace("</em></p>", "</p>")
        elif boards_info:
            boards_html = f"<div class='boards-section'><p style='color: #666; font-size: 13px; line-height: 1.5;'>{boards_info.replace('<p>', '').replace('</p>', '').replace('<em>', '').replace('</em>', '')}</p></div>"
        
        # Display success message with minimal professional UI
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pinterest Connected</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        background: #f5f5f5;
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 20px;
                        color: #333;
                    }}
                    .container {{
                        background: white;
                        border-radius: 8px;
                        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                        max-width: 500px;
                        width: 100%;
                        padding: 48px 40px;
                    }}
                    .success-icon {{
                        width: 64px;
                        height: 64px;
                        margin: 0 auto 24px;
                        background: #BD081C;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-size: 32px;
                        font-weight: 300;
                    }}
                    h1 {{
                        color: #1a1a1a;
                        font-size: 24px;
                        font-weight: 600;
                        text-align: center;
                        margin-bottom: 8px;
                        letter-spacing: -0.3px;
                    }}
                    .subtitle {{
                        color: #666;
                        font-size: 14px;
                        text-align: center;
                        margin-bottom: 32px;
                        line-height: 1.5;
                    }}
                    .info-section {{
                        border-top: 1px solid #e5e5e5;
                        border-bottom: 1px solid #e5e5e5;
                        padding: 20px 0;
                        margin: 24px 0;
                    }}
                    .info-item {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        padding: 8px 0;
                        font-size: 14px;
                    }}
                    .info-label {{
                        color: #666;
                        font-weight: 400;
                    }}
                    .info-value {{
                        color: #1a1a1a;
                        font-weight: 500;
                    }}
                    .status-badge {{
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        color: #0a7c0a;
                        font-size: 13px;
                        font-weight: 500;
                    }}
                    .status-badge::before {{
                        content: '';
                        width: 8px;
                        height: 8px;
                        background: #0a7c0a;
                        border-radius: 50%;
                    }}
                    .boards-section {{
                        margin: 24px 0;
                        padding: 20px 0;
                    }}
                    .boards-section h3 {{
                        color: #1a1a1a;
                        font-size: 14px;
                        font-weight: 600;
                        margin-bottom: 12px;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }}
                    .board-list {{
                        list-style: none;
                        margin: 0;
                        padding: 0;
                    }}
                    .board-item {{
                        background: #f9f9f9;
                        border: 1px solid #e5e5e5;
                        border-radius: 4px;
                        padding: 12px;
                        margin-bottom: 8px;
                        font-size: 13px;
                    }}
                    .board-item strong {{
                        color: #1a1a1a;
                        font-weight: 500;
                        display: block;
                        margin-bottom: 4px;
                    }}
                    .board-item code {{
                        background: #fff;
                        padding: 2px 6px;
                        border-radius: 3px;
                        font-size: 11px;
                        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', monospace;
                        color: #666;
                        border: 1px solid #e5e5e5;
                    }}
                    .actions {{
                        margin-top: 32px;
                        display: flex;
                        flex-direction: column;
                        gap: 10px;
                    }}
                    .btn {{
                        display: block;
                        padding: 12px 24px;
                        border-radius: 4px;
                        text-decoration: none;
                        font-weight: 500;
                        font-size: 14px;
                        text-align: center;
                        transition: all 0.2s ease;
                        border: none;
                        cursor: pointer;
                    }}
                    .btn-primary {{
                        background: #BD081C;
                        color: white;
                    }}
                    .btn-primary:hover {{
                        background: #a00716;
                    }}
                    .btn-secondary {{
                        background: transparent;
                        color: #666;
                        border: 1px solid #e5e5e5;
                    }}
                    .btn-secondary:hover {{
                        background: #f9f9f9;
                        border-color: #d5d5d5;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success-icon">✓</div>
                    <h1>Pinterest Connected</h1>
                    <p class="subtitle">Your account has been successfully authorized</p>
                    
                    <div class="info-section">
                        <div class="info-item">
                            <span class="info-label">Status</span>
                            <span class="info-value">
                                <span class="status-badge">Connected</span>
                            </span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Token Expires</span>
                            <span class="info-value">{token_expires_at.strftime('%b %d, %Y') if token_expires_at else 'Not specified'}</span>
                        </div>
                    </div>
                    
                    {boards_html}
                    
                    <div class="actions">
                        <a href="{admin_webapp_url}/settings" class="btn btn-primary">
                            Continue to Settings
                        </a>
                        <a href="{admin_webapp_url}" class="btn btn-secondary">
                            Go to Dashboard
                        </a>
                    </div>
                </div>
                <script>
                    // Automatically redirect to settings after 5 seconds
                    setTimeout(function() {{
                        window.location.href = '{admin_webapp_url}/settings';
                    }}, 5000);
                </script>
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
                        <a href="{admin_webapp_url}/settings" class="btn btn-secondary">Go to Settings</a>
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
        from django.conf import settings
        
        boards = PinterestService.get_boards_with_token(integration.access_token)
        
        if boards is None:
            return JsonResponse({
                'error': 'Failed to fetch boards. Check server logs for details.'
            }, status=500)
        
        # If no boards exist and we're in sandbox mode, optionally create one
        # Check if create_if_empty parameter is passed
        create_if_empty = request.GET.get('create_if_empty', 'false').lower() == 'true'
        use_sandbox = getattr(settings, 'PINTEREST_USE_SANDBOX', True)
        
        if len(boards) == 0 and create_if_empty and use_sandbox:
            # Create a default board
            new_board = PinterestService.create_board_with_token(
                integration.access_token,
                name="Design Gallery",
                description="WeDesignz designs"
            )
            
            if new_board:
                boards = [new_board]
                # Auto-select it
                integration.board_id = str(new_board.get('id', ''))
                integration.board_name = new_board.get('name', 'Design Gallery')
                integration.save()
                logger.info(f"Created and auto-selected board: {integration.board_name} (ID: {integration.board_id})")
        
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
        from .pinterest_service import PinterestService
        from django.conf import settings
        
        # Check if we're in sandbox mode
        use_sandbox = getattr(settings, 'PINTEREST_USE_SANDBOX', True)
        
        # Validate board_id is numeric (Pinterest requirement)
        if not str(board_id).isdigit():
            return JsonResponse({
                'error': 'Board ID must be numeric (Pinterest requirement).'
            }, status=400)
        
        # In sandbox mode, skip validation since boards API may return empty
        if use_sandbox:
            # Sandbox mode: Allow setting board ID directly
            integration.board_id = str(board_id)
            if board_name:
                integration.board_name = board_name
            else:
                # Try to get board name from API if not provided
                try:
                    boards = PinterestService.get_boards_with_token(integration.access_token)
                    if boards:
                        for board in boards:
                            if str(board.get('id')) == str(board_id):
                                integration.board_name = board.get('name', '')
                                break
                    if not integration.board_name:
                        integration.board_name = board_name or f"Board {board_id}"
                except:
                    integration.board_name = board_name or f"Board {board_id}"
            integration.save()
            
            logger.info(f"Pinterest board set (sandbox): {integration.board_name} (ID: {integration.board_id})")
            
            return JsonResponse({
                'success': True,
                'message': 'Board set successfully',
                'board_id': integration.board_id,
                'board_name': integration.board_name
            })
        else:
            # Production mode: Validate board exists
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


@api_view(['POST'])
@permission_classes([AllowAny])
def pinterest_create_board(request):
    """
    Create a new Pinterest board.
    """
    name = request.data.get('name')
    description = request.data.get('description', '')
    privacy = request.data.get('privacy', 'PUBLIC')
    
    if not name:
        return JsonResponse({
            'error': 'Board name is required'
        }, status=400)
    
    if privacy not in ['PUBLIC', 'SECRET']:
        return JsonResponse({
            'error': 'Privacy must be PUBLIC or SECRET'
        }, status=400)
    
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
        
        new_board = PinterestService.create_board_with_token(
            integration.access_token,
            name=name,
            description=description,
            privacy=privacy
        )
        
        if not new_board:
            return JsonResponse({
                'error': 'Failed to create board. Check server logs for details.'
            }, status=500)
        
        logger.info(f"Pinterest board created: {new_board.get('name')} (ID: {new_board.get('id')})")
        
        return JsonResponse({
            'success': True,
            'message': 'Board created successfully',
            'board': {
                'id': str(new_board.get('id')),
                'name': new_board.get('name'),
                'description': new_board.get('description', ''),
                'privacy': new_board.get('privacy', 'PUBLIC'),
                'pin_count': new_board.get('pin_count', 0)
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating Pinterest board: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'Error creating board: {str(e)}'
        }, status=500)


@api_view(['PATCH'])
@permission_classes([AllowAny])
def pinterest_update_board(request):
    """
    Update a Pinterest board.
    """
    board_id = request.data.get('board_id')
    name = request.data.get('name')
    description = request.data.get('description')
    privacy = request.data.get('privacy')
    
    if not board_id:
        return JsonResponse({
            'error': 'board_id is required'
        }, status=400)
    
    if not any([name, description, privacy]):
        return JsonResponse({
            'error': 'At least one field (name, description, privacy) must be provided'
        }, status=400)
    
    if privacy and privacy not in ['PUBLIC', 'SECRET']:
        return JsonResponse({
            'error': 'Privacy must be PUBLIC or SECRET'
        }, status=400)
    
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
        
        updated_board = PinterestService.update_board_with_token(
            integration.access_token,
            board_id,
            name=name,
            description=description,
            privacy=privacy
        )
        
        if not updated_board:
            return JsonResponse({
                'error': 'Failed to update board. Check server logs for details.'
            }, status=500)
        
        # If this is the currently selected board, update the integration
        if str(integration.board_id) == str(board_id):
            if name:
                integration.board_name = name
                integration.save(update_fields=['board_name'])
        
        logger.info(f"Pinterest board updated: {updated_board.get('name')} (ID: {updated_board.get('id')})")
        
        return JsonResponse({
            'success': True,
            'message': 'Board updated successfully',
            'board': {
                'id': str(updated_board.get('id')),
                'name': updated_board.get('name'),
                'description': updated_board.get('description', ''),
                'privacy': updated_board.get('privacy', 'PUBLIC'),
                'pin_count': updated_board.get('pin_count', 0)
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating Pinterest board: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'Error updating board: {str(e)}'
        }, status=500)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def pinterest_delete_board(request, board_id=None):
    """
    Delete a Pinterest board.
    """
    # Support both URL parameter and body parameter
    if not board_id:
        board_id = request.data.get('board_id')
    
    if not board_id:
        return JsonResponse({
            'error': 'board_id is required'
        }, status=400)
    
    integration = PinterestIntegration.get_instance()
    
    if not integration.access_token:
        return JsonResponse({
            'error': 'Pinterest access token not configured. Please authorize first.'
        }, status=400)
    
    if not integration.is_token_valid():
        return JsonResponse({
            'error': 'Pinterest access token expired. Please re-authorize.'
        }, status=400)
    
    # Prevent deleting the currently selected board
    if str(integration.board_id) == str(board_id):
        return JsonResponse({
            'error': 'Cannot delete the currently selected board. Please select a different board first.'
        }, status=400)
    
    try:
        from .pinterest_service import PinterestService
        
        success = PinterestService.delete_board_with_token(
            integration.access_token,
            board_id
        )
        
        if not success:
            return JsonResponse({
                'error': 'Failed to delete board. Check server logs for details.'
            }, status=500)
        
        logger.info(f"Pinterest board deleted: {board_id}")
        
        return JsonResponse({
            'success': True,
            'message': 'Board deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting Pinterest board: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'Error deleting board: {str(e)}'
        }, status=500)


# ==================== INSTAGRAM VIEWS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def instagram_oauth_initiate(request):
    """
    Initiate Instagram OAuth flow through Facebook.
    Redirects user to Facebook authorization page.
    Note: Instagram uses Facebook's OAuth system.
    """
    app_id = getattr(settings, 'FACEBOOK_APP_ID', None) or getattr(settings, 'INSTAGRAM_APP_ID', None)
    redirect_uri = getattr(settings, 'INSTAGRAM_REDIRECT_URI', None)
    
    if not app_id:
        return JsonResponse({'error': 'Facebook/Instagram App ID not configured'}, status=500)
    if not redirect_uri:
        return JsonResponse({'error': 'Instagram Redirect URI not configured'}, status=500)
    
    # Build authorization URL for Facebook (Instagram uses Facebook OAuth)
    from urllib.parse import quote_plus
    redirect_uri_clean = redirect_uri.rstrip('/')
    redirect_uri_encoded = quote_plus(redirect_uri_clean)
    
    # Instagram Graph API requires these permissions:
    # - pages_show_list: List Facebook pages (needed for Instagram Business accounts)
    # - pages_read_engagement: Read page engagement
    # - business_management: Manage business assets
    # - instagram_content_publish: Post to Instagram (requires App Review for production)
    # Note: instagram_basic is deprecated, use pages permissions instead
    auth_url = (
        f"https://www.facebook.com/v18.0/dialog/oauth"
        f"?client_id={app_id}"
        f"&redirect_uri={redirect_uri_encoded}"
        f"&response_type=code"
        f"&scope=pages_show_list,pages_read_engagement,business_management,instagram_content_publish"
        f"&state=instagram_auth"
    )
    
    logger.info(f"Instagram OAuth authorization URL: client_id={app_id}, redirect_uri={redirect_uri_clean}")
    logger.info(f"Redirecting to Facebook OAuth for Instagram: {auth_url}")
    return redirect(auth_url)


@api_view(['GET'])
@permission_classes([AllowAny])
@csrf_exempt
def instagram_oauth_callback(request):
    """
    Handle Instagram OAuth callback from Facebook.
    Exchanges authorization code for access token and saves to database.
    """
    code = request.GET.get('code')
    error = request.GET.get('error')
    error_reason = request.GET.get('error_reason', '')
    error_description = request.GET.get('error_description', '')
    
    # Get admin webapp URL from settings
    admin_webapp_url = getattr(settings, 'ADMIN_WEBAPP_URL', 'https://admin.wedesignz.com')
    
    if error:
        error_msg = error
        if error_description:
            error_msg += f": {error_description}"
        logger.error(f"Instagram OAuth error: {error_msg}")
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Instagram Authorization Failed</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
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
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
                        color: white;
                    }}
                    .btn-primary:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 20px rgba(225, 48, 108, 0.4);
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
                        {error_msg}
                    </div>
                    <p style="color: #6c757d; margin-top: 16px;">
                        There was an issue authorizing your Instagram account. Please try again.
                    </p>
                    <div class="actions">
                        <a href="/api/common/instagram/authorize/" class="btn btn-primary">Try Again</a>
                        <a href="{admin_webapp_url}/settings?tab=instagram" class="btn btn-secondary">Go to Settings</a>
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
                <title>Instagram Authorization Failed</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
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
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
                        color: white;
                    }}
                    .btn-primary:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 8px 20px rgba(225, 48, 108, 0.4);
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
                    <p style="color: #6c757d; margin-top: 16px;">
                        No authorization code received. Please try again.
                    </p>
                    <div class="actions">
                        <a href="/api/common/instagram/authorize/" class="btn btn-primary">Try Again</a>
                        <a href="{admin_webapp_url}/settings?tab=instagram" class="btn btn-secondary">Go to Settings</a>
                    </div>
                </div>
            </body>
            </html>
            """,
            status=400
        )
    
    # Exchange code for access token
    app_id = getattr(settings, 'FACEBOOK_APP_ID', None) or getattr(settings, 'INSTAGRAM_APP_ID', None)
    app_secret = getattr(settings, 'FACEBOOK_APP_SECRET', None) or getattr(settings, 'INSTAGRAM_APP_SECRET', None)
    redirect_uri = getattr(settings, 'INSTAGRAM_REDIRECT_URI', None)
    
    if not app_id or not app_secret:
        logger.error("Facebook/Instagram App ID or Secret not configured")
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Instagram Configuration Error</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
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
                    h1 {{ color: #dc3545; font-size: 28px; margin-bottom: 16px; }}
                    p {{ color: #6c757d; margin-top: 16px; }}
                    .btn {{
                        display: inline-block;
                        padding: 14px 28px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        margin-top: 24px;
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
                        color: white;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Configuration Error</h1>
                    <p>Facebook/Instagram App credentials are not configured. Please contact your administrator.</p>
                    <a href="{admin_webapp_url}/settings?tab=instagram" class="btn">Go to Settings</a>
                </div>
            </body>
            </html>
            """,
            status=500
        )
    
    try:
        # Step 1: Exchange code for short-lived access token
        token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        token_params = {
            'client_id': app_id,
            'client_secret': app_secret,
            'redirect_uri': redirect_uri.rstrip('/'),
            'code': code
        }
        
        token_response = requests.get(token_url, params=token_params, timeout=30)
        token_response.raise_for_status()
        token_data = token_response.json()
        
        short_lived_token = token_data.get('access_token')
        if not short_lived_token:
            raise ValueError("No access token in response")
        
        # Step 2: Exchange short-lived token for long-lived token (60 days)
        long_token_url = "https://graph.facebook.com/v18.0/oauth/access_token"
        long_token_params = {
            'grant_type': 'fb_exchange_token',
            'client_id': app_id,
            'client_secret': app_secret,
            'fb_exchange_token': short_lived_token
        }
        
        long_token_response = requests.get(long_token_url, params=long_token_params, timeout=30)
        long_token_response.raise_for_status()
        long_token_data = long_token_response.json()
        
        long_lived_token = long_token_data.get('access_token', short_lived_token)
        expires_in = long_token_data.get('expires_in', 5184000)  # Default 60 days
        
        # Step 3: Get user info to find Instagram Business Account ID
        user_info_url = "https://graph.facebook.com/v18.0/me"
        user_info_params = {
            'fields': 'id,name',
            'access_token': long_lived_token
        }
        
        user_info_response = requests.get(user_info_url, params=user_info_params, timeout=30)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()
        
        # Step 4: Get Instagram Business Account ID
        # First, get pages (Instagram Business accounts are linked to Facebook Pages)
        # IMPORTANT: We need to request 'access_token' field to get the Page Access Token
        # The Page Access Token is required for Instagram Graph API calls, not the user's token
        pages_url = "https://graph.facebook.com/v18.0/me/accounts"
        pages_params = {
            'access_token': long_lived_token,
            'fields': 'id,name,access_token,instagram_business_account'
        }
        
        pages_response = requests.get(pages_url, params=pages_params, timeout=30)
        pages_response.raise_for_status()
        pages_data = pages_response.json()
        
        # Add detailed logging to debug what's being returned
        logger.info(f"Pages API response received. Number of pages: {len(pages_data.get('data', []))}")
        if pages_data.get('data'):
            logger.info(f"First page sample keys: {list(pages_data['data'][0].keys())}")
        
        instagram_account_id = None
        instagram_username = None
        page_access_token = None  # This is the token we need for Instagram API
        page_id = None  # Store the page ID for fallback
        
        # Find the Instagram Business Account
        for page in pages_data.get('data', []):
            logger.info(f"Processing page: ID={page.get('id')}, name={page.get('name')}")
            logger.info(f"Page has 'access_token' field: {'access_token' in page}")
            logger.info(f"Page has 'instagram_business_account': {'instagram_business_account' in page}")
            
            if 'instagram_business_account' in page:
                instagram_account = page['instagram_business_account']
                instagram_account_id = instagram_account.get('id')
                page_id = page.get('id')
                
                logger.info(f"Found Instagram Business Account ID: {instagram_account_id} for page: {page_id}")
                
                # CRITICAL: Get the page access token (required for Instagram Graph API)
                # The page access token is different from the user's long-lived token
                page_access_token = page.get('access_token')
                
                if not page_access_token:
                    logger.warning(f"Page {page_id} has Instagram Business Account but no access_token in response")
                    logger.warning(f"Trying fallback method to get page access token...")
                    
                    # FALLBACK: Try to get page access token by querying the page directly
                    try:
                        page_token_url = f"https://graph.facebook.com/v18.0/{page_id}"
                        page_token_params = {
                            'fields': 'access_token',
                            'access_token': long_lived_token
                        }
                        page_token_response = requests.get(page_token_url, params=page_token_params, timeout=30)
                        if page_token_response.status_code == 200:
                            page_token_data = page_token_response.json()
                            page_access_token = page_token_data.get('access_token')
                            if page_access_token:
                                logger.info(f"Successfully retrieved page access token via fallback method")
                            else:
                                logger.warning(f"Fallback method returned no access_token")
                        else:
                            logger.warning(f"Fallback method failed with status {page_token_response.status_code}: {page_token_response.text[:200]}")
                    except Exception as e:
                        logger.warning(f"Fallback method exception: {e}")
                    
                    if not page_access_token:
                        logger.warning(f"Could not get access token for page {page_id}, trying next page...")
                        continue
                
                # Get Instagram account details using the page access token
                # Note: 'username' field is deprecated in Instagram Graph API v2.0+
                # We can't retrieve it via API, so we'll leave it as None
                if instagram_account_id:
                    # Just verify the account ID is valid by making a simple request
                    instagram_url = f"https://graph.facebook.com/v18.0/{instagram_account_id}"
                    instagram_params = {
                        'fields': 'id',  # Only request 'id' - username is deprecated
                        'access_token': page_access_token
                    }
                    instagram_response = requests.get(instagram_url, params=instagram_params, timeout=30)
                    if instagram_response.status_code == 200:
                        instagram_data = instagram_response.json()
                        # Username is deprecated, so we can't get it from API
                        instagram_username = None
                        logger.info(f"Instagram Business Account ID verified successfully")
                    else:
                        logger.warning(f"Could not verify Instagram Business Account ID: {instagram_response.text[:200]}")
                    break
        
        # Validate that we have the required page access token
        if not page_access_token:
            # Provide more detailed error message
            pages_list = [p.get('id') for p in pages_data.get('data', [])]
            error_msg = (
                f"No page access token found. "
                f"Pages returned: {pages_list}. "
                f"Make sure your Instagram Business account is linked to a Facebook Page "
                f"and you have granted 'pages_show_list' and 'pages_read_engagement' permissions."
            )
            logger.error(error_msg)
            logger.error(f"Full pages response structure: {list(pages_data.keys())}")
            if pages_data.get('data'):
                logger.error(f"Sample page structure: {list(pages_data['data'][0].keys()) if pages_data['data'] else 'No pages'}")
            raise ValueError(error_msg)
        
        if not instagram_account_id:
            error_msg = "No Instagram Business Account found. Make sure your Instagram account is a Business or Creator account and is linked to a Facebook Page."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Validate that we have the Instagram Business Account ID (not a Page ID)
        # Instagram Business Account IDs are typically 15-17 digits
        # Facebook Page IDs are typically shorter (10-12 digits)
        logger.info(f"Found Instagram Business Account ID: {instagram_account_id}")
        logger.info(f"Page ID: {page.get('id')}")
        logger.info(f"Page Access Token (first 20 chars): {page_access_token[:20] if page_access_token else 'None'}...")
        
        # Verify the Instagram Business Account ID is valid by testing it
        try:
            verify_url = f"https://graph.facebook.com/v18.0/{instagram_account_id}"
            verify_params = {
                'fields': 'id',
                'access_token': page_access_token
            }
            verify_response = requests.get(verify_url, params=verify_params, timeout=10)
            if verify_response.status_code != 200:
                error_data = verify_response.json() if verify_response.text else {}
                error_msg = error_data.get('error', {}).get('message', 'Invalid Instagram Business Account ID')
                logger.error(f"Instagram Business Account ID validation failed: {error_msg}")
                raise ValueError(f"Invalid Instagram Business Account ID: {error_msg}")
            logger.info(f"Instagram Business Account ID validated successfully: {instagram_account_id}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Could not verify Instagram Business Account ID: {e}")
            # Continue anyway, but log the warning
        
        # Save to database
        integration = InstagramIntegration.get_instance()
        # Store the PAGE ACCESS TOKEN, not the user's long-lived token
        # Instagram Graph API requires the page access token for posting
        integration.access_token = page_access_token
        integration.user_id = instagram_account_id  # This should be the Instagram Business Account ID, not Page ID
        integration.username = instagram_username
        integration.is_enabled = True
        
        # Calculate expiration date
        from datetime import timedelta
        integration.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        
        if request.user and request.user.is_authenticated:
            integration.created_by = request.user
        
        integration.save()
        
        logger.info(f"Instagram OAuth successful!")
        logger.info(f"  - Instagram Business Account ID (user_id): {integration.user_id}")
        logger.info(f"  - Username: {integration.username or 'N/A (deprecated field)'}")
        logger.info(f"  - Access Token: {integration.access_token[:30] if integration.access_token else 'None'}...")
        logger.info(f"  - Token Expires: {integration.token_expires_at}")
        
        # Return success page
        token_expires_at = integration.token_expires_at
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Instagram Authorization Successful</title>
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        padding: 20px;
                    }}
                    .container {{
                        background: white;
                        border-radius: 12px;
                        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
                        max-width: 500px;
                        width: 100%;
                        padding: 48px 40px;
                        text-align: center;
                    }}
                    .success-icon {{
                        width: 64px;
                        height: 64px;
                        margin: 0 auto 24px;
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-size: 32px;
                        font-weight: 300;
                    }}
                    h1 {{
                        color: #1a1a1a;
                        font-size: 24px;
                        font-weight: 600;
                        text-align: center;
                        margin-bottom: 8px;
                        letter-spacing: -0.3px;
                    }}
                    .subtitle {{
                        color: #666;
                        font-size: 14px;
                        text-align: center;
                        margin-bottom: 32px;
                        line-height: 1.5;
                    }}
                    .info-section {{
                        border-top: 1px solid #e5e5e5;
                        border-bottom: 1px solid #e5e5e5;
                        padding: 20px 0;
                        margin: 24px 0;
                    }}
                    .info-item {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        padding: 8px 0;
                        font-size: 14px;
                    }}
                    .info-label {{
                        color: #666;
                        font-weight: 400;
                    }}
                    .info-value {{
                        color: #1a1a1a;
                        font-weight: 500;
                    }}
                    .status-badge {{
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        color: #0a7c0a;
                        font-size: 13px;
                        font-weight: 500;
                    }}
                    .status-badge::before {{
                        content: '';
                        width: 8px;
                        height: 8px;
                        background: #0a7c0a;
                        border-radius: 50%;
                    }}
                    .account-info {{
                        background: #f9f9f9;
                        border: 1px solid #e5e5e5;
                        border-radius: 4px;
                        padding: 12px;
                        margin: 16px 0;
                        font-size: 13px;
                    }}
                    .account-info strong {{
                        color: #1a1a1a;
                        font-weight: 500;
                        display: block;
                        margin-bottom: 4px;
                    }}
                    .account-info code {{
                        background: #fff;
                        padding: 2px 6px;
                        border-radius: 3px;
                        font-size: 11px;
                        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', monospace;
                        color: #666;
                        border: 1px solid #e5e5e5;
                    }}
                    .actions {{
                        margin-top: 32px;
                        display: flex;
                        flex-direction: column;
                        gap: 10px;
                    }}
                    .btn {{
                        display: block;
                        padding: 12px 24px;
                        border-radius: 4px;
                        text-decoration: none;
                        font-weight: 500;
                        font-size: 14px;
                        text-align: center;
                        transition: all 0.2s ease;
                        border: none;
                        cursor: pointer;
                    }}
                    .btn-primary {{
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
                        color: white;
                    }}
                    .btn-primary:hover {{
                        opacity: 0.9;
                        transform: translateY(-1px);
                        box-shadow: 0 4px 12px rgba(225, 48, 108, 0.3);
                    }}
                    .btn-secondary {{
                        background: transparent;
                        color: #666;
                        border: 1px solid #e5e5e5;
                    }}
                    .btn-secondary:hover {{
                        background: #f9f9f9;
                        border-color: #d5d5d5;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success-icon">✓</div>
                    <h1>Instagram Connected</h1>
                    <p class="subtitle">Your account has been successfully authorized</p>
                    
                    <div class="info-section">
                        <div class="info-item">
                            <span class="info-label">Status</span>
                            <span class="info-value">
                                <span class="status-badge">Connected</span>
                            </span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">Token Expires</span>
                            <span class="info-value">{token_expires_at.strftime('%b %d, %Y') if token_expires_at else 'Not specified'}</span>
                        </div>
                    </div>
                    
                    <div class="account-info">
                        <strong>Instagram Account</strong>
                        <code>{'@' + instagram_username if instagram_username else 'Account ID: ' + str(integration.user_id)}</code>
                    </div>
                    
                    <div class="actions">
                        <a href="{admin_webapp_url}/settings?tab=instagram" class="btn btn-primary">
                            Continue to Settings
                        </a>
                        <a href="{admin_webapp_url}" class="btn btn-secondary">
                            Go to Dashboard
                        </a>
                    </div>
                </div>
                <script>
                    // Automatically redirect to settings after 5 seconds
                    setTimeout(function() {{
                        window.location.href = '{admin_webapp_url}/settings?tab=instagram';
                    }}, 5000);
                </script>
            </body>
            </html>
            """
        )
        
    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_msg = error_data.get('error', {}).get('message', str(e))
            except:
                error_msg = e.response.text[:500]
        
        logger.error(f"Instagram OAuth token exchange failed: {error_msg}", exc_info=True)
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Instagram Authorization Error</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
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
                    h1 {{ color: #dc3545; font-size: 28px; margin-bottom: 16px; }}
                    .error-box {{
                        background: #fee;
                        border: 2px solid #fcc;
                        border-radius: 8px;
                        padding: 16px;
                        margin: 24px 0;
                        color: #721c24;
                    }}
                    .btn {{
                        display: inline-block;
                        padding: 14px 28px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        margin-top: 24px;
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
                        color: white;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Authorization Error</h1>
                    <div class="error-box">
                        <strong>Error</strong>
                        <p style="margin-top: 8px;">{error_msg}</p>
                    </div>
                    <a href="{admin_webapp_url}/settings?tab=instagram" class="btn">Go to Settings</a>
                </div>
            </body>
            </html>
            """,
            status=500
        )
    except Exception as e:
        logger.error(f"Instagram OAuth error: {str(e)}", exc_info=True)
        return HttpResponse(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Instagram Authorization Error</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
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
                    h1 {{ color: #dc3545; font-size: 28px; margin-bottom: 16px; }}
                    .error-box {{
                        background: #fee;
                        border: 2px solid #fcc;
                        border-radius: 8px;
                        padding: 16px;
                        margin: 24px 0;
                        color: #721c24;
                    }}
                    .btn {{
                        display: inline-block;
                        padding: 14px 28px;
                        border-radius: 8px;
                        text-decoration: none;
                        font-weight: 600;
                        margin-top: 24px;
                        background: linear-gradient(135deg, #E1306C 0%, #C13584 50%, #833AB4 100%);
                        color: white;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Authorization Error</h1>
                    <div class="error-box">
                        <strong>Error</strong>
                        <p style="margin-top: 8px;">{str(e)}</p>
                    </div>
                    <a href="{admin_webapp_url}/settings?tab=instagram" class="btn">Go to Settings</a>
                </div>
            </body>
            </html>
            """,
            status=500
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def instagram_status(request):
    """
    Check Instagram integration status.
    Returns JSON with current status.
    """
    integration = InstagramIntegration.get_instance()
    
    status_data = {
        'is_enabled': integration.is_enabled,
        'is_configured': bool(integration.access_token),
        'is_token_valid': integration.is_token_valid(),
        'username': integration.username,
        'last_successful_post': integration.last_successful_post.isoformat() if integration.last_successful_post else None,
        'last_error': integration.last_error,
        'last_error_at': integration.last_error_at.isoformat() if integration.last_error_at else None,
    }
    
    return JsonResponse(status_data)


@api_view(['POST'])
@permission_classes([AllowAny])
def instagram_post(request):
    """
    Create Instagram posts (supports bulk posting).
    Accepts array of posts and queues them for async processing.
    """
    posts_data = request.data.get('posts', [])
    
    if not posts_data or not isinstance(posts_data, list):
        return JsonResponse({
            'error': 'posts array is required'
        }, status=400)
    
    if len(posts_data) == 0:
        return JsonResponse({
            'error': 'At least one post is required'
        }, status=400)
    
    # Validate integration
    integration = InstagramIntegration.get_instance()
    
    if not integration.is_enabled:
        return JsonResponse({
            'error': 'Instagram integration is disabled'
        }, status=400)
    
    if not integration.access_token:
        return JsonResponse({
            'error': 'Instagram access token not configured. Please authorize first.'
        }, status=400)
    
    if not integration.is_token_valid():
        return JsonResponse({
            'error': 'Instagram access token expired. Please re-authorize.'
        }, status=400)
    
    try:
        from Catalog.models import Product
        from .tasks import post_to_instagram
        
        created_posts = []
        errors = []
        total_posts = len(posts_data)
        
        logger.info(f"Processing {total_posts} Instagram posts")
        
        for index, post_data in enumerate(posts_data):
            try:
                product_id = post_data.get('productId')
                media_type = post_data.get('mediaType')
                caption = post_data.get('caption', '')
                post_type = post_data.get('postType', 'post')
                
                logger.info(f"Processing post {index + 1}/{total_posts}: product_id={product_id}, media_type={media_type}")
                
                # Validate required fields
                if not product_id:
                    error_msg = 'productId is required'
                    logger.warning(f"Post {index + 1} validation failed: {error_msg}")
                    errors.append({'post': post_data, 'error': error_msg})
                    continue
                
                if media_type not in ['mockup', 'jpg', 'png']:
                    error_msg = f'Invalid media_type: {media_type}'
                    logger.warning(f"Post {index + 1} validation failed: {error_msg}")
                    errors.append({'post': post_data, 'error': error_msg})
                    continue
                
                if post_type not in ['post', 'story']:
                    error_msg = f'Invalid post_type: {post_type}'
                    logger.warning(f"Post {index + 1} validation failed: {error_msg}")
                    errors.append({'post': post_data, 'error': error_msg})
                    continue
                
                # Get product
                try:
                    product = Product.objects.get(id=product_id)
                except Product.DoesNotExist:
                    error_msg = f'Product {product_id} not found'
                    logger.warning(f"Post {index + 1} failed: {error_msg}")
                    errors.append({'post': post_data, 'error': error_msg})
                    continue
            
            # Get media file URL based on media_type
            media_files = product.get_media().filter(media_type='image')
            image_url = None
            
            for media_file in media_files:
                # Get file name from the file field (same as Celery task)
                file_name = ''
                if hasattr(media_file, 'file') and media_file.file:
                    try:
                        file_name = media_file.file.name.lower()
                    except (AttributeError, ValueError):
                        file_name = ''
                
                if media_type == 'mockup':
                    # Check if it's a mockup
                    is_mockup = 'mockup' in file_name
                    if not is_mockup:
                        # Check metadata
                        try:
                            from MediaFiles.models import Relation
                            relation = Relation.objects.filter(
                                relation_type='Product:Media',
                                id_1=product.pk,
                                id_2=media_file.pk
                            ).first()
                            if relation and relation.meta and 'mockup' in str(relation.meta).lower():
                                is_mockup = True
                        except Exception:
                            pass
                    
                    if is_mockup:
                        image_url = media_file.file.url if hasattr(media_file, 'file') and media_file.file else None
                        break
                elif media_type == 'jpg':
                    if file_name.endswith(('.jpg', '.jpeg')):
                        image_url = media_file.file.url if hasattr(media_file, 'file') and media_file.file else None
                        break
                elif media_type == 'png':
                    if file_name.endswith('.png'):
                        image_url = media_file.file.url if hasattr(media_file, 'file') and media_file.file else None
                        break
            
                if not image_url:
                    error_msg = f'No {media_type} image found for product {product_id}'
                    logger.warning(f"Post {index + 1} failed: {error_msg}")
                    errors.append({
                        'post': post_data,
                        'error': error_msg
                    })
                    continue
                
                # Make image URL absolute if it's relative
                if image_url.startswith('/'):
                    site_domain = getattr(settings, 'SITE_DOMAIN', 'wedesignz.com')
                    protocol = 'https' if not settings.DEBUG else 'http'
                    image_url = f"{protocol}://{site_domain}{image_url}"
                
                # Create InstagramPost record
                try:
                    instagram_post = InstagramPost.objects.create(
                        product=product,
                        media_type=media_type,
                        caption=caption,
                        post_type=post_type,
                        status='pending'
                    )
                    logger.info(f"Created InstagramPost record {instagram_post.id} for product {product_id}")
                except Exception as e:
                    error_msg = f"Failed to create InstagramPost record: {str(e)}"
                    logger.error(f"Post {index + 1} failed: {error_msg}", exc_info=True)
                    errors.append({
                        'post': post_data,
                        'error': error_msg
                    })
                    continue
                
                # Queue Celery task for async posting
                try:
                    # Get base_url for consistency (though task can work without it)
                    base_url = getattr(settings, 'SITE_DOMAIN', 'wedesignz.com')
                    if not base_url.startswith('http'):
                        base_url = f"https://{base_url}"
                    
                    # Queue the task
                    task_result = post_to_instagram.delay(instagram_post.id, base_url)
                    logger.info(f"Queued Instagram post task {task_result.id} for post {instagram_post.id}, product {product_id}")
                    
                    created_posts.append({
                        'id': instagram_post.id,
                        'product_id': product_id,
                        'status': 'queued'
                    })
                    
                    # Add small delay between queuing tasks to avoid overwhelming the worker
                    # and to respect Instagram rate limits. Only delay if there are more posts to process.
                    if index < total_posts - 1:
                        time.sleep(0.5)  # 500ms delay between queuing tasks
                        
                except Exception as e:
                    # If task queuing fails, mark the post as failed
                    error_msg = f"Failed to queue Instagram post task: {str(e)}"
                    logger.error(f"Post {index + 1} failed: {error_msg}", exc_info=True)
                    try:
                        instagram_post.status = 'failed'
                        instagram_post.error_message = error_msg
                        instagram_post.save(update_fields=['status', 'error_message'])
                    except Exception as save_error:
                        logger.error(f"Failed to update InstagramPost {instagram_post.id} status: {save_error}")
                    errors.append({
                        'post': post_data,
                        'error': error_msg
                    })
                    continue
                    
            except Exception as e:
                # Catch any unexpected errors for this specific post
                error_msg = f"Unexpected error processing post {index + 1}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append({
                    'post': post_data,
                    'error': error_msg
                })
                continue  # Continue processing remaining posts
        
        response_data = {
            'message': f'Queued {len(created_posts)} post(s) for Instagram',
            'posts_queued': len(created_posts),
            'post_ids': [p['id'] for p in created_posts],
            'errors': errors if errors else None
        }
        
        return JsonResponse(response_data, status=200)
        
    except Exception as e:
        logger.error(f"Error creating Instagram posts: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': f'Error creating posts: {str(e)}'
        }, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def instagram_posts_list(request):
    """
    Get list of Instagram posts with filtering and pagination.
    """
    from django.core.paginator import Paginator
    
    status_filter = request.GET.get('status')
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 20))
    
    posts = InstagramPost.objects.all()
    
    if status_filter:
        posts = posts.filter(status=status_filter)
    
    posts = posts.order_by('-created_at')
    
    paginator = Paginator(posts, limit)
    page_obj = paginator.get_page(page)
    
    posts_data = []
    for post in page_obj.object_list:
        posts_data.append({
            'id': post.id,
            'product_id': post.product.id,
            'product_title': post.product.title,
            'media_type': post.media_type,
            'caption': post.caption,
            'post_type': post.post_type,
            'status': post.status,
            'post_id': post.post_id,
            'post_url': post.post_url,
            'error_message': post.error_message,
            'retry_count': post.retry_count,
            'created_at': post.created_at.isoformat(),
            'posted_at': post.posted_at.isoformat() if post.posted_at else None,
        })
    
    return JsonResponse({
        'data': posts_data,
        'pagination': {
            'page': page,
            'limit': limit,
            'total': paginator.count,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
        }
    })

