from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled, PermissionDenied


def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)
    if isinstance(exc, Throttled):  # check that a Throttled exception is raised
        custom_response_data = {
            'error': 'Rate Limit Exceeded >:(',
            'details': 'Enhance your calm, try again in %d seconds' % exc.wait,
            'retry_after': '%d seconds' % exc.wait
        }
        response.data = custom_response_data

    if isinstance(exc, PermissionDenied):
        custom_response_data = {
            'error': 'Permission denied',
            'details': 'You are not allowed to perform this action',
        }
        response.data = custom_response_data
    return response
