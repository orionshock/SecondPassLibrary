from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self) -> None:
        # Ensure ServerSetting cache invalidates on save/delete even when settings
        # are edited outside core.server_settings.set_server_setting().
        from . import checks  # noqa: F401
        from . import signals  # noqa: F401
