import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Folder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, null=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
    maintainer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='folder_maintainer_user')

    viewer = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='folder_viewer_user')

    def __str__(self):
        return self.name

    def clean(self):
        if self.parent == self:
            raise ValidationError("A folder cannot be its own parent.")

    def save(self, *args, **kwargs):
        folders = Folder.objects.filter(owner=self.owner.id)

        if self.name == "root":
            if self.parent:
                self.parent = None
            else:
                if any(folder.name == "root" for folder in folders):
                    self.name = "_root"

        # Set self.parent to folder with name "root" if self.parent is None if it is found
        if not self.parent and self.name != "root":
            matching_folder = next((folder for folder in folders if folder.name == "root"), None)
            if matching_folder:
                self.parent = matching_folder

        super(Folder, self).save(*args, **kwargs)


class File(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, null=False, blank=False)
    name = models.CharField(max_length=255, null=False, blank=False)
    extension = models.CharField(max_length=10, null=False, blank=False)
    streamable = models.BooleanField(default=False)
    size = models.BigIntegerField()
    key = models.BinaryField()
    encrypted_size = models.BigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    m3u8_message_id = models.URLField(null=True, blank=True)
    parent = models.ForeignKey(Folder, on_delete=models.CASCADE)
    ready = models.BooleanField(default=False)

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
    size = models.BigIntegerField()

    def __str__(self):
        return str(self.sequence)
