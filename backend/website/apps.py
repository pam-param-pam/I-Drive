from django.apps import AppConfig

class WebsiteConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "website"

    def ready(self):
        from .safety.helper import get_classes_extending_discordAttachmentMixin

        subclasses = get_classes_extending_discordAttachmentMixin()
        if len(subclasses) == 0:
            raise RuntimeError(
                "No models extend DiscordAttachmentMixin."
                "This means that 'get_classes_extending_discordAttachmentMixin' no longer works. This will CORRUPT data integrity on discord"
            )
