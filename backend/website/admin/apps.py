from django.contrib.admin.apps import AdminConfig


class WebsiteAdminConfig(AdminConfig):
    default_site = "website.admin.site.IDriveAdminSite"

    def ready(self):
        super().ready()
        # this import is required
        from . import registration  # noqa: F401
