"""
Error Handler Middleware
Logs all 500 errors with full details to help debug issues.
"""
import traceback
from django.http import JsonResponse, Http404
from django.conf import settings


class ErrorHandlerMiddleware:
    """
    Middleware to catch and log all exceptions that result in 500 errors.
    Http404 exceptions are not caught as they should return 404, not 500.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """
        Catch all exceptions and log them with full details.
        Http404 exceptions are allowed to propagate so Django can handle them properly.
        """
        # Don't catch Http404 - let Django handle it normally (returns 404, not 500)
        if isinstance(exception, Http404):
            return None
        
        error_message = str(exception)
        error_traceback = traceback.format_exc()
        
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

