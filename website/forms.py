from django import forms

from website.formatChecker import ContentTypeRestrictedFileField


class UploadFileForm(forms.Form):
    file = ContentTypeRestrictedFileField(max_upload_size=10737418240)

