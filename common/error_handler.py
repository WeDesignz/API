"""
Error Handler Middleware
Logs all 500 errors with full details to help debug issues.
"""
import logging
import traceback
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware:
    """
    Middleware to catch and log all exceptions that result in 500 errors.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """
        Catch all exceptions and log them with full details.
        """
        error_message = str(exception)
        error_traceback = traceback.format_exc()
        
        # Log the error with full context
        logger.error(
            f"500 Error on {request.method} {request.path}",
            extra={
                'request_path': request.path,
                'request_method': request.method,
                'user': str(request.user) if hasattr(request, 'user') else 'Anonymous',
                'error_message': error_message,
                'error_traceback': error_traceback,
                'request_data': dict(request.GET) if request.method == 'GET' else dict(request.POST),
            }
        )
        
        # Print to console for immediate visibility
        print(f"\n{'='*80}")
        print(f"500 ERROR: {request.method} {request.path}")
        print(f"{'='*80}")
        print(f"Error: {error_message}")
        print(f"\nTraceback:")
        print(error_traceback)
        print(f"{'='*80}\n")
        
        # Return JSON response with error details
        if settings.DEBUG:
            return JsonResponse({
                'error': 'Internal Server Error',
                'message': error_message,
                'path': request.path,
                'method': request.method,
                'traceback': error_traceback.split('\n') if settings.DEBUG else None
            }, status=500)
        else:
            return JsonResponse({
                'error': 'Internal Server Error',
                'message': 'An error occurred while processing your request. Please try again later.'
            }, status=500)


