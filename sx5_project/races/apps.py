from django.apps import AppConfig


class RaceResultsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'races'

    def ready(self):
        import races.signals
