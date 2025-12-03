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

