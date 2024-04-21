from rest_framework.throttling import UserRateThrottle


class MediaRateThrottle(UserRateThrottle):
    scope = 'media'
