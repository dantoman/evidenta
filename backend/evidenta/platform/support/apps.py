from django.apps import AppConfig


class SupportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "evidenta.platform.support"
    label = "support"
    verbose_name = "Support grants"
