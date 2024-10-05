import asyncio

from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, throttle_classes

from ..utilities.throttle import MediaRateThrottle


@api_view(['GET'])
@throttle_classes([MediaRateThrottle])
# @handle_common_errors
def get_file_url_view(request):
    async def iterable_content():
        for _ in range(1000):
            await asyncio.sleep(0.1)
            print('Returning chunk')
            yield b'a'

    return StreamingHttpResponse(iterable_content())


