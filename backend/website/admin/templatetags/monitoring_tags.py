from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def grafana_url() -> str:
    return settings.GRAFANA_URL
