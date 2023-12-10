from django.forms import forms, FileField
from django.template.defaultfilters import filesizeformat
from django.utils.translation import gettext_lazy as _

class ContentTypeRestrictedFileField(FileField):
    def __init__(self, *args, **kwargs):
        self.max_upload_size = kwargs.pop("max_upload_size", 0)

        super(ContentTypeRestrictedFileField, self).__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):

        data = super(ContentTypeRestrictedFileField, self).clean(*args, **kwargs)

        file = data

        if file.size > self.max_upload_size:
            raise forms.ValidationError(_('Please keep filesize under %s. Current filesize %s') % (filesizeformat(self.max_upload_size), filesizeformat(file.size)))

        return data