import secrets

import shortuuid
from django.contrib.auth.models import User
from django.db import models
from django.db.models import CheckConstraint, Q
from django.utils import timezone
from shortuuidfield import ShortUUIDField

from .file_models import File
from .folder_models import Folder


class UserZIP(models.Model):
    id = ShortUUIDField(primary_key=True, default=shortuuid.uuid, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    files = models.ManyToManyField(File, related_name='user_zips', blank=True)
    folders = models.ManyToManyField(Folder, related_name='user_zips', blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True, blank=True)
    name = models.CharField(max_length=255, blank=True)

    constraints = [
        # token must not be empty
        CheckConstraint(
            check=~Q(token__exact=""),
            name="%(class)s_token_not_empty",
        ),

        # name must not be empty
        CheckConstraint(
            check=~Q(name__exact=""),
            name="%(class)s_name_not_empty",
        ),
    ]

    def __str__(self):
        return f'UserZIP[{self.id} by {self.owner}]'

    def save(self, *args, **kwargs):
        if self.token is None or self.token == '':
            self.token = secrets.token_urlsafe(32)

        if len(self.files.all()) == 0 and len(self.folders.all()) == 1:
            self.name = self.folders.all()[0].name
        else:
            self.name = f"I-Drive-{self.id}"
        super(UserZIP, self).save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.created_at + timezone.timedelta(days=7)


