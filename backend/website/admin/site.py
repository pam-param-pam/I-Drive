from django.contrib.admin import AdminSite
from django.urls import reverse


class IDriveAdminSite(AdminSite):
    section_order = (
        "Accounts",
        "File System",
        "Discord Media",
        "File Metadata",
        "Internal Namespace",
        "Sharing",
        "Operations",
        "Discord",
        "Other",
    )

    model_sections = {
        "Folder": "File System",
        "File": "File System",
        "TrashRoot": "Internal Namespace",
        "FolderLockPolicy": "Internal Namespace",
        "FolderHashWork": "Internal Namespace",
        "FolderHeightRepair": "Internal Namespace",
        "Fragment": "Discord Media",
        "Thumbnail": "Discord Media",
        "Moment": "Discord Media",
        "Subtitle": "Discord Media",
        "VideoMetadata": "File Metadata",
        "VideoTrack": "File Metadata",
        "AudioTrack": "File Metadata",
        "SubtitleTrack": "File Metadata",
        "RawMetadata": "File Metadata",
        "PhotoMetadata": "File Metadata",
        "MediaPosition": "File Metadata",
        "Tag": "File Metadata",
        "ShareableLink": "Sharing",
        "ShareAccess": "Sharing",
        "ShareAccessEvent": "Sharing",
        "UserSettings": "Accounts",
        "UserPerms": "Accounts",
        "PerDeviceToken": "Accounts",
        "Notification": "Accounts",
        "DiscordSettings": "Discord",
        "Channel": "Discord",
        "Webhook": "Discord",
        "Bot": "Discord",
        "DeletionScope": "Operations",
        "DeletionFileWorkItem": "Operations",
        "DeletionFolderWorkItem": "Operations",
        "DeletionJob": "Operations",
        "RawExtractionClaim": "Operations",
        "UserZIP": "Other",
    }

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        if app_label is not None:
            return app_list

        website_app = next((app for app in app_list if app["app_label"] == "website"), None)
        if website_app is None:
            return app_list

        sections = {name: [] for name in self.section_order}
        for model in website_app["models"]:
            section = self.model_sections.get(model["object_name"], "Other")
            sections[section].append(model)

        grouped = []
        app_url = reverse("admin:app_list", kwargs={"app_label": "website"}, current_app=self.name)
        for name in self.section_order:
            models = sections[name]
            if not models:
                continue
            grouped.append({
                "name": name,
                "app_label": "website",
                "app_url": app_url,
                "has_module_perms": website_app["has_module_perms"],
                "models": models,
            })

        result = [app for app in app_list if app["app_label"] != "website"]
        result.extend(grouped)
        return result
