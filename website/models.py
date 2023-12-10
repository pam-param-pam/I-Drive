import uuid

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Folder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    parent_id = models.CharField(max_length=255, default="root")


class File(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    extension = models.CharField(max_length=10)
    streamable = models.BooleanField(default=False)
    size = models.BigIntegerField()
    key = models.CharField(max_length=32)
    #owner = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(default=timezone.now)
    m3u8_message_id = models.URLField()
    parent_id = models.CharField(max_length=255, default="root")
    def __str__(self):
        return self.name

class Fragment(models.Model):
    sequence = models.SmallIntegerField()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    file = models.ForeignKey(File, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255)

