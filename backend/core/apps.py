from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self) -> None:
        # Model signals route every ServerSetting write through the same
        # transaction-aware committed-effects owner.
        from . import checks  # noqa: F401
        from . import signals  # noqa: F401
