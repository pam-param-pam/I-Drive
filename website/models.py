import uuid

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Folder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)

    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    maintainer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='folder_maintainer_user')

    viewer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='folder_viewer_user')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.name == "root":
            folders = Folder.objects.filter(owner=self.owner.id)
            for folder in folders:
                if folder.name == "root":
                    self.name = "_root"

        super(Folder, self).save(*args, **kwargs)
class File(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, null=False, blank=False)
    name = models.CharField(max_length=255, null=False, blank=False)
    extension = models.CharField(max_length=10, null=False, blank=False)
    streamable = models.BooleanField(default=False)
    size = models.BigIntegerField()
    key = models.BinaryField()
    encrypted_size = models.BigIntegerField()
    uploaded_at = models.DateTimeField(default=timezone.now)
    m3u8_message_id = models.URLField(null=True)
    parent = models.ForeignKey(Folder, on_delete=models.CASCADE)

    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    maintainer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='file_maintainer_user')
    viewer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='file_viewer_user')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.encrypted_size is None:
            self.encrypted_size = self.size
        super(File, self).save(*args, **kwargs)


class Fragment(models.Model):
    sequence = models.SmallIntegerField()
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    file = models.ForeignKey(File, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255)

    def __str__(self):
        return self.sequence

