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
    
    if error:
        logger.error(f"Pinterest OAuth error: {error}")
        return HttpResponse(
            f"<h1>Pinterest Authorization Failed</h1>"
            f"<p>Error: {error}</p>"
            f"<p>Please try again.</p>",
            status=400
        )
    
    if not code:
        return HttpResponse(
            "<h1>Pinterest Authorization Failed</h1>"
            "<p>No authorization code received.</p>",
            status=400
        )
    
    app_id = getattr(settings, 'PINTEREST_APP_ID', None)
    app_secret = getattr(settings, 'PINTEREST_APP_SECRET', None)
    redirect_uri = getattr(settings, 'PINTEREST_REDIRECT_URI', None)
    
    if not app_id or not app_secret:
        return HttpResponse(
            "<h1>Configuration Error</h1>"
            "<p>Pinterest credentials not configured.</p>",
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
            return HttpResponse(
                "<h1>Token Exchange Failed</h1>"
                "<p>No access token received from Pinterest.</p>",
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
        
        # Display success message
        return HttpResponse(
            f"""
            <html>
            <head>
                <title>Pinterest Authorization Successful</title>
                <style>
                    body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
                    .success {{ background: #d4edda; border: 1px solid #c3e6cb; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .info {{ background: #d1ecf1; border: 1px solid #bee5eb; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
                    ul {{ line-height: 1.8; }}
                </style>
            </head>
            <body>
                <h1>✅ Pinterest Authorization Successful!</h1>
                
                <div class="success">
                    <h2>Access Token Saved</h2>
                    <p>Your Pinterest access token has been saved to the database.</p>
                    <p><strong>Token expires:</strong> {token_expires_at.strftime('%Y-%m-%d %H:%M:%S') if token_expires_at else 'Not specified'}</p>
                </div>
                
                {boards_info}
                
                <div class="info">
                    <h2>Next Steps:</h2>
                    <ol>
                        <li>If you see boards above, copy the <strong>Board ID</strong> of the board where you want to post designs</li>
                        <li>Set the board ID using the management command: <code>python manage.py set_pinterest_board BOARD_ID</code></li>
                        <li>Or update it in the admin panel under "Pinterest Integration"</li>
                        <li>Test by approving a design - it should automatically post to Pinterest!</li>
                    </ol>
                </div>
                
                <p><a href="/admin/common/pinterestintegration/">Go to Admin Panel</a> | <a href="/api/pinterest/status/">Check Status</a></p>
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
        
        return HttpResponse(
            f"<h1>Token Exchange Failed</h1>"
            f"<p>Error: {error_msg}</p>"
            f"<p>Please try authorizing again.</p>",
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

