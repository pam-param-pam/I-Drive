from datetime import datetime, timedelta

from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import UserRateThrottle


class UserRateThrottleBase(UserRateThrottle):

    bucket = ""

    def __init__(self):
        super().__init__()
        self.request = None

    def get_cache_key(self, request, view):
        self.request = request
        if not getattr(self, 'bucket', None):
            msg = "No bucket rate"
            raise ImproperlyConfigured(msg)

        return super().get_cache_key(request, view)

    def throttle_success(self):

        self.request.META["rate_limit_remaining"] = self.get_remaining_requests()
        self.request.META["rate_limit_reset_after"] = self.get_reset_time()
        self.request.META["rate_limit_bucket"] = self.bucket

        return super().throttle_success()

    def get_reset_time(self):
        """
        Calculate the time when the rate limit bucket resets, in seconds.
        """
        if self.rate is None:
            return None  # No limit

        if not hasattr(self, 'history') or not hasattr(self, 'now'):
            raise AttributeError("This method should be called after `allow_request` method.")

        if not self.history:  # If history is empty, no requests have been made yet
            return self.duration  # Reset time is the duration itself, in seconds

        # Convert the float timestamp to a datetime object
        last_request_time = datetime.fromtimestamp(self.history[-1])

        # Calculate the time when the rate limit resets
        reset_time = last_request_time + timedelta(seconds=self.duration)

        # Calculate the total number of seconds until the reset time relative to the current time
        seconds_until_reset = (reset_time - datetime.now()).total_seconds()

        # Return the reset time in seconds
        return seconds_until_reset

    def get_remaining_requests(self):
        """
        Returns the number of remaining requests before the limit is hit.
        """
        if self.rate is None:
            return float('inf')  # No limit

        if not hasattr(self, 'history') or not hasattr(self, 'now'):
            raise AttributeError("This method should be called after `allow_request` method.")

        return self.num_requests - len(self.history)


class MyAnonRateThrottle(UserRateThrottleBase):
    scope = 'anon'
    bucket = "aBcDeFgHiJ"

class MyUserRateThrottle(UserRateThrottleBase):
    scope = 'user'
    bucket = "RpQwXsEfGt"

class FolderPasswordRateThrottle(UserRateThrottleBase):
    scope = 'folder_password'
    bucket = "zYxWvUtSrQ"

class MediaRateThrottle(UserRateThrottleBase):
    scope = 'media'
    bucket = "lMnOpQrStU"

class SearchRateThrottle(UserRateThrottleBase):
    scope = 'search'
    bucket = "VwXyZaBcDe"

class PasswordChangeThrottle(UserRateThrottleBase):
    scope = 'password_change'
    bucket = "FgHiJkLmNo"
