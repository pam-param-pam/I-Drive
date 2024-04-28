from rest_framework.views import exception_handler
from rest_framework.exceptions import Throttled


def custom_exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = exception_handler(exc, context)

    if isinstance(exc, Throttled):  # check that a Throttled exception is raised
        custom_response_data = {
            'error': 'Rate Limit Exceeded',
            'details': 'You are rate limited for exceeding limits. Please calm down >:(',
            'retry_after': '%d seconds' % exc.wait
        }
        response.data = custom_response_data

    return response
