"""
Custom exception handler for Django REST Framework.
Provides consistent error response format across the API.
"""
from rest_framework.views import exception_handler
from rest_framework import status
from rest_framework.exceptions import (
    ValidationError, AuthenticationFailed, NotAuthenticated,
    PermissionDenied, NotFound, Throttled
)
from django.http import Http404
from django.core.exceptions import ValidationError as DjangoValidationError
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns consistent error format.
    
    Response format:
    {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Human readable message",
            "details": {}  # Optional field-specific errors
        }
    }
    """
    # Call DRF's default handler first
    response = exception_handler(exc, context)
    
    # Log the exception
    logger.error(
        f"API Exception: {type(exc).__name__}: {exc}",
        extra={
            'view': context.get('view'),
            'request': context.get('request'),
            'exception_type': type(exc).__name__,
        },
        exc_info=True
    )
    
    if response is not None:
        # Customize response format
        error_response = {
            'error': {
                'code': get_error_code(exc),
                'message': get_error_message(exc, response),
            }
        }
        
        # Add details for validation errors
        if isinstance(exc, ValidationError) and response.data:
            error_response['error']['details'] = response.data
        
        response.data = error_response
        return response
    
    # Handle unhandled exceptions
    if isinstance(exc, Http404):
        return create_error_response(
            status.HTTP_404_NOT_FOUND,
            'NOT_FOUND',
            'The requested resource was not found.'
        )
    
    if isinstance(exc, DjangoValidationError):
        return create_error_response(
            status.HTTP_400_BAD_REQUEST,
            'VALIDATION_ERROR',
            str(exc),
            details=exc.message_dict if hasattr(exc, 'message_dict') else {}
        )
    
    # Log unexpected errors
    logger.critical(f"Unhandled exception: {exc}", exc_info=True)
    
    return create_error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        'INTERNAL_SERVER_ERROR',
        'An unexpected error occurred. Please try again later.'
    )


def get_error_code(exc):
    """Map exception types to error codes."""
    error_codes = {
        ValidationError: 'VALIDATION_ERROR',
        AuthenticationFailed: 'AUTHENTICATION_FAILED',
        NotAuthenticated: 'NOT_AUTHENTICATED',
        PermissionDenied: 'PERMISSION_DENIED',
        NotFound: 'NOT_FOUND',
        Throttled: 'RATE_LIMITED',
    }
    return error_codes.get(type(exc), 'ERROR')


def get_error_message(exc, response):
    """Extract human-readable message from exception/response."""
    if isinstance(exc, ValidationError):
        if hasattr(exc, 'detail'):
            if isinstance(exc.detail, dict):
                return 'Validation failed for one or more fields.'
            elif isinstance(exc.detail, list):
                return str(exc.detail[0]) if exc.detail else 'Validation failed.'
    return getattr(exc, 'detail', str(exc)) or 'An error occurred.'


def create_error_response(http_status, code, message, details=None):
    """Create standardized error response."""
    from rest_framework.response import Response
    
    error_data = {
        'error': {
            'code': code,
            'message': message,
        }
    }
    
    if details:
        error_data['error']['details'] = details
    
    return Response(error_data, status=http_status)