from django.apps import AppConfig


class OutbreakConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "outbreaks"

    def ready(self):
        from . import signals
