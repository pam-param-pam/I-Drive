from django import forms

from website.formatChecker import ContentTypeRestrictedFileField


class UploadFileForm(forms.Form):
    file = ContentTypeRestrictedFileField(max_upload_size=5368709120)
    #folder_id = forms.UUIDField(disabled=True)
