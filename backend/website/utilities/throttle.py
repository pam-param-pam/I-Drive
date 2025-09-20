import time
from datetime import datetime, timedelta

from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import UserRateThrottle

from ..utilities.constants import cache


class MyUserRateThrottleBase(UserRateThrottle):
    bucket = None

    def __init__(self):
        super().__init__()
        self.fail_block = 30
        self.fail_limit = 15
        self.fail_count = None
        self.request = None

    def get_cache_key(self, request, view):
        self.request = request
        if not self.bucket:
            raise ImproperlyConfigured("Throttle class must define a bucket.")
        return super().get_cache_key(request, view)

    def allow_request(self, request, view):
        self.request = request

        # STEP 1. Check general rate limit
        # allow_request already calls throttle_failure() or throttle_success()
        # so we should be careful not to call it again. Especially because calling
        # throttle_success() twice will lead to doubling the history records
        user_allowed = super().allow_request(request, view)
        if not user_allowed:
            return self.throttle_failure()

        # STEP 2. Check failed attempts (custom logic)
        remaining_failed_requests = self.get_remaining_failed_requests()
        if remaining_failed_requests <= 0:
            return self.throttle_failure()

        return user_allowed

    def parse_rate(self, rate):
        if rate is None:
            return None, None
        num_requests, duration = rate.split('/')
        num_requests = int(num_requests)
        duration = duration.lower()
        period = duration[-1]
        try:
            duration_time = int(duration[:-1])
        except ValueError:
            duration_time = 1
        duration_time *= {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[period]
        return num_requests, duration_time

    def apply_ratelimit_headers(self):
        self.request.META["rate_limit_remaining"] = min(self.get_remaining_requests(), self.get_remaining_failed_requests())
        self.request.META["rate_limit_reset_after"] = round(self.wait(), 4)
        self.request.META["rate_limit_bucket"] = self.bucket

    def throttle_failure(self):
        self.apply_ratelimit_headers()
        return super().throttle_failure()

    def throttle_success(self):
        self.apply_ratelimit_headers()
        return super().throttle_success()

    def wait(self):
        if self.get_remaining_failed_requests() <= 0:
            fail_key = self._get_fail_key(self.request)
            fail_data = cache.get(fail_key, [])
            now = time.time()

            recent_fails = sorted(t for t in fail_data if now - t < self.fail_block)
            fail_count = len(recent_fails)

            if fail_count < self.fail_limit / 2:
                return 0

            # How many fails must expire to be below half
            target_fails = int(fail_count - (self.fail_limit // 2)) + 1
            fail_to_expire = recent_fails[:target_fails][-1]
            wait_time = max((fail_to_expire + self.fail_block) - now, 0)

            return wait_time

        return self.get_reset_time()

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

    def get_remaining_failed_requests(self):
        """
        Returns the number of remaining requests in the global fail bucket before the limit is hit.
        """
        fail_key = self._get_fail_key(self.request)
        fail_data = cache.get(fail_key, [])
        now = time.time()

        recent_fails = [t for t in fail_data if now - t < self.fail_block]
        return max(self.fail_limit - len(recent_fails), 0)

    def get_remaining_requests(self):
        """
        Returns the number of remaining requests before the limit is hit.
        """
        if self.rate is None:
            return float('inf')

        if not hasattr(self, 'history') or not hasattr(self, 'now'):
            raise AttributeError("This method should be called after `allow_request` method.")

        return max(self.num_requests - len(self.history), 0)

    def _get_fail_key(self, request):
        if request.user.is_authenticated:
            return f"fail:{request.user.pk}"
        return f"fail_ip:{request.META.get('REMOTE_ADDR')}"

class defaultAnonUserThrottle(MyUserRateThrottleBase):
    scope = 'anon'
    bucket = "aBcDeFgHiJ"

class defaultAuthUserThrottle(MyUserRateThrottleBase):
    scope = 'user'
    bucket = "RpQwXsEfGt"

class FolderPasswordThrottle(MyUserRateThrottleBase):
    scope = 'folder_password'
    bucket = "zYxWvUtSrQ"

class MediaThrottle(MyUserRateThrottleBase):
    scope = 'media'
    bucket = "lMnOpQrStU"

class AnonUserMediaThrottle(MyUserRateThrottleBase):
    scope = 'media_anon'
    bucket = "lYnOX4rStU"

class SearchThrottle(MyUserRateThrottleBase):
    scope = 'search'
    bucket = "VwXyZaBcDe"

class PasswordChangeThrottle(MyUserRateThrottleBase):
    scope = 'password_change'
    bucket = "FgHiJkLmNo"

class RegisterThrottle(MyUserRateThrottleBase):
    scope = 'register'
    bucket = "FdHakamxf"

class LoginThrottle(MyUserRateThrottleBase):
    scope = 'login'
    bucket = "Ad3DkDf5o"

class DiscordSettingsThrottle(MyUserRateThrottleBase):
    scope = 'discord_settings'
    bucket = "YWJob2rcw"

