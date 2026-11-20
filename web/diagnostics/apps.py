from django.apps import AppConfig


class DiagnosticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'diagnostics'

    def ready(self):
        from django.conf import settings

        if settings.AI_WARMUP:
            import threading

            from .ai.assistant import warm_up

            threading.Thread(target=warm_up, daemon=True).start()
