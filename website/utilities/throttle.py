from rest_framework.throttling import UserRateThrottle


class MediaRateThrottle(UserRateThrottle):
    scope = 'media'

class FolderPasswordRateThrottle(UserRateThrottle):
    scope = 'folder_password'

class SearchRateThrottle(UserRateThrottle):
    scope = 'search'
