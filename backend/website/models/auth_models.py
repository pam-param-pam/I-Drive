import datetime
import hashlib
import hmac
import secrets

import shortuuid
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import CheckConstraint, Q, UniqueConstraint, F
from django.utils import timezone
from shortuuidfield import ShortUUIDField


class PerDeviceTokenManager(models.Manager):
    def _hash(self, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    def create_token(self, user, device_name: str, device_id: str, expires: datetime.timedelta, ip_address: str, user_agent: str, country: str = None, city: str = None,
                     device_type: str = None):
        raw = secrets.token_urlsafe(32)
        hashed = self._hash(raw)
        expires_at = timezone.now() + expires if expires else None
        instance = self.create(
            user=user,
            token_hash=hashed,
            device_name=device_name,
            device_id=device_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            country=country,
            city=city,
            device_type=device_type
        )
        return raw, instance

    def get_active_for_user(self, user):
        now = timezone.now()
        return self.filter(user=user).filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))

    def get_token_from_raw_token(self, raw_token):
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

        try:
            token_obj = PerDeviceToken.objects.select_related('user').get(token_hash=token_hash)
        except PerDeviceToken.DoesNotExist:
            return None

        if not token_obj.check_token(raw_token):
            return None

        if token_obj.is_expired():
            token_obj.delete()
            return None

        token_obj.mark_used()
        return token_obj


class PerDeviceToken(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='device_tokens')
    token_hash = models.CharField(max_length=64, db_index=True)
    device_name = models.CharField(max_length=50)
    device_id = ShortUUIDField(default=shortuuid.uuid, db_index=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True)
    expires_at = models.DateTimeField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    country = models.CharField(max_length=50, null=True)
    city = models.CharField(max_length=50, null=True)
    device_type = models.CharField(max_length=10, choices=[("mobile", "Mobile"), ("pc", "PC"), ("code", "Code")])
    objects = PerDeviceTokenManager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(device_type__in=["mobile", "pc", "code"]) | models.Q(device_type__isnull=True),
                name="valid_device_type"
            ),
            CheckConstraint(
                check=~Q(token_hash__exact=""),
                name="%(class)s_token_hash_not_empty",
            ),
            CheckConstraint(
                check=~Q(device_id__exact=""),
                name="%(class)s_device_id_not_empty",
            ),
            CheckConstraint(
                check=(Q(expires_at__isnull=True) | Q(expires_at__gte=F("created_at"))),
                name="%(class)s_expires_after_created",
            ),
            CheckConstraint(
                check=(Q(last_used_at__isnull=True) | Q(last_used_at__gte=F("created_at"))),
                name="%(class)s_last_used_after_created",
            ),
            UniqueConstraint(
                fields=["user", "device_id"],
                name="%(class)s_unique_device_per_user",
            ),
            UniqueConstraint(
                fields=["user", "token_hash"],
                name="%(class)s_unique_token_hash_per_user",
            )
        ]
        ordering = ["-created_at"]
        verbose_name = "Per-device token"
        verbose_name_plural = "Per-device tokens"

    def is_expired(self):
        return self.expires_at is not None and timezone.now() >= self.expires_at

    def check_token(self, raw_token: str) -> bool:
        hashed = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        # constant-time comparison
        return hmac.compare_digest(hashed, self.token_hash)

    def mark_used(self):
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])

    def __str__(self):
        return f"Token for {self.device_name} for user {self.user}"
