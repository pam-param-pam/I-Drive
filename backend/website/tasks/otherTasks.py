import ipaddress

import requests

from website.celery import app
from website.constants import cache
from website.models import Fragment
from website.services import attachment_service, cache_service


@app.task(queue="cleanup")
def update_router_public_ip():
    response = requests.get("https://api.ipify.org", timeout=5)
    response.raise_for_status()

    value = response.text.strip()
    ipaddress.ip_address(value)

    key = cache_service.get_router_ip_key()
    cache.set(key, value, timeout=36000)
    return value


@app.task(queue="cleanup", expires=1)
def prefetch_next_fragments(fragment_id: str, number_to_prefetch: int):
    fragment = Fragment.objects.get(id=fragment_id)
    fragments = Fragment.objects.filter(file=fragment.file)
    filtered_fragments = fragments.filter(sequence__gt=fragment.sequence).order_by("sequence")[:number_to_prefetch]

    for next_fragment in filtered_fragments:
        attachment_service.get_attachment_url(user=next_fragment.file.owner, resource=next_fragment, file=next_fragment.file)
