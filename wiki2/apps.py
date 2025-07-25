from django.apps import AppConfig


class Wiki2Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wiki2'

    def ready(self):
        import wiki2.signals
