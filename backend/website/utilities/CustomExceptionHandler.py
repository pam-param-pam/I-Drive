from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled, PermissionDenied

from ..utilities.other import format_wait_time


def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)
    if isinstance(exc, Throttled):  # check that a Throttled exception is raised
        custom_response_data = {
            'error': 'Rate Limit Exceeded >:(',
            'details': f'Enhance your calm, try again in {format_wait_time(exc.wait)}',
            'retry_after': f'{exc.wait} seconds'
        }
        response.data = custom_response_data

    if isinstance(exc, PermissionDenied):
        custom_response_data = {
            'error': 'Permission denied',
            'details': 'You are not allowed to perform this action',
        }
        response.data = custom_response_data

    print(exc)
    return response
