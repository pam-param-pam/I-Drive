from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled, PermissionDenied, ValidationError

from ..utilities.other import format_wait_time


def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)
    if isinstance(exc, Throttled):
        custom_response_data = {
            'error': 'Rate Limit Exceeded >:(',
            'details': f'Enhance your calm, try again in {format_wait_time(exc.wait)}',
            'code': 429,
            'retry_after': f'{exc.wait} seconds'
        }
        response.data = custom_response_data

    if isinstance(exc, ValidationError):
        details = response.data.get('non_field_errors')
        if details:
            details = details[0]
        else:
            details = response.data

        custom_response_data = {
            "error": 'errors.validationFailed',
            "code": 400,
            "details": details,
        }
        response.data = custom_response_data

    if isinstance(exc, PermissionDenied):
        custom_response_data = {
            'error': 'errors.permissionDenied',
            'code': 403,
            'details': exc.detail,
        }
        response.data = custom_response_data

    return response
